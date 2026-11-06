import hmac
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db.database import get_db
from app.models.entities import RecordSignature,uid,now
from app.core.security import current_user,permit,audit,REVIEW_ROLES
from app.api.routes import serialize
from app.services.mfa_service import reauthenticate
from app.services.signature_service import record,seal
router=APIRouter(prefix='/api/signatures')
@router.post('',status_code=201)
def sign(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES)
    if data.get('meaning') not in {'REVIEWED','APPROVED','AUTHORSHIP'} or not isinstance(data.get('statement'),str) or not 10<=len(data['statement'])<=5000:raise HTTPException(422,'Explicit signature meaning and 10–5000 character attestation are required')
    if data.get('consent') is not True:raise HTTPException(422,'Explicit attestation consent is required')
    reauthenticate(db,user,data.get('password'),data.get('code'))
    target_type=str(data.get('target_type',''));identifier=str(data.get('target_id',''));fingerprint=record(db,target_type,identifier,user)
    row=RecordSignature(id=uid(),org_id=user.org_id,target_type=target_type,target_id=identifier,signer_id=user.id,meaning=data['meaning'],statement=data['statement'],record_hash=fingerprint,created_at=now(),signer_snapshot={'name':user.name,'email':user.email,'role':user.role});row.seal=seal(row);db.add(row);db.flush();audit(db,user,'RECORD_ATTESTATION',row.id,{'target_id':identifier,'meaning':row.meaning,'record_hash':fingerprint});db.commit();return serialize(row)
@router.get('/{target_type}/{identifier}')
def signatures(target_type:str,identifier:str,user=Depends(current_user),db=Depends(get_db)):
    current=record(db,target_type,identifier,user)
    return [{**serialize(r),'seal_valid':hmac.compare_digest(r.seal,seal(r)),'record_unchanged':r.record_hash==current} for r in db.scalars(select(RecordSignature).where(RecordSignature.org_id==user.org_id,RecordSignature.target_type==target_type,RecordSignature.target_id==identifier).order_by(RecordSignature.created_at))]
