"""Workflow APIs separated from legacy CRUD routes."""
import io,hashlib,json,time
from datetime import date
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,BackgroundTasks,Query
from fastapi.responses import Response,FileResponse
from sqlalchemy import select,func,or_,and_
from app.db.database import get_db
from app.models.entities import *
from app.schemas.requests import AssessmentInput,Search
from app.core.security import current_user,permit,owned,audit,REVIEW_ROLES
from app.core.config import STORAGE,MAX_UPLOAD
from app.api.routes import serialize,save_upload,requirement_snapshot
from app.services.job_service import dispatch

router=APIRouter(prefix='/api')
@router.get('/records/{collection}')
def paginated(collection:str,q:str='',status:str|None=None,kind:str|None=None,category:str|None=None,authority:str|None=None,jurisdiction:str|None=None,department:str|None=None,risk:str|None=None,since:str|None=None,until:str|None=None,group_by:str|None=None,regulatory_status:str|None=None,limit:int=Query(25,ge=1,le=200),offset:int=Query(0,ge=0),user=Depends(current_user),db=Depends(get_db)):
    models={'documents':Document,'assessments':Assessment,'findings':Finding,'capa':Capa,'reports':Report,'evaluations':Evaluation,'audit':Audit,'jobs':ProcessingJob,'requirements':Requirement,'users':User}
    if collection not in models:raise HTTPException(404,'Collection not found')
    if collection=='audit':permit(user,REVIEW_ROLES)
    if collection=='users':permit(user,{'System Administrator'})
    model=models[collection];conditions=[model.org_id==user.org_id]
    if model is Document:conditions.append(Document.archived==0)
    if regulatory_status and model is Document:conditions.append(Document.regulatory_status==regulatory_status)
    if q:
        name=getattr(model,'name',None)
        if name is None:name=getattr(model,'title',None)
        if model is Finding:name=Finding.original['requirement_text'].as_string()
        if model is Requirement:name=Requirement.statement
        if model is Audit:name=Audit.action
        if name is not None:conditions.append(or_(name.ilike('%'+q+'%'),User.email.ilike('%'+q+'%')) if model is User else name.ilike('%'+q+'%'))
    if status:
        column=func.coalesce(Finding.reviewed_classification,Finding.original['compliance_status'].as_string()) if model is Finding else getattr(model,'status',None)
        if column is None:column=getattr(model,'state',None)
        if column is not None:conditions.append(column==status)
    for name,value in [('since',since),('until',until)]:
        if value:
            try:date.fromisoformat(value)
            except ValueError:raise HTTPException(422,'Date filters require YYYY-MM-DD')
            conditions.append(model.created_at>=value if name=='since' else model.created_at<=value+'T23:59:59.999999+00:00')
    source_conditions=[Document.org_id==user.org_id]
    for column,value in [(Document.kind,kind),(Document.category,category),(Document.authority,authority),(Document.jurisdiction,jurisdiction)]:
        if value:source_conditions.append(column==value)
    if department:source_conditions.append(func.coalesce(Document.metadata_json['department'].as_string(),'Unassigned')==department)
    if any([kind,category,authority,jurisdiction,department]):
        ids=select(Document.id).where(*source_conditions)
        if model is Document:conditions.extend(source_conditions)
        elif model is Requirement:conditions.append(Requirement.document_id.in_(ids))
        elif model is Assessment:conditions.append(Assessment.id.in_(select(AssessmentDocument.assessment_id).where(AssessmentDocument.org_id==user.org_id,AssessmentDocument.document_id.in_(ids))))
        elif model in {Finding,Capa}:
            finding_ids=select(EvidenceMapping.finding_id).where(EvidenceMapping.org_id==user.org_id,EvidenceMapping.document_id.in_(ids))
            conditions.append(Finding.id.in_(finding_ids) if model is Finding else Capa.finding_id.in_(finding_ids))
    latest=None
    if model in {Finding,Capa}:
        target=Finding.id if model is Finding else Capa.finding_id
        latest=select(RiskAssessment.factors['level'].as_string()).where(RiskAssessment.org_id==user.org_id,RiskAssessment.finding_id==target).order_by(RiskAssessment.created_at.desc(),RiskAssessment.id.desc()).limit(1).correlate(model).scalar_subquery()
        if risk:conditions.append(func.coalesce(latest,'UNASSESSED')==risk)
    count=db.scalar(select(func.count()).select_from(model).where(*conditions))
    items=list(db.scalars(select(model).where(*conditions).order_by(model.created_at.desc(),model.id).limit(limit).offset(offset)))
    serialized=[serialize(x) for x in items];groups={}
    if model is Finding:
        risk_rows=db.scalars(select(RiskAssessment).where(RiskAssessment.org_id==user.org_id,RiskAssessment.finding_id.in_([x.id for x in items])).order_by(RiskAssessment.created_at.desc(),RiskAssessment.id.desc()))
        risks={}
        for row in risk_rows:risks.setdefault(row.finding_id,row.factors)
        departments={};categories={};documents={}
        for fid,meta,category_name,document_id in db.execute(select(EvidenceMapping.finding_id,Document.metadata_json,Document.category,Document.id).join(Document,Document.id==EvidenceMapping.document_id).where(EvidenceMapping.org_id==user.org_id,EvidenceMapping.finding_id.in_([x.id for x in items]),EvidenceMapping.role=='ORGANIZATIONAL_CANDIDATE')):
            departments.setdefault(fid,set()).add(meta.get('department','Unassigned'));categories.setdefault(fid,set()).add(category_name);documents.setdefault(fid,set()).add(document_id)
        for item in serialized:
            item['latest_risk']=risks.get(item['id']);item['departments']=sorted(departments.get(item['id'],{'Unassigned'}));item['categories']=sorted(categories.get(item['id'],{'Unassigned'}));item['source_document_ids']=sorted(documents.get(item['id'],{'Unassigned'}))
        if group_by:
            if group_by not in {'risk','department','status','review','category','document','requirement'}:raise HTTPException(422,'Unsupported grouping')
            statement=select(Finding.id)
            if group_by in {'department','category','document'}:
                expression=func.coalesce(Document.metadata_json['department'].as_string(),'Unassigned') if group_by=='department' else func.coalesce(Document.category,'Unassigned') if group_by=='category' else func.coalesce(Document.id,'Unassigned')
                statement=select(Finding.id.label('finding_id'),expression.label('group_key')).outerjoin(EvidenceMapping,and_(EvidenceMapping.finding_id==Finding.id,EvidenceMapping.org_id==user.org_id,EvidenceMapping.role=='ORGANIZATIONAL_CANDIDATE')).outerjoin(Document,and_(Document.id==EvidenceMapping.document_id,Document.org_id==user.org_id)).where(*conditions).distinct()
            else:
                expression=func.coalesce(latest,'UNASSESSED') if group_by=='risk' else func.coalesce(Finding.reviewed_classification,Finding.original['compliance_status'].as_string()) if group_by=='status' else Finding.review_status if group_by=='review' else Finding.requirement_id
                statement=select(Finding.id.label('finding_id'),expression.label('group_key')).where(*conditions)
            grouped=statement.subquery();groups=dict(db.execute(select(grouped.c.group_key,func.count()).group_by(grouped.c.group_key)).all())
    return {'items':serialized,'total':count,'limit':limit,'offset':offset,'groups':groups,'group_note':'Group totals cover the entire filtered result. A finding linked to multiple departments/documents can appear in multiple source groups.'}
