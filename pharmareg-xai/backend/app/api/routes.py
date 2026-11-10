import hashlib, json, secrets, time
from collections import Counter
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from app.db.database import get_db
from app.models.entities import *
from app.schemas.requests import *
from app.core.security import current_user, permit, owned, audit, hasher, issue, resolve, digest, REVIEW_ROLES, ROLES
from app.core.config import STORAGE, MAX_UPLOAD, LLM_PROVIDER
from app.services.extraction_service import validate_file
from app.services.document_service import process_document
from app.services.hybrid_retrieval_service import search
from app.services.compliance_service import run_assessment
from app.services.risk_service import calculate
from app.services.report_service import generate
from app.services.evaluation_service import retrieval_metrics
from app.services.job_service import dispatch,resume_pending

router=APIRouter(prefix='/api')
def serialize(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in {'password','path','digest'}}
def listing(db,model,user,limit=100,offset=0):
    return [serialize(x) for x in db.scalars(select(model).where(model.org_id==user.org_id).order_by(model.created_at.desc()).limit(min(limit,200)).offset(max(offset,0)))]

@router.post('/auth/register',status_code=201)
def register(data:Register,db=Depends(get_db)):
    org=Organization(name=data.organization);db.add(org);db.flush()
    user=User(org_id=org.id,email=data.email,name=data.name,password=hasher.hash(data.password));db.add(user)
    try: db.flush()
    except IntegrityError: db.rollback();raise HTTPException(409,'Email already registered')
    audit(db,user,'REGISTER',user.id);db.commit()
    return issue(db,user)
@router.post('/auth/login')
def login(data:Login,db=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email.strip().lower()))
    try:
        if not user: raise ValueError()
        hasher.verify(user.password,data.password)
    except Exception: raise HTTPException(401,'Invalid credentials')
    from app.services.mfa_service import credential,verify
    mfa=credential(db,user)
    if mfa and mfa.enabled and not verify(db,user,data.code):raise HTTPException(401,'A fresh authenticator or recovery code is required')
    audit(db,user,'LOGIN',user.id);db.commit();return issue(db,user)
@router.post('/auth/refresh')
def refresh(data:Refresh,db=Depends(get_db)):
    user,record=resolve(db,data.refresh_token,'refresh')
    claimed=db.execute(update(Token).where(Token.id==record.id,Token.revoked==0).values(revoked=1))
    if claimed.rowcount!=1: raise HTTPException(401,'Refresh token already consumed')
    return issue(db,user)
@router.post('/auth/logout')
def logout(user=Depends(current_user),db=Depends(get_db)):
    for token in db.scalars(select(Token).where(Token.user_id==user.id)): token.revoked=1
    audit(db,user,'LOGOUT',user.id);db.commit();return {'ok':True}
@router.get('/auth/me')
def me(user=Depends(current_user)): return serialize(user)
@router.post('/auth/password-reset/request')
def reset_request(data:dict,db=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==str(data.get('email','')).strip().lower()))
    if user:
        value=secrets.token_urlsafe(48)
        db.add(Token(user_id=user.id,digest=digest(value),kind='password-reset',expires=int(time.time())+900))
        # A local outbox supports development without disclosing tokens through the public API.
        # Production requires an operator-provided mailer, not automatic external email delivery.
        import os
        if os.getenv('APP_ENV','development')!='production':
            outbox=STORAGE/'outbox';outbox.mkdir(exist_ok=True)
            (outbox/(uid()+'.json')).write_text(json.dumps({'to':user.email,'token':value,'expires_in_seconds':900}),encoding='utf-8')
        else:
            from app.services.mail_service import deliver_reset
            try:deliver_reset(user.email,value)
            except Exception:
                import logging
                logging.exception('Configured password recovery delivery failed')
                db.rollback()
                return {'message':'If the account exists, a reset request has been recorded. Contact your workspace administrator for delivery.'}
        audit(db,user,'PASSWORD_RESET_REQUEST',user.id);db.commit()
    return {'message':'If the account exists, a reset request has been recorded. Contact your workspace administrator for delivery.'}
