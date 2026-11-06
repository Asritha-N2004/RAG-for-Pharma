import secrets,base64,hashlib
from urllib.parse import urlencode
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,delete
from app.db.database import get_db
from app.models.entities import MfaCredential,RecoveryCode
from app.core.security import current_user,audit,issue
from app.services.mfa_service import credential,encrypt,verify,reauthenticate,revoke_all
router=APIRouter(prefix='/api/auth/mfa')
@router.get('')
def status(user=Depends(current_user),db=Depends(get_db)):
    row=credential(db,user)
    return {'enabled':bool(row and row.enabled),'enrollment_pending':bool(row and not row.enabled),'unused_recovery_codes':len(list(db.scalars(select(RecoveryCode).where(RecoveryCode.user_id==user.id,RecoveryCode.used==0))))}
@router.post('/enroll')
def enroll(data:dict,user=Depends(current_user),db=Depends(get_db)):
    reauthenticate(db,user,data.get('password'),data.get('code'));row=credential(db,user)
    if row and row.enabled:raise HTTPException(409,'MFA is already enabled')
    secret=base64.b32encode(secrets.token_bytes(20)).decode()
    if row:row.encrypted_secret=encrypt(secret);row.last_step=-1
    else:db.add(MfaCredential(org_id=user.org_id,user_id=user.id,encrypted_secret=encrypt(secret)))
    audit(db,user,'MFA_ENROLLMENT_START',user.id);db.commit()
    return {'secret':secret,'provisioning_uri':'otpauth://totp/PharmaReg-XAI:'+user.email+'?'+urlencode({'secret':secret,'issuer':'PharmaReg-XAI','algorithm':'SHA1','digits':6,'period':30})}
@router.post('/confirm')
def confirm(data:dict,user=Depends(current_user),db=Depends(get_db)):
    row=credential(db,user)
    if not row or row.enabled or not verify(db,user,data.get('code'),allow_pending=True):raise HTTPException(401,'Invalid enrollment code')
    row.enabled=1;db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==user.id))
    codes=[secrets.token_hex(8) for _ in range(10)]
    for value in codes:db.add(RecoveryCode(org_id=user.org_id,user_id=user.id,digest=hashlib.sha256(value.encode()).hexdigest()))
    revoke_all(db,user);audit(db,user,'MFA_ENABLED',user.id);db.commit()
    return {**issue(db,user),'recovery_codes':codes}
@router.post('/disable')
def disable(data:dict,user=Depends(current_user),db=Depends(get_db)):
    reauthenticate(db,user,data.get('password'),data.get('code'));row=credential(db,user)
    if row:db.delete(row)
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==user.id));revoke_all(db,user);audit(db,user,'MFA_DISABLED',user.id);db.commit();return issue(db,user)