@router.get('/documents/{identifier}/summary')
def document_summary(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    return serialize(owned(db,Document,identifier,user))
@router.get('/audit-logs/verify')
def audit_integrity(user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES)
    from app.services.audit_service import verify
    return verify(db,user.org_id)
@router.get('/jobs')
def jobs(target_id:str|None=None,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),user=Depends(current_user),db=Depends(get_db)):
    query=select(ProcessingJob).where(ProcessingJob.org_id==user.org_id)
    if target_id:query=query.where(ProcessingJob.target_id==target_id)
    return [serialize(x) for x in db.scalars(query.order_by(ProcessingJob.created_at.desc()).limit(limit).offset(offset))]
@router.post('/jobs/{identifier}/retry')
def retry_job(identifier:str,background:BackgroundTasks,user=Depends(current_user),db=Depends(get_db)):
    permit(user);job=owned(db,ProcessingJob,identifier,user)
    if job.task=='assessment':permit(user,REVIEW_ROLES)
    if job.state not in {'FAILED','RETRY'}:raise HTTPException(409,'Job must be failed or awaiting retry')
    job.state='QUEUED';job.available_at=0;job.attempts=0;audit(db,user,'JOB_RETRY',identifier);db.commit()
    from app.services.job_service import notify,execute
    notify()
    import os
    if os.getenv('JOB_MODE','embedded') in {'inline','test-inline'}:background.add_task(execute,identifier)
    return serialize(job)
