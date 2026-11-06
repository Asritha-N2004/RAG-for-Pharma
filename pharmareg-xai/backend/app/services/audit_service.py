"""HMAC chained audit seals detect changed/deleted/reordered sealed records.

The last hash must be exported to independent storage to detect deletion of a trailing
suffix by an attacker who controls the entire database. HMAC key is never stored in DB.
"""
import hmac,hashlib,json,os
from sqlalchemy import select
from app.models.entities import Audit,AuditSeal,Organization
from app.core.config import SECRET_KEY
def canonical(row):
    return json.dumps({k:getattr(row,k) for k in ['id','org_id','actor_id','action','target_id','details','created_at']},sort_keys=True,separators=(',',':'))
def signature(previous,row):return hmac.new((os.getenv('AUDIT_HMAC_KEY') or SECRET_KEY).encode(),(previous+canonical(row)).encode(),hashlib.sha256).hexdigest()
def append(db,user,action,target,details):
    # Serialize this organization's chain without upgrading FK KEY SHARE locks.
    # FOR UPDATE deadlocks when concurrent transactions already inserted child rows.
    db.scalar(select(Organization).where(Organization.id==user.org_id).with_for_update(key_share=True))
    row=Audit(org_id=user.org_id,actor_id=user.id,action=action,target_id=target,details=details or {});db.add(row);db.flush()
    last=db.scalar(select(AuditSeal).where(AuditSeal.org_id==user.org_id).order_by(AuditSeal.created_at.desc(),AuditSeal.id.desc()).limit(1))
    previous=last.hash if last else '0'*64
    db.add(AuditSeal(org_id=user.org_id,audit_id=row.id,previous_hash=previous,hash=signature(previous,row)));db.flush()
def verify(db,org_id):
    seals=list(db.scalars(select(AuditSeal).where(AuditSeal.org_id==org_id).order_by(AuditSeal.created_at,AuditSeal.id)))
    previous='0'*64;errors=[]
    for seal in seals:
        row=db.get(Audit,seal.audit_id)
        if not row or seal.previous_hash!=previous or not hmac.compare_digest(seal.hash,signature(seal.previous_hash,row)):errors.append(seal.audit_id)
        previous=seal.hash
    sealed={s.audit_id for s in seals};unsealed=[x for x in db.scalars(select(Audit.id).where(Audit.org_id==org_id)) if x not in sealed]
    return {'valid':not errors,'sealed_records':len(seals),'invalid_records':errors,'legacy_unsealed_records':len(unsealed),'checkpoint':previous,'limitation':'Export checkpoint to independent storage to detect complete trailing-suffix deletion; database administrators can otherwise delete trailing records and seals together.'}
