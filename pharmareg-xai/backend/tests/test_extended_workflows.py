import time,socket,json,sys
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from conftest import account
from test_workflow import upload,setup_assessment
from app.db.database import Session
from app.models.entities import ProcessingJob,Audit
from app.services.job_service import enqueue,claim,execute

def independent(client,h):
    r=client.post('/api/users',headers=h,json={'name':'Independent QA','email':'independent@example.com','password':'Independent-password-123','role':'Quality Assurance Manager'})
    assert r.status_code==201,r.text
    r=client.post('/api/auth/login',json={'email':'independent@example.com','password':'Independent-password-123'})
    return {'Authorization':'Bearer '+r.json()['access_token']}
def test_durable_jobs_single_claim_and_expired_lease(client):
    h=account(client);doc=upload(client,h,'DEMONSTRATION.pdf','DEMONSTRATION DATA\nTraining records are retained.')
    org=client.get('/api/auth/me',headers=h).json()['org_id']
    with Session() as db:
        job=enqueue(db,org,'reindex',doc['id']);db.commit();identifier=job.id
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:claim(identifier),range(4)))
    assert sum(r is not None for r in results)==1
    with Session() as db:job=db.get(ProcessingJob,identifier);job.lease_until=int(time.time())-1;db.commit()
    assert execute(identifier)
    with Session() as db:job=db.get(ProcessingJob,identifier);assert job.state=='SUCCEEDED' and job.attempts==2
    jobs=client.get('/api/jobs?target_id='+doc['id'],headers=h).json();assert all(j['state']=='SUCCEEDED' for j in jobs)
def test_reindex_lineage_and_pdf_viewer(client):
    h=account(client);first=upload(client,h,'v1.pdf','DEMONSTRATION DATA\nTraining evidence exists.')
    second=upload(client,h,'v2.pdf','DEMONSTRATION DATA\nTraining evidence revised.')
    ids=[c['id'] for c in second['chunks']]
    assert client.post('/api/documents/'+second['id']+'/reindex',headers=h).status_code==200
    assert [c['id'] for c in client.get('/api/documents/'+second['id'],headers=h).json()['chunks']]==ids
    r=client.patch('/api/documents/'+second['id']+'/metadata',headers=h,json={'previous_document_id':first['id'],'effective_date':'2026-10-01','department':'Quality'})
    assert r.status_code==200,r.text
    assert len(client.get('/api/documents/'+second['id']+'/versions',headers=h).json())==2
    image=client.get('/api/documents/'+second['id']+'/pages/1?chunk_id='+ids[0],headers=h)
    assert image.status_code==200 and image.content.startswith(b'\x89PNG')
    assert client.get('/api/documents/'+first['id']+'/pages/1?chunk_id='+ids[0],headers=h).status_code==422
    b=account(client,'other@example.com')
    assert client.get('/api/documents/'+second['id']+'/pages/1',headers=b).status_code==404
    page=client.get('/api/records/documents?limit=1&offset=1',headers=h).json();assert page['total']==2 and len(page['items'])==1
def test_edit_draft_and_immutable_completed(client):
    h=account(client);identifier,reg,sop=setup_assessment(client,h)
    completed=client.get('/api/compliance/assessments/'+identifier,headers=h).json()
    config=completed['config'];config['name']='Edited draft'
    assert client.patch('/api/compliance/assessments/'+identifier,headers=h,json=config).status_code==409
    draft=client.post('/api/compliance/assessments',headers=h,json=config).json()
    config['scope']='Revised documentary training scope'
    r=client.patch('/api/compliance/assessments/'+draft['id'],headers=h,json=config);assert r.status_code==200 and r.json()['config']['scope']==config['scope']
def test_dataset_independent_review_and_real_metrics(client):
    h=account(client);identifier,reg,sop=setup_assessment(client,h);ih=independent(client,h)
    finding=client.get('/api/compliance/assessments/'+identifier+'/findings',headers=h).json()[0]
    dataset=client.post('/api/evaluation/datasets',headers=h,json={'name':'DEMONSTRATION DATA controlled labels'}).json()
    label={'query':'training records','relevant_chunk_ids':[sop['chunks'][0]['id']],'finding_id':finding['id'],'expected_classification':'INSUFFICIENT_EVIDENCE','claim_supported':[True,False],'element_supported':[True,False],'citation_complete':True}
    row=client.post('/api/evaluation/datasets/'+dataset['id']+'/cases',headers=h,json=label)
    assert row.status_code==201,row.text
    rid=row.json()['id'];review={'decision':'APPROVED','explanation':'Independent fixture review of expected labels.'}
    assert client.post('/api/evaluation/cases/'+rid+'/review',headers=h,json=review).status_code==403
    assert client.post('/api/evaluation/datasets/'+dataset['id']+'/run',headers=h,json={}).status_code==422
    assert client.post('/api/evaluation/cases/'+rid+'/review',headers=ih,json=review).status_code==200
    result=client.post('/api/evaluation/datasets/'+dataset['id']+'/run',headers=h,json={'k':2})
    assert result.status_code==200,result.text
    metrics=result.json()['metrics'];assert metrics['classification']['accuracy']==1
    assert metrics['explainability']['unsupported_claim_rate_human_labeled']==.5
    assert metrics['explainability']['evidence_coverage_human_labeled']==.5
