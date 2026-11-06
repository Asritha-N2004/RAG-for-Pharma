from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db.database import get_db
from app.models.entities import ValidationRecord
from app.core.security import current_user,permit,audit,REVIEW_ROLES
from app.api.routes import serialize
router=APIRouter(prefix='/api/validation')
@router.get('')
def records(user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES)
    return [serialize(r) for r in db.scalars(select(ValidationRecord).where(ValidationRecord.org_id==user.org_id).order_by(ValidationRecord.created_at.desc()))]
@router.post('',status_code=201)
def decision(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES)
    if data.get('area') not in {'FUNCTIONAL','DEPLOYMENT','SECURITY','ACCESSIBILITY','DOMAIN_EVALUATION','ELECTRONIC_RECORDS','BACKUP_RESTORE'} or data.get('status') not in {'PENDING','IN_REVIEW','VERIFIED','FAILED'}:raise HTTPException(422,'Recognized validation area and status required')
    evidence=data.get('evidence',{})
    if not isinstance(data.get('statement'),str) or not 20<=len(data['statement'])<=10000 or not isinstance(evidence,dict) or not all(isinstance(evidence.get(k),str) and 3<=len(evidence[k])<=2000 for k in ['reference','reviewer_qualification']):raise HTTPException(422,'A review statement, evidence reference and reviewer qualification must be recorded')
    row=ValidationRecord(org_id=user.org_id,area=data['area'],status=data['status'],reviewer_id=user.id,statement=data['statement'],evidence=evidence);db.add(row);db.flush();audit(db,user,'VALIDATION_DECISION',row.id,{'area':row.area,'status':row.status});db.commit();return serialize(row)