@router.post('/documents/{identifier}/reindex')
def reindex(identifier:str,background:BackgroundTasks,user=Depends(current_user),db=Depends(get_db)):
    permit(user);doc=owned(db,Document,identifier,user)
    if doc.status not in {'Indexed','Failed'}:raise HTTPException(409,'Wait for active extraction/indexing to finish before rebuilding')
    if not db.scalar(select(Chunk).where(Chunk.document_id==identifier)):raise HTTPException(409,'No source chunks to index')
    return serialize(dispatch(background,db,user.org_id,'reindex',identifier))
@router.get('/documents/{identifier}/versions')
def versions(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,Document,identifier,user)
    version=db.scalar(select(DocumentVersion).where(DocumentVersion.document_id==identifier))
    family=version.family_id if version else identifier
    ids=list(db.scalars(select(DocumentVersion.document_id).where(DocumentVersion.family_id==family,DocumentVersion.org_id==user.org_id)))
    return [serialize(x) for x in db.scalars(select(Document).where(Document.org_id==user.org_id,Document.id.in_(ids or [identifier])).order_by(Document.created_at))]
@router.get('/documents/{identifier}/metadata')
def source_metadata(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,Document,identifier,user)
    row=db.scalar(select(DocumentVersion).where(DocumentVersion.document_id==identifier,DocumentVersion.org_id==user.org_id))
    return serialize(row) if row else {'publication_date':None,'effective_date':None,'revision_date':None,'previous_document_id':None}
@router.patch('/documents/{identifier}/metadata')
def metadata(identifier:str,data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user);doc=owned(db,Document,identifier,user)
    if 'department' in data and (not isinstance(data['department'],str) or len(data['department'])>200):raise HTTPException(422,'Department must be text, at most 200 characters')
    if data.get('previous_document_id') and not isinstance(data['previous_document_id'],str):raise HTTPException(422,'Previous version must be a document ID')
    version=db.scalar(select(DocumentVersion).where(DocumentVersion.document_id==identifier))
    if not version:version=DocumentVersion(org_id=user.org_id,document_id=identifier,family_id=identifier);db.add(version)
    before=serialize(version)
    dates_changed=False
    for field in ['publication_date','effective_date','revision_date']:
        if field in data:
            try:
                value=date.fromisoformat(data[field]).isoformat() if data[field] else None
            except (ValueError,TypeError):raise HTTPException(422,'Dates must use YYYY-MM-DD')
            if getattr(version,field)!=value:dates_changed=True
            setattr(version,field,value)
    previous=data.get('previous_document_id')
    if previous:
        parent=owned(db,Document,previous,user)
        if parent.id==identifier or parent.kind!=doc.kind:raise HTTPException(422,'Choose a previous source of the same kind')
        parent_version=db.scalar(select(DocumentVersion).where(DocumentVersion.document_id==previous))
        if version.previous_document_id and version.previous_document_id!=previous:raise HTTPException(409,'Existing version lineage is immutable')
        if db.scalar(select(DocumentVersion).where(DocumentVersion.previous_document_id==identifier)) and version.previous_document_id!=previous:raise HTTPException(409,'Cannot reparent a source with linked descendants')
        if parent.created_at>=doc.created_at:raise HTTPException(422,'A previous version must predate this upload')
        version.previous_document_id=previous;version.family_id=parent_version.family_id if parent_version else previous
    doc.metadata_json={**doc.metadata_json,**{k:data[k] for k in ['department'] if k in data},'regulatory_dates':{k:getattr(version,k) for k in ['publication_date','effective_date','revision_date']}}
    if dates_changed and doc.kind=='regulatory':doc.regulatory_status='UNVERIFIED'
    db.flush()
    audit(db,user,'SOURCE_METADATA_UPDATE',identifier,{'before':before,'after':serialize(version),'submitted':data});db.commit();return serialize(version)