def test_capa_attachment_and_separate_closure(client):
    h=account(client);identifier,reg,sop=setup_assessment(client,h);ih=independent(client,h)
    finding=client.get('/api/compliance/assessments/'+identifier+'/findings',headers=h).json()[0]
    capa=client.post('/api/capa',headers=h,json={'finding_id':finding['id'],'title':'Controlled evidence action','owner':'QA','due_date':'2026-12-01'}).json()
    attachment=client.post('/api/capa/'+capa['id']+'/attachments',headers=h,files={'file':('DEMONSTRATION.txt',b'DEMONSTRATION DATA approved evidence')})
    assert attachment.status_code==201,attachment.text
    aid=attachment.json()['id'];assert client.get('/api/capa/attachments/'+aid+'/download',headers=ih).status_code==200
    update={'implementation_evidence':'Controlled attachment '+aid,'effectiveness_review':'Independent verification of fixture evidence'}
    for status in ['IN_PROGRESS','VERIFICATION']:assert client.patch('/api/capa/'+capa['id'],headers=h,json={**update,'status':status}).status_code==200
    assert client.patch('/api/capa/'+capa['id'],headers=h,json={**update,'status':'CLOSED'}).status_code==403
    assert client.patch('/api/capa/'+capa['id'],headers=ih,json={**update,'status':'CLOSED'}).status_code==200
    assert len(client.get('/api/capa/'+capa['id']+'/history',headers=h).json())==4
def test_conversation_history_private_to_author(client):
    h=account(client);ih=independent(client,h);upload(client,h,'records.pdf','DEMONSTRATION DATA\nTraining records are retained.')
    session=client.post('/api/conversations',headers=h,json={'title':'Training review'}).json()
    for question in ['What training records are retained?','Who retains those records?']:
        r=client.post('/api/conversations/'+session['id']+'/messages',headers=h,json={'query':question});assert r.status_code==200,r.text
    assert len(client.get('/api/conversations/'+session['id'],headers=h).json()['turns'])==2
    assert client.get('/api/conversations/'+session['id'],headers=ih).status_code==404
def test_audit_seals_detect_tampering(client):
    h=account(client);upload(client,h,'record.pdf','DEMONSTRATION DATA\nEvidence record.')
    result=client.get('/api/audit-logs/verify',headers=h).json();assert result['valid'] and result['sealed_records']>=2
    with Session() as db:
        row=db.scalar(select(Audit).where(Audit.action=='DOCUMENT_UPLOAD'));row.details={'tampered':True};db.commit()
    result=client.get('/api/audit-logs/verify',headers=h).json();assert not result['valid'] and result['invalid_records']
def test_source_import_ssrf_and_scanner_fail_closed(client,monkeypatch):
    from app.services.source_import_service import validate_url
    import pytest
    with pytest.raises(ValueError):validate_url('http://127.0.0.1/internal')
    with pytest.raises(ValueError):validate_url('https://attacker.invalid/secret')
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))])
    with pytest.raises(ValueError,match='public'):validate_url('https://www.fda.gov/example.pdf')
    h=account(client);monkeypatch.setenv('MALWARE_SCANNER_COMMAND',json.dumps([sys.executable,'-c','import sys;sys.exit(1)']))
    r=client.post('/api/documents/upload',headers=h,files={'file':('file.txt',b'DEMONSTRATION DATA')});assert r.status_code==422
    assert client.get('/api/documents',headers=h).json()==[]
def test_saved_draft_detects_changed_requirement_review(client):
    h=account(client);identifier,reg,sop=setup_assessment(client,h)
    complete=client.get('/api/compliance/assessments/'+identifier,headers=h).json()
    draft=client.post('/api/compliance/assessments',headers=h,json=complete['config']).json()
    rid=complete['config']['requirement_ids'][0]
    review=client.post('/api/regulations/requirements/'+rid+'/review',headers=h,json={'decision':'APPROVED','explanation':'Controlled revised requirement interpretation.','statement':'Personnel must receive training and retain objective records.'})
    assert review.status_code==200
    rejected=client.post('/api/compliance/assessments/'+draft['id']+'/run',headers=h)
    assert rejected.status_code==409
    assert client.get('/api/compliance/assessments/'+draft['id'],headers=h).json()['status']=='DRAFT'
    edited=client.patch('/api/compliance/assessments/'+draft['id'],headers=h,json=complete['config']);assert edited.status_code==200
    assert client.post('/api/compliance/assessments/'+draft['id']+'/run',headers=h).status_code==200
def test_regulatory_date_correction_requires_new_applicability_review(client):
    h=account(client);doc=upload(client,h,'regulation.pdf','DEMONSTRATION DATA\nTraining should be documented.','regulatory')
    assert client.post('/api/regulations/'+doc['id']+'/applicability',headers=h,json={'status':'CURRENT_APPROVED','explanation':'Controlled fixture applicability review.'}).status_code==200
    assert client.patch('/api/documents/'+doc['id']+'/metadata',headers=h,json={'effective_date':'2026-10-01'}).status_code==200
    updated=client.get('/api/documents/'+doc['id'],headers=h).json()
    assert updated['regulatory_status']=='UNVERIFIED'
    assert updated['metadata_json']['regulatory_dates']['effective_date']=='2026-10-01'
    assert client.get('/api/documents/'+doc['id']+'/metadata',headers=h).json()['effective_date']=='2026-10-01'
