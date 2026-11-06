import time
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db.database import get_db
from app.models.entities import EvaluationDataset,EvaluationCase,Evaluation,Finding,Chunk
from app.core.security import current_user,permit,owned,audit,REVIEW_ROLES
from app.api.routes import serialize
from app.services.rag_service import STATUSES
from app.services.hybrid_retrieval_service import search
from app.services.evaluation_service import retrieval_metrics,classification_metrics,evidence_metrics
router=APIRouter(prefix='/api/evaluation')
@router.post('/datasets',status_code=201)
def create(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES)
    if not isinstance(data.get('name'),str) or not 1<=len(data['name'])<=200:raise HTTPException(422,'Dataset name is required')
    row=EvaluationDataset(org_id=user.org_id,name=data['name'],description=str(data.get('description',''))[:10000]);db.add(row);db.flush();audit(db,user,'DATASET_CREATE',row.id);db.commit();return serialize(row)
@router.get('/datasets')
def datasets(user=Depends(current_user),db=Depends(get_db)):
    return [serialize(x) for x in db.scalars(select(EvaluationDataset).where(EvaluationDataset.org_id==user.org_id))]
@router.post('/datasets/{identifier}/cases',status_code=201)
def add_case(identifier:str,data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);owned(db,EvaluationDataset,identifier,user)
    if not isinstance(data.get('query'),str) or not 3<=len(data['query'])<=5000:raise HTTPException(422,'Supply a query of 3–5000 characters')
    relevant=data.get('relevant_chunk_ids',[])
    if not isinstance(relevant,list) or not relevant or len(relevant)>200 or len(relevant)!=len(set(relevant)):raise HTTPException(422,'Supply distinct source chunk IDs')
    for chunk in relevant:owned(db,Chunk,chunk,user)
    if data.get('finding_id'):
        owned(db,Finding,data['finding_id'],user)
        if data.get('expected_classification') not in STATUSES:raise HTTPException(422,'A finding label requires an expected classification')
    for key in ['claim_supported','element_supported']:
        if key in data and (not isinstance(data[key],list) or any(type(x) is not bool for x in data[key])):raise HTTPException(422,'Claim/element annotations must contain boolean judgments')
    if 'citation_complete' in data and type(data['citation_complete']) is not bool:raise HTTPException(422,'citation_complete must be boolean')
    row=EvaluationCase(org_id=user.org_id,dataset_id=identifier,labels=data,author_id=user.id);db.add(row);db.flush();audit(db,user,'ANNOTATION_CREATE',row.id);db.commit();return serialize(row)
@router.get('/datasets/{identifier}/cases')
def cases(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,EvaluationDataset,identifier,user)
    return [serialize(x) for x in db.scalars(select(EvaluationCase).where(EvaluationCase.dataset_id==identifier,EvaluationCase.org_id==user.org_id))]
@router.post('/cases/{identifier}/review')
def review(identifier:str,data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);row=owned(db,EvaluationCase,identifier,user)
    if row.author_id==user.id:raise HTTPException(403,'Gold-standard labels require an independent second reviewer')
    if data.get('decision') not in {'APPROVED','REJECTED'} or len(str(data.get('explanation','')))<5:raise HTTPException(422,'Approve/reject with a review explanation')
    row.status=data['decision'];row.reviewer_id=user.id;audit(db,user,'ANNOTATION_REVIEW',identifier,data);db.commit();return serialize(row)
@router.post('/datasets/{identifier}/run')
def run(identifier:str,data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);owned(db,EvaluationDataset,identifier,user)
    rows=list(db.scalars(select(EvaluationCase).where(EvaluationCase.dataset_id==identifier,EvaluationCase.org_id==user.org_id,EvaluationCase.status=='APPROVED')))
    if not rows:raise HTTPException(422,'Independent approved labels are required')
    if len(rows)>1000:raise HTTPException(422,'Maximum 1000 cases per research execution')
    k=data.get('k',5);modes=data.get('modes',['keyword','dense','hybrid'])
    if type(k) is not int or not 1<=k<=30 or not isinstance(modes,list) or not modes or any(m not in {'keyword','dense','hybrid','reranked'} for m in modes):raise HTTPException(422,'Invalid k or retrieval modes')
    output={'retrieval':{}}
    for mode in modes:
        started=time.perf_counter();results=[]
        try:
            for case in rows:
                ranked=search(db,user.org_id,case.labels['query'],top_k=k,mode=mode)
                results.append(retrieval_metrics([r['chunk_id'] for r in ranked],case.labels['relevant_chunk_ids'],k))
        except Exception as exc:raise HTTPException(422,'Retrieval mode execution failed: '+str(exc))
        output['retrieval'][mode]={name:sum(r[name] for r in results)/len(results) for name in results[0]};output['retrieval'][mode]['average_latency_ms']=(time.perf_counter()-started)*1000/len(results)
    labeled=[r for r in rows if r.labels.get('finding_id')]
    fs=[owned(db,Finding,r.labels['finding_id'],user) for r in labeled]
    output['classification']=classification_metrics([r.labels['expected_classification'] for r in labeled],[f.original['compliance_status'] for f in fs]) if labeled else None
    output['explainability']=evidence_metrics(fs,[r.labels for r in labeled])
    record=Evaluation(org_id=user.org_id,config={'dataset_id':identifier,'case_snapshots':[serialize(r) for r in rows],'k':k,'modes':modes,'classification_target':'original generated finding; human overrides are not predictions'},metrics=output);db.add(record);db.flush();audit(db,user,'RESEARCH_RUN',record.id);db.commit();return serialize(record)
