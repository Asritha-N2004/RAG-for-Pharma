import base64,hashlib,hmac,secrets,struct,time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select,update
from fastapi import HTTPException
from app.models.entities import MfaCredential,RecoveryCode,Token
from app.core.config import SECRET_KEY
def encrypt(value):
    nonce=secrets.token_bytes(12);key=hashlib.sha256(('identity:'+SECRET_KEY).encode()).digest()
    return base64.urlsafe_b64encode(nonce+AESGCM(key).encrypt(nonce,value.encode(),b'PharmaReg identity v1')).decode()
def decrypt(value):
    raw=base64.urlsafe_b64decode(value);key=hashlib.sha256(('identity:'+SECRET_KEY).encode()).digest()
    return AESGCM(key).decrypt(raw[:12],raw[12:],b'PharmaReg identity v1').decode()
def code(secret,step=None):
    step=int(time.time())//30 if step is None else step
    value=hmac.new(base64.b32decode(secret),struct.pack('>Q',step),hashlib.sha1).digest();offset=value[-1]&15
    return str((struct.unpack('>I',value[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)
def credential(db,user):return db.scalar(select(MfaCredential).where(MfaCredential.user_id==user.id,MfaCredential.org_id==user.org_id))
def verify(db,user,value,allow_pending=False):
    row=credential(db,user)
    if not row or (not row.enabled and not allow_pending):return False
    value=str(value or '').strip().replace(' ','');step=int(time.time())//30
    secret=decrypt(row.encrypted_secret)
    for candidate in [step,step-1,step+1]:
        if hmac.compare_digest(value,code(secret,candidate)) and candidate>row.last_step:
            result=db.execute(update(MfaCredential).where(MfaCredential.id==row.id,MfaCredential.last_step<candidate).values(last_step=candidate))
            return result.rowcount==1
    if row.enabled:
        digest=hashlib.sha256(value.encode()).hexdigest()
        result=db.execute(update(RecoveryCode).where(RecoveryCode.user_id==user.id,RecoveryCode.org_id==user.org_id,RecoveryCode.digest==digest,RecoveryCode.used==0).values(used=1))
        return result.rowcount==1
    return False
def reauthenticate(db,user,password,otp=None):
    from app.core.security import hasher
    try:hasher.verify(user.password,str(password))
    except Exception:raise HTTPException(401,'Reauthentication failed')
    row=credential(db,user)
    if row and row.enabled and not verify(db,user,otp):raise HTTPException(401,'A fresh authenticator or recovery code is required')
def revoke_all(db,user):
    db.execute(update(Token).where(Token.user_id==user.id).values(revoked=1))
