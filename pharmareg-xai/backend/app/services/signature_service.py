import hashlib,hmac,json,os
from sqlalchemy import select
from fastapi import HTTPException
from app.models.entities import Finding,Capa,Report,Review,RecordSignature,now,uid
from app.core.security import owned
from app.core.config import SECRET_KEY
MODELS={'finding':Finding,'capa':Capa,'report':Report}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def record(db,target_type,identifier,user):
    if target_type not in MODELS:raise HTTPException(422,'Signature target must be finding, capa or report')
    row=owned(db,MODELS[target_type],identifier,user)
    from app.api.routes import serialize
    if target_type=='finding':
        reviews=[serialize(r) for r in db.scalars(select(Review).where(Review.org_id==user.org_id,Review.target_id==identifier).order_by(Review.created_at,Review.id))]
        value={'record':serialize(row),'reviews':reviews}
    else:value=serialize(row)
    return hashlib.sha256(canonical(value).encode()).hexdigest()
def seal(row):
    value={k:getattr(row,k) for k in ['id','org_id','target_type','target_id','signer_id','meaning','statement','record_hash','signer_snapshot','created_at']}
    return hmac.new((os.getenv('SIGNATURE_HMAC_KEY') or SECRET_KEY).encode(),canonical(value).encode(),hashlib.sha256).hexdigest()