@router.post('/auth/password-reset/confirm')
def reset_confirm(data:dict,db=Depends(get_db)):
    password=data.get('password','')
    if not isinstance(password,str) or not 12<=len(password)<=128: raise HTTPException(422,'Password must be 12–128 characters')
    token=db.scalar(select(Token).where(Token.digest==digest(str(data.get('token',''))),Token.kind=='password-reset',Token.revoked==0,Token.expires>int(time.time())))
    if not token: raise HTTPException(400,'Invalid or expired reset token')
    user=db.get(User,token.user_id);user.password=hasher.hash(password)
    for row in db.scalars(select(Token).where(Token.user_id==user.id)): row.revoked=1
    audit(db,user,'PASSWORD_RESET_COMPLETE',user.id);db.commit();return {'ok':True}
@router.patch('/auth/me')
def update_profile(data:dict,user=Depends(current_user),db=Depends(get_db)):
    name=data.get('name','')
    if not isinstance(name,str) or not 1<=len(name)<=200: raise HTTPException(422,'Name must be 1–200 characters')
    user.name=name;audit(db,user,'PROFILE_UPDATE',user.id);db.commit();return serialize(user)
@router.get('/organizations')
def organizations(user=Depends(current_user),db=Depends(get_db)): return [serialize(db.get(Organization,user.org_id))]
@router.get('/organizations/{identifier}')
def organization(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    if identifier!=user.org_id: raise HTTPException(404,'Organization not found')
    return serialize(db.get(Organization,identifier))
@router.patch('/organizations/{identifier}')
def update_organization(identifier:str,data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'})
    if identifier!=user.org_id: raise HTTPException(404,'Organization not found')
    name=data.get('name','').strip()
    if not name or len(name)>200: raise HTTPException(422,'Invalid name')
    org=db.get(Organization,identifier);org.name=name;audit(db,user,'ORGANIZATION_UPDATE',identifier);db.commit();return serialize(org)
@router.get('/users')
def users(user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'});return listing(db,User,user)
@router.post('/users',status_code=201)
def create_member(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'})
    try:
        validated=Register(email=data['email'],password=data['password'],name=data['name'],organization='existing')
    except Exception: raise HTTPException(422,'Provide valid email, name, and a 12–128 character password')
    role=data.get('role','Standard User')
    if role not in ROLES: raise HTTPException(422,'Unknown role')
    member=User(org_id=user.org_id,email=validated.email,password=hasher.hash(validated.password),name=validated.name,role=role);db.add(member)
    try: db.flush()
    except IntegrityError: db.rollback();raise HTTPException(409,'Email is already registered')
    audit(db,user,'MEMBER_CREATE',member.id,{'role':role});db.commit();return serialize(member)
@router.patch('/users/{identifier}')
def update_user(identifier:str,data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'});target=owned(db,User,identifier,user)
    if data.get('role') not in ROLES: raise HTTPException(422,'Unknown role')
    if target.id==user.id: raise HTTPException(409,'Cannot remove your own administrator access')
    target.role=data['role'];audit(db,user,'ROLE_UPDATE',identifier,data);db.commit();return serialize(target)

async def save_upload(file,background,db,user,kind,category,authority,jurisdiction,version,source_url):
    permit(user)
    data=await file.read(MAX_UPLOAD+1)
    name=(file.filename or 'upload').replace('\\','/').split('/')[-1][:250]
    ext=validate_file(name,data)
    identifier=uid();folder=STORAGE/'uploads'/user.org_id;folder.mkdir(parents=True,exist_ok=True)
    path=folder/(identifier+ext);path.write_bytes(data)
    from app.services.file_security_service import scan
    try:scan_status=scan(path)
    except Exception as exc:path.unlink(missing_ok=True);raise HTTPException(422,str(exc))
    from app.services.storage_service import encrypt_file
    from starlette.concurrency import run_in_threadpool
    path=await run_in_threadpool(encrypt_file,path)
    doc=Document(id=identifier,org_id=user.org_id,name=name,kind=kind,category=category,authority=authority,jurisdiction=jurisdiction,version=version,source_url=source_url,checksum=hashlib.sha256(data).hexdigest(),path=str(path))
    doc.metadata_json={'malware_scan':scan_status}
    db.add(doc);db.flush();db.add(DocumentVersion(org_id=user.org_id,document_id=identifier,family_id=identifier))
    audit(db,user,'DOCUMENT_UPLOAD',identifier,{'checksum':doc.checksum});db.commit()
    dispatch(background,db,user.org_id,'document',identifier);return serialize(doc)
@router.post('/documents/upload',status_code=201)
@router.post('/regulations/upload',status_code=201)
async def upload(request:Request,background:BackgroundTasks,file:UploadFile=File(...),kind:str=Form('organizational'),category:str=Form('Other Pharmaceutical Documents'),authority:str=Form('User supplied'),jurisdiction:str=Form('Unspecified'),version:str=Form('1'),source_url:str=Form(''),user=Depends(current_user),db=Depends(get_db)):
    if request.url.path=='/api/regulations/upload': kind='regulatory'
    if kind not in {'regulatory','organizational'}: raise HTTPException(422,'Invalid kind')
    if any(len(v)>250 for v in [category,authority,jurisdiction,version]) or len(source_url)>2000: raise HTTPException(422,'Metadata too long')
    return await save_upload(file,background,db,user,kind,category,authority,jurisdiction,version,source_url)
@router.post('/documents/upload/bulk',status_code=201)
async def bulk(background:BackgroundTasks,files:list[UploadFile]=File(...),user=Depends(current_user),db=Depends(get_db)):
    if len(files)>20: raise HTTPException(422,'Maximum 20 files')
    return [await save_upload(f,background,db,user,'organizational','Other Pharmaceutical Documents','User supplied','Unspecified','1','') for f in files]
@router.get('/documents')
def documents(q:str='',kind:str|None=None,limit:int=100,offset:int=0,user=Depends(current_user),db=Depends(get_db)):
    stmt=select(Document).where(Document.org_id==user.org_id,Document.archived==0)
    if q: stmt=stmt.where(Document.name.ilike('%'+q+'%'))
    if kind: stmt=stmt.where(Document.kind==kind)
    return [serialize(d) for d in db.scalars(stmt.order_by(Document.created_at.desc()).limit(max(1,min(limit,200))).offset(max(0,offset)))]
@router.get('/regulations')
def regulations(user=Depends(current_user),db=Depends(get_db)): return documents(kind='regulatory',user=user,db=db)
@router.get('/documents/{identifier}')
@router.get('/regulations/{identifier}')
@router.get('/documents/{identifier}/status')
def document(identifier:str,background:BackgroundTasks,user=Depends(current_user),db=Depends(get_db)):
    doc=owned(db,Document,identifier,user)
    resume_pending(background,db,user.org_id,identifier)
    return {**serialize(doc),'chunks':[serialize(c) for c in db.scalars(select(Chunk).where(Chunk.document_id==doc.id))]}
@router.get('/documents/{identifier}/preview')
def preview(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    doc=owned(db,Document,identifier,user);audit(db,user,'DOCUMENT_DOWNLOAD',identifier);db.commit()
    from app.services.storage_service import download
    return download(doc.path,doc.name)
@router.delete('/documents/{identifier}')
def archive(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    permit(user);doc=owned(db,Document,identifier,user);doc.archived=1;audit(db,user,'DOCUMENT_ARCHIVE',identifier);db.commit();return {'archived':True}
@router.post('/documents/{identifier}/process')
def reprocess(identifier:str,background:BackgroundTasks,user=Depends(current_user),db=Depends(get_db)):
    permit(user);doc=owned(db,Document,identifier,user)
    if doc.status!='Failed': raise HTTPException(409,'Only failed uploads may be retried; indexed versions are immutable')
    doc.status='Queued';db.commit();dispatch(background,db,user.org_id,'document',identifier);return {'status':'Queued'}
@router.post('/regulations/{identifier}/applicability')
def applicability(identifier:str,data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);doc=owned(db,Document,identifier,user)
    if doc.kind!='regulatory' or data.get('status') not in {'CURRENT_APPROVED','SUPERSEDED','HISTORICAL','DRAFT','UNVERIFIED'} or len(data.get('explanation',''))<5: raise HTTPException(422,'Status and review rationale required')
    doc.regulatory_status=data['status'];db.add(Review(org_id=user.org_id,target_id=identifier,reviewer_id=user.id,decision=data['status'],explanation=data['explanation'],snapshot=serialize(doc)));audit(db,user,'APPLICABILITY_REVIEW',identifier,data);db.commit();return serialize(doc)
@router.get('/regulations/{identifier}/requirements')
def requirements(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,Document,identifier,user)
    rows=list(db.scalars(select(Requirement).where(Requirement.document_id==identifier)));latest={}
    for version in db.scalars(select(RequirementVersion).where(RequirementVersion.org_id==user.org_id,RequirementVersion.requirement_id.in_([r.id for r in rows])).order_by(RequirementVersion.created_at.desc(),RequirementVersion.id.desc())):latest.setdefault(version.requirement_id,version)
    return [{**serialize(r),'material_elements':latest[r.id].snapshot.get('material_elements',[r.statement]) if r.id in latest else [r.statement],'review_version_id':latest[r.id].id if r.id in latest else None} for r in rows]
@router.post('/regulations/{identifier}/extract-requirements')
def extract_requirements(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);doc=owned(db,Document,identifier,user)
    if doc.status!='Indexed': raise HTTPException(409,'Document must be indexed first')
    return requirements(identifier,user,db)
@router.post('/regulations/requirements/{identifier}/review')
def requirement_review(identifier:str,data:Decision,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);req=owned(db,Requirement,identifier,user)
    if data.decision not in {'APPROVED','REJECTED'}: raise HTTPException(422,'Approve or reject requirement')
    db.add(Review(org_id=user.org_id,target_id=req.id,reviewer_id=user.id,decision=data.decision,explanation=data.explanation,snapshot=serialize(req)))
    req.status=data.decision;req.statement=data.statement or req.statement;req.designation=data.designation;req.applicability=data.applicability
    if any(not e.strip() or len(e)>5000 for e in data.material_elements):raise HTTPException(422,'Material elements must contain nonempty text, at most 5000 characters each')
    db.add(RequirementVersion(org_id=user.org_id,requirement_id=req.id,reviewer_id=user.id,snapshot={'statement':req.statement,'status':req.status,'designation':req.designation,'applicability':req.applicability,'material_elements':data.material_elements or [req.statement]}))
    audit(db,user,'REQUIREMENT_REVIEW',identifier,data.model_dump());db.commit();return serialize(req)
@router.post('/retrieval/search')
def retrieval(data:Search,user=Depends(current_user),db=Depends(get_db)):
    return search(db,user.org_id,**data.model_dump(exclude={'document_ids'}),document_ids=data.document_ids)

def requirement_snapshot(db,identifiers):
    snapshots={}
    for identifier in identifiers:
        req=db.get(Requirement,identifier)
        latest=db.scalar(select(RequirementVersion).where(RequirementVersion.requirement_id==identifier).order_by(RequirementVersion.created_at.desc()).limit(1))
        snapshots[identifier]={'statement':req.statement,'material_elements':latest.snapshot.get('material_elements',[req.statement]) if latest else [req.statement],'review_version_id':latest.id if latest else None,'applicability':req.applicability,'designation':req.designation,'source_chunk_id':req.chunk_id}
    return snapshots

@router.post('/compliance/assessments',status_code=201)
def create_assessment(data:AssessmentInput,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES)
    if len(set(data.requirement_ids))!=len(data.requirement_ids): raise HTTPException(422,'Duplicate requirement selection')
    for identifier in data.regulatory_document_ids:
        doc=owned(db,Document,identifier,user)
        if doc.kind!='regulatory' or doc.regulatory_status!='CURRENT_APPROVED' or doc.status!='Indexed' or doc.archived or doc.jurisdiction!=data.jurisdiction: raise HTTPException(422,'Select indexed, current expert-approved regulations in the chosen jurisdiction')
    for identifier in data.organizational_document_ids:
        doc=owned(db,Document,identifier,user)
        if doc.kind!='organizational' or doc.status!='Indexed' or doc.archived: raise HTTPException(422,'Select indexed organizational documents')
    for identifier in [*data.requirement_ids,*data.excluded_requirements]:
        req=owned(db,Requirement,identifier,user)
        if req.status!='APPROVED' or req.document_id not in data.regulatory_document_ids: raise HTTPException(422,'Requirements must be approved and belong to selected regulations')
    import os
    row=Assessment(org_id=user.org_id,name=data.name,config={**data.model_dump(),'provider':LLM_PROVIDER,'model':os.getenv('LLM_MODEL',''),'embedding_provider':os.getenv('EMBEDDING_PROVIDER','hash-local'),'embedding_model':os.getenv('EMBEDDING_MODEL','sha256-feature-hash-v1'),'requirement_snapshots':requirement_snapshot(db,[*data.requirement_ids,*data.excluded_requirements]),'applicability_review':{'reviewer_id':user.id,'reviewed_at':now()},'retrieval':{'mode':'hybrid','top_k':6}});db.add(row);db.flush()
    from app.services.assessment_config_service import sync_links
    sync_links(db,row);audit(db,user,'ASSESSMENT_CREATE',row.id);db.commit();return serialize(row)
@router.get('/compliance/assessments')
def assessments(user=Depends(current_user),db=Depends(get_db)): return listing(db,Assessment,user)
@router.get('/compliance/assessments/{identifier}')
def assessment(identifier:str,background:BackgroundTasks,user=Depends(current_user),db=Depends(get_db)):
    row=owned(db,Assessment,identifier,user);resume_pending(background,db,user.org_id,identifier);return serialize(row)
@router.post('/compliance/assessments/{identifier}/run')
def run(identifier:str,background:BackgroundTasks,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);row=owned(db,Assessment,identifier,user)
    if row.status not in {'DRAFT','FAILED'}: raise HTTPException(409,'Assessment already running or completed')
    from app.services.compliance_service import check_revisions
    try:check_revisions(db,row)
    except ValueError as exc:raise HTTPException(409,str(exc))
    claimed=db.execute(update(Assessment).where(Assessment.id==identifier,Assessment.org_id==user.org_id,Assessment.status.in_(['DRAFT','FAILED'])).values(status='RUNNING',error=''))
    if claimed.rowcount!=1: raise HTTPException(409,'Assessment already claimed by another request')
    db.refresh(row);audit(db,user,'ASSESSMENT_RUN',identifier);db.commit();dispatch(background,db,user.org_id,'assessment',identifier);return serialize(row)
@router.get('/compliance/assessments/{identifier}/findings')
def findings(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,Assessment,identifier,user);return [serialize(f) for f in db.scalars(select(Finding).where(Finding.assessment_id==identifier))]
@router.get('/compliance/findings/{identifier}')
@router.get('/explainability/findings/{identifier}')
def finding(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    row=owned(db,Finding,identifier,user);return {**serialize(row),'reviews':[serialize(r) for r in db.scalars(select(Review).where(Review.target_id==identifier,Review.org_id==user.org_id))]}
@router.get('/explainability/evidence/{identifier}')
def evidence(identifier:str,user=Depends(current_user),db=Depends(get_db)): return serialize(owned(db,Chunk,identifier,user))
@router.post('/compliance/findings/{identifier}/review')
def finding_review(identifier:str,data:Decision,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);row=owned(db,Finding,identifier,user)
    db.add(Review(org_id=user.org_id,target_id=identifier,reviewer_id=user.id,decision=data.decision,explanation=data.explanation,snapshot=serialize(row)))
    row.review_status=data.decision;row.reviewed_classification=data.classification
    audit(db,user,'FINDING_REVIEW',identifier,data.model_dump());db.commit();return serialize(row)
@router.get('/risk/findings')
def risk_findings(user=Depends(current_user),db=Depends(get_db)): return listing(db,Finding,user)
@router.post('/risk/assess')
def risk(data:RiskInput,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);row=owned(db,Finding,data.finding_id,user)
    setting=db.scalar(select(Setting).where(Setting.org_id==user.org_id,Setting.key=='risk_thresholds'))
    result={**calculate(data.severity,data.likelihood,data.detectability,setting.value if setting else None),'explanation':data.explanation,'reviewer':user.id,'review_date':now()}
    db.add(RiskAssessment(org_id=user.org_id,finding_id=row.id,reviewer_id=user.id,factors=result,explanation=data.explanation))
    db.add(Review(org_id=user.org_id,target_id=row.id,reviewer_id=user.id,decision='RISK_ASSESSED',explanation=data.explanation,snapshot=result));audit(db,user,'RISK_ASSESSED',row.id,result);db.commit();return result
@router.get('/risk/summary')
def risk_summary(user=Depends(current_user),db=Depends(get_db)):
    rows=db.scalars(select(Review).where(Review.org_id==user.org_id,Review.decision=='RISK_ASSESSED').order_by(Review.created_at))
    latest={r.target_id:r.snapshot for r in rows};return dict(Counter(r['level'] for r in latest.values()))
@router.post('/capa',status_code=201)
def create_capa(data:CapaInput,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);owned(db,Finding,data.finding_id,user)
    try: __import__('datetime').date.fromisoformat(data.due_date)
    except ValueError: raise HTTPException(422,'Use ISO due date')
    row=Capa(org_id=user.org_id,finding_id=data.finding_id,title=data.title,data={**data.model_dump(),'created_by':user.id});db.add(row);db.flush();db.add(CapaEvent(org_id=user.org_id,capa_id=row.id,actor_id=user.id,snapshot={'status':'OPEN','data':row.data}));audit(db,user,'CAPA_CREATE',row.id);db.commit();return serialize(row)
@router.get('/capa')
def capas(user=Depends(current_user),db=Depends(get_db)): return listing(db,Capa,user)
@router.get('/capa/{identifier}')
def capa(identifier:str,user=Depends(current_user),db=Depends(get_db)): return serialize(owned(db,Capa,identifier,user))
@router.patch('/capa/{identifier}')
@router.post('/capa/{identifier}/close')
def update_capa(identifier:str,data:CapaUpdate,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);row=owned(db,Capa,identifier,user)
    allowed={'OPEN':{'IN_PROGRESS'},'IN_PROGRESS':{'VERIFICATION'},'VERIFICATION':{'IN_PROGRESS','CLOSED'},'CLOSED':set()}
    if data.status not in allowed[row.status]: raise HTTPException(409,'Invalid CAPA transition')
    if data.status=='CLOSED' and (not data.implementation_evidence or not data.effectiveness_review): raise HTTPException(422,'Closure requires implementation evidence and effectiveness review')
    if data.status=='CLOSED' and row.data.get('verification_submitted_by')==user.id:raise HTTPException(403,'An independent reviewer must approve CAPA closure')
    if data.status=='VERIFICATION':row.data={**row.data,'verification_submitted_by':user.id}
    db.add(CapaEvent(org_id=user.org_id,capa_id=row.id,actor_id=user.id,snapshot={'before':serialize(row),'after':data.model_dump()}))
    row.status=data.status;row.data={**row.data,**data.model_dump(),'updated_by':user.id};audit(db,user,'CAPA_UPDATE',identifier,data.model_dump());db.commit();return serialize(row)

@router.post('/chat')
@router.post('/rag/query')
def chat(data:Search,user=Depends(current_user),db=Depends(get_db)):
    refs=search(db,user.org_id,data.query,document_ids=data.document_ids,top_k=data.top_k)
    answer={'question':data.query,'answer':'Retrieved source excerpts are shown below. No generated legal or compliance conclusion is established in extractive chat mode.' if refs else 'Insufficient evidence: no matching indexed source passages.','regulatory_references':[r for r in refs if owned(db,Document,r['document_id'],user).kind=='regulatory'],'organizational_evidence':[r for r in refs if owned(db,Document,r['document_id'],user).kind=='organizational'],'evidence_sufficiency':'UNVERIFIED','limitations':['Retrieval relevance does not establish applicability or compliance.'],'provider':'local-extractive'}
    row=Chat(org_id=user.org_id,user_id=user.id,question=data.query,response=answer);db.add(row);db.commit();return answer
@router.get('/chat/sessions')
@router.get('/rag/history')
def history(user=Depends(current_user),db=Depends(get_db)): return listing(db,Chat,user)
@router.get('/chat/sessions/{identifier}')
def chat_session(identifier:str,user=Depends(current_user),db=Depends(get_db)): return serialize(owned(db,Chat,identifier,user))
@router.post('/reports/generate',status_code=201)
def report_create(data:ReportInput,user=Depends(current_user),db=Depends(get_db)):
    assessment=owned(db,Assessment,data.assessment_id,user)
    if assessment.status!='COMPLETED': raise HTTPException(409,'Assessment must complete first')
    rows=list(db.scalars(select(Finding).where(Finding.assessment_id==assessment.id)))
    ids=[f.id for f in rows]
    snapshot={'assessment':serialize(assessment),'organization':serialize(db.get(Organization,user.org_id)),'documents':[serialize(owned(db,Document,i,user)) for i in assessment.config['regulatory_document_ids']+assessment.config['organizational_document_ids']],'findings':[serialize(f) for f in rows],'reviews':[serialize(r) for r in db.scalars(select(Review).where(Review.org_id==user.org_id,Review.target_id.in_(ids)))],'capas':[serialize(c) for c in db.scalars(select(Capa).where(Capa.org_id==user.org_id,Capa.finding_id.in_(ids)))]}
    snapshot['risk_assessments']=[serialize(r) for r in db.scalars(select(RiskAssessment).where(RiskAssessment.org_id==user.org_id,RiskAssessment.finding_id.in_(ids)).order_by(RiskAssessment.created_at))]
    capa_ids=[c['id'] for c in snapshot['capas']]
    snapshot['capa_attachments']=[serialize(a) for a in db.scalars(select(CapaAttachment).where(CapaAttachment.org_id==user.org_id,CapaAttachment.capa_id.in_(capa_ids)))]
    report=Report(org_id=user.org_id,assessment_id=assessment.id,format=data.format,snapshot=snapshot);db.add(report);db.flush();generate(report);audit(db,user,'REPORT_GENERATE',report.id);db.commit();return serialize(report)
@router.get('/reports')
def reports(user=Depends(current_user),db=Depends(get_db)): return listing(db,Report,user)
@router.get('/reports/{identifier}')
def report(identifier:str,user=Depends(current_user),db=Depends(get_db)): return serialize(owned(db,Report,identifier,user))
@router.get('/reports/{identifier}/download')
def download(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    row=owned(db,Report,identifier,user);audit(db,user,'REPORT_DOWNLOAD',identifier);db.commit()
    from app.services.storage_service import download
    return download(row.path,'PharmaReg-'+row.id+'.'+row.format)
@router.post('/evaluation/run')
def evaluate(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES)
    cases=data.get('cases',[]);k=data.get('k',5)
    if not cases or len(cases)>100 or not isinstance(k,int) or not 1<=k<=30: raise HTTPException(422,'Supply 1–100 labeled cases and k 1–30')
    if any(not case.get('relevant_chunk_ids') for case in cases): raise HTTPException(422,'Every evaluation case requires nonempty human-labeled relevant chunk IDs')
    output={}
    for mode in ['keyword','dense','hybrid']:
        metrics=[];start=time.perf_counter()
        for case in cases:
            if not isinstance(case.get('query'),str) or not isinstance(case.get('relevant_chunk_ids'),list): raise HTTPException(422,'Case requires query and relevant_chunk_ids')
            for identifier in case['relevant_chunk_ids']: owned(db,Chunk,identifier,user)
            result=search(db,user.org_id,case['query'],top_k=k,mode=mode)
            metrics.append(retrieval_metrics([r['chunk_id'] for r in result],case['relevant_chunk_ids'],k))
        output[mode]={key:sum(m[key] for m in metrics)/len(metrics) for key in metrics[0]}
        output[mode]['average_latency_ms']=(time.perf_counter()-start)*1000/len(cases)
    row=Evaluation(org_id=user.org_id,config=data,metrics=output);db.add(row);db.commit();return serialize(row)
@router.get('/evaluation/runs')
def evaluations(user=Depends(current_user),db=Depends(get_db)): return listing(db,Evaluation,user)
@router.get('/evaluation/runs/{identifier}')
def evaluation(identifier:str,user=Depends(current_user),db=Depends(get_db)): return serialize(owned(db,Evaluation,identifier,user))
@router.get('/audit-logs')
def logs(limit:int=100,offset:int=0,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);return listing(db,Audit,user,limit,offset)
@router.get('/settings')
def settings(user=Depends(current_user)):
    from app.core.config import ALLOW_EXTERNAL_LLM
    return {'llm_provider':LLM_PROVIDER,'external_llm_authorized':ALLOW_EXTERNAL_LLM,'embedding_provider':__import__('os').getenv('EMBEDDING_PROVIDER','hash-local'),'max_upload_mb':MAX_UPLOAD//1024//1024,'human_review_required':True}
@router.get('/settings/risk-matrix')
def risk_matrix(user=Depends(current_user),db=Depends(get_db)):
    row=db.scalar(select(Setting).where(Setting.org_id==user.org_id,Setting.key=='risk_thresholds'))
    return row.value if row else {'critical':80,'high':40,'medium':15}
@router.patch('/settings/risk-matrix')
def update_matrix(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'})
    if set(data)!={'critical','high','medium'} or not all(type(v) is int for v in data.values()) or not 1<=data['medium']<data['high']<data['critical']<=125: raise HTTPException(422,'Require integer thresholds: 1 ≤ medium < high < critical ≤ 125')
    row=db.scalar(select(Setting).where(Setting.org_id==user.org_id,Setting.key=='risk_thresholds'))
    if row: row.value=data
    else: db.add(Setting(org_id=user.org_id,key='risk_thresholds',value=data))
    audit(db,user,'RISK_MATRIX_UPDATE',user.org_id,data);db.commit();return data
@router.get('/dashboard/summary')
def dashboard(user=Depends(current_user),db=Depends(get_db)):
    def count(model): return db.scalar(select(func.count()).select_from(model).where(model.org_id==user.org_id))
    fs=list(db.scalars(select(Finding).where(Finding.org_id==user.org_id)))
    return {'documents':count(Document),'assessments':count(Assessment),'requirements':count(Requirement),'findings':len(fs),'pending_reviews':sum(f.review_status=='PENDING' for f in fs),'open_capas':db.scalar(select(func.count()).select_from(Capa).where(Capa.org_id==user.org_id,Capa.status!='CLOSED')),'compliance_distribution':dict(Counter(f.reviewed_classification or f.original['compliance_status'] for f in fs)),'risk_distribution':risk_summary(user,db),'provider':LLM_PROVIDER}
@router.get('/dashboard/compliance')
def distribution(user=Depends(current_user),db=Depends(get_db)): return dashboard(user,db)['compliance_distribution']
@router.get('/dashboard/risks')
def risks(user=Depends(current_user),db=Depends(get_db)): return risk_summary(user,db)
@router.get('/dashboard/activity')
def activity(user=Depends(current_user),db=Depends(get_db)): return listing(db,Audit,user,20)