@router.get('/documents/{identifier}/pages/{page}')
def page_image(identifier:str,page:int,chunk_id:str|None=None,user=Depends(current_user),db=Depends(get_db)):
    import pymupdf
    doc=owned(db,Document,identifier,user)
    if not doc.name.lower().endswith('.pdf'):raise HTTPException(422,'Only PDF sources have rendered physical pages')
    selected=None
    if chunk_id:
        selected=owned(db,Chunk,chunk_id,user)
        if selected.document_id!=identifier or selected.page!=page:raise HTTPException(422,'Chunk does not belong to this source page')
    from app.services.storage_service import pdf
    with pdf(doc.path) as source:
        if not 1<=page<=len(source):raise HTTPException(404,'PDF page not found')
        rendered=source[page-1]
        if selected:
            for line in selected.text.splitlines():
                if len(line.strip())<8:continue
                for rectangle in rendered.search_for(line.strip())[:50]:rendered.add_highlight_annot(rectangle)
        image=rendered.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4),alpha=False).tobytes('png')
    audit(db,user,'SOURCE_PAGE_VIEW',identifier,{'page':page,'chunk_id':chunk_id});db.commit()
    return Response(image,media_type='image/png')
@router.patch('/compliance/assessments/{identifier}')
def update_draft(identifier:str,data:AssessmentInput,user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);assessment=owned(db,Assessment,identifier,user)
    if assessment.status!='DRAFT':raise HTTPException(409,'Only drafts can be edited')
    for identifier_ in data.regulatory_document_ids:
        d=owned(db,Document,identifier_,user)
        if d.kind!='regulatory' or d.regulatory_status!='CURRENT_APPROVED' or d.status!='Indexed' or d.archived or d.jurisdiction!=data.jurisdiction:raise HTTPException(422,'Regulatory source is not current, indexed and applicable')
    for identifier_ in data.organizational_document_ids:
        d=owned(db,Document,identifier_,user)
        if d.kind!='organizational' or d.archived or d.status!='Indexed':raise HTTPException(422,'Organizational source must be indexed')
    if len(data.requirement_ids)!=len(set(data.requirement_ids)):raise HTTPException(422,'Duplicate requirements')
    for identifier_ in [*data.requirement_ids,*data.excluded_requirements]:
        r=owned(db,Requirement,identifier_,user)
        if r.document_id not in data.regulatory_document_ids or r.status!='APPROVED':raise HTTPException(422,'Select approved requirements from the chosen sources')
    assessment.name=data.name;assessment.config={**assessment.config,**data.model_dump(),'requirement_snapshots':requirement_snapshot(db,[*data.requirement_ids,*data.excluded_requirements]),'applicability_review':{'reviewer_id':user.id,'reviewed_at':now()}}
    from app.services.assessment_config_service import sync_links
    sync_links(db,assessment);audit(db,user,'ASSESSMENT_DRAFT_UPDATE',assessment.id);db.commit();return serialize(assessment)
@router.get('/regulations/requirements/{identifier}/versions')
def requirement_versions(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,Requirement,identifier,user)
    return [serialize(x) for x in db.scalars(select(RequirementVersion).where(RequirementVersion.requirement_id==identifier,RequirementVersion.org_id==user.org_id).order_by(RequirementVersion.created_at))]
@router.post('/capa/{identifier}/attachments',status_code=201)
async def capa_attach(identifier:str,file:UploadFile=File(...),user=Depends(current_user),db=Depends(get_db)):
    permit(user,REVIEW_ROLES);capa=owned(db,Capa,identifier,user)
    if capa.status=='CLOSED':raise HTTPException(409,'Closed CAPAs are immutable')
    from app.services.extraction_service import validate_file
    from app.services.file_security_service import scan
    raw=await file.read(MAX_UPLOAD+1);name=(file.filename or 'evidence').replace('\\','/').rsplit('/',1)[-1][:250];ext=validate_file(name,raw)
    folder=STORAGE/'capa'/user.org_id;folder.mkdir(parents=True,exist_ok=True);path=folder/(uid()+ext);path.write_bytes(raw)
    try:scan(path)
    except Exception as exc:path.unlink(missing_ok=True);raise HTTPException(422,str(exc))
    from app.services.storage_service import encrypt_file
    from starlette.concurrency import run_in_threadpool
    path=await run_in_threadpool(encrypt_file,path)
    attachment=CapaAttachment(org_id=user.org_id,capa_id=capa.id,uploaded_by=user.id,name=name,path=str(path),checksum=hashlib.sha256(raw).hexdigest());db.add(attachment);db.flush();audit(db,user,'CAPA_EVIDENCE_UPLOAD',attachment.id,{'checksum':attachment.checksum});db.commit();return serialize(attachment)
@router.get('/capa/{identifier}/attachments')
def capa_attachments(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,Capa,identifier,user)
    return [serialize(x) for x in db.scalars(select(CapaAttachment).where(CapaAttachment.capa_id==identifier,CapaAttachment.org_id==user.org_id))]
@router.get('/capa/attachments/{identifier}/download')
def attachment_download(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    row=owned(db,CapaAttachment,identifier,user);audit(db,user,'CAPA_EVIDENCE_DOWNLOAD',identifier);db.commit()
    from app.services.storage_service import download
    return download(row.path,row.name)
@router.get('/capa/{identifier}/history')
def capa_history(identifier:str,user=Depends(current_user),db=Depends(get_db)):
    owned(db,Capa,identifier,user)
    return [serialize(x) for x in db.scalars(select(CapaEvent).where(CapaEvent.capa_id==identifier,CapaEvent.org_id==user.org_id).order_by(CapaEvent.created_at))]
@router.post('/sources',status_code=201)
def register_source(data:dict,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'})
    from urllib.parse import urlsplit
    from app.services.source_import_service import OFFICIAL
    import os
    url=str(data.get('url',''));parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in OFFICIAL|set(os.getenv('SOURCE_ALLOWED_HOSTS','').split(',')) or parsed.username or parsed.password or parsed.port not in {None,443}:raise HTTPException(422,'Register an allowlisted official HTTPS URL')
    if not all(isinstance(data.get(k),str) and 1<=len(data[k])<=250 for k in ['title','authority','jurisdiction']):raise HTTPException(422,'Title, authority and jurisdiction required')
    source=RegulatorySource(org_id=user.org_id,url=url,title=data['title'],authority=data['authority'],jurisdiction=data['jurisdiction'],approved_by=user.id);db.add(source);db.flush();audit(db,user,'SOURCE_REGISTER',source.id);db.commit();return serialize(source)
@router.get('/sources')
def sources(user=Depends(current_user),db=Depends(get_db)):
    return [serialize(x) for x in db.scalars(select(RegulatorySource).where(RegulatorySource.org_id==user.org_id).order_by(RegulatorySource.created_at))]
@router.post('/sources/{identifier}/import',status_code=201)
async def import_source(identifier:str,background:BackgroundTasks,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'});source=owned(db,RegulatorySource,identifier,user)
    from app.services.source_import_service import fetch
    from starlette.concurrency import run_in_threadpool
    try:name,data,url=await run_in_threadpool(fetch,source.url)
    except Exception as exc:raise HTTPException(422,'Source import failed: '+str(exc))
    result=await save_upload(UploadFile(filename=name,file=io.BytesIO(data)),background,db,user,'regulatory','Regulatory Guidelines',source.authority,source.jurisdiction,'Imported; review required',url)
    audit(db,user,'SOURCE_IMPORT',source.id,{'document_id':result['id']});db.commit();return result
@router.get('/dashboard/analytics')
def analytics(authority:str|None=None,department:str|None=None,since:str|None=None,until:str|None=None,user=Depends(current_user),db=Depends(get_db)):
    stmt=select(Document).where(Document.org_id==user.org_id,Document.archived==0)
    if authority:stmt=stmt.where(Document.authority==authority)
    if since:stmt=stmt.where(Document.created_at>=since)
    if until:stmt=stmt.where(Document.created_at<=until+'T23:59:59.999999+00:00')
    docs=list(db.scalars(stmt));docs=[d for d in docs if not department or d.metadata_json.get('department')==department]
    ids={d.id for d in docs}
    from collections import Counter
    findings=list(db.scalars(select(Finding).where(Finding.org_id==user.org_id)))
    scoped=[f for f in findings if any(e['document_id'] in ids for e in f.original['regulatory_evidence']+f.original['organizational_evidence'])]
    capas=list(db.scalars(select(Capa).where(Capa.org_id==user.org_id,Capa.finding_id.in_([f.id for f in scoped]))))
    return {'authority_distribution':dict(Counter(d.authority for d in docs if d.kind=='regulatory')),'document_processing':dict(Counter(d.status for d in docs)),'department_distribution':dict(Counter(d.metadata_json.get('department','Unassigned') for d in docs)),'compliance_distribution':dict(Counter(f.reviewed_classification or f.original['compliance_status'] for f in scoped)),'capa_status':dict(Counter(c.status for c in capas)),'overdue_capas':[serialize(c) for c in capas if c.status!='CLOSED' and c.data.get('due_date','9999')<date.today().isoformat()],'assessment_trend':dict(Counter(f.created_at[:10] for f in scoped))}
