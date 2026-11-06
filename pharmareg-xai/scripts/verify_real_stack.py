"""Run actual local LLM + semantic embeddings + persistent Chroma acceptance.

Uses an isolated database; no production data and no external LLM transmissions.
The generated labels are software fixtures, never claimed as an expert gold set.
"""
import os,sys,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];backend=root/'backend'
storage=root/'storage'/'real-stack-verification';storage.mkdir(parents=True,exist_ok=True)
os.environ.update(STORAGE_DIR=str(storage),DATABASE_URL='sqlite:///'+str(storage/'acceptance.db'),LLM_PROVIDER='local-openai',LLM_MODEL=os.getenv('VERIFY_LLM_MODEL','llama3.2:3b'),OPENAI_BASE_URL='http://localhost:11434/v1',LLM_TIMEOUT='240',EMBEDDING_PROVIDER='sentence-transformers',EMBEDDING_MODEL='sentence-transformers/all-MiniLM-L6-v2',MODELS_OFFLINE='true',VECTOR_STORE='chroma',CHROMA_MODE='persistent',JOB_MODE='test-inline',ANONYMIZED_TELEMETRY='False')
os.environ['RERANKER_CACHE']=str(root/'storage'/'models')
sys.path.insert(0,str(backend));os.chdir(backend)
from alembic.config import Config
from alembic import command
command.upgrade(Config(str(backend/'alembic.ini')),'head')
from fastapi.testclient import TestClient
from app.main import app
started=time.perf_counter();results={}
def check(response,code=200):
    assert response.status_code==code,response.text
    return response.json()
with TestClient(app) as client:
    tokens=check(client.post('/api/auth/register',json={'email':f'real-{time.time_ns()}@example.com','name':'Controlled real-model test','password':'Actual-model-test-123','organization':'DEMONSTRATION DATA real ML verification'}),201)
    h={'Authorization':'Bearer '+tokens['access_token']}
    payload=(root/'sample_data'/'official'/'FDA-Q7-2016.pdf').read_bytes()
    regulatory=check(client.post('/api/regulations/upload',headers=h,data={'authority':'US FDA','jurisdiction':'US','version':'September 2016'},files={'file':('FDA-Q7-2016.pdf',payload,'application/pdf')}),201)
    doc=check(client.get('/api/documents/'+regulatory['id'],headers=h));assert doc['status']=='Indexed',doc['error']
    results['authentic_pdf']={'pages':doc['pages'],'chunks':len(doc['chunks']),'embedding_dimension':len(doc['chunks'][0]['embedding']),'checksum':doc['checksum']}
    reqs=check(client.get('/api/regulations/'+doc['id']+'/requirements',headers=h))
    training=next((r for r in reqs if r['statement'].lower().startswith('training should')),next((r for r in reqs if 'training' in r['statement'].lower() and len(r['statement'])>60),reqs[0]))
    check(client.post('/api/regulations/'+doc['id']+'/applicability',headers=h,json={'status':'CURRENT_APPROVED','explanation':'Controlled software test of authentic source; not qualified regulatory approval.'}))
    check(client.post('/api/regulations/requirements/'+training['id']+'/review',headers=h,json={'decision':'APPROVED','explanation':'Controlled software fixture; original training guidance preserved.','designation':'ADVISORY'}))
    sop=check(client.post('/api/documents/upload',headers=h,data={'jurisdiction':'US'},files={'file':('DEMONSTRATION-SOP.txt',b'DEMONSTRATION DATA - synthetic organizational evidence\n1 Personnel training\nPersonnel receive training before operating equipment. The Quality Assurance manager retains signed training records. Training effectiveness has not been evaluated; no effectiveness records were supplied.','text/plain')}),201)
    sop_detail=check(client.get('/api/documents/'+sop['id'],headers=h));assert sop_detail['status']=='Indexed',sop_detail['error']
    retrieval=check(client.post('/api/retrieval/search',headers=h,json={'query':training['statement'],'document_ids':[sop['id']],'top_k':3}));assert retrieval
    results['hybrid_retrieval']={'sources':len(retrieval),'score':retrieval[0]['retrieval_score'],'dense_score':retrieval[0]['dense_score']}
    reranked=check(client.post('/api/retrieval/search',headers=h,json={'query':training['statement'],'document_ids':[sop['id']],'top_k':3,'mode':'reranked'}));assert reranked;results['cross_encoder_reranking']={'returned':len(reranked),'model':'cross-encoder/ms-marco-MiniLM-L-6-v2'}
    assessment=check(client.post('/api/compliance/assessments',headers=h,json={'name':'Actual local-model acceptance','regulatory_document_ids':[doc['id']],'organizational_document_ids':[sop['id']],'requirement_ids':[training['id']],'jurisdiction':'US','scope':'Documentary training assessment using synthetic SOP evidence; no operational compliance is presumed.'}),201)
    check(client.post('/api/compliance/assessments/'+assessment['id']+'/run',headers=h))
    state=check(client.get('/api/compliance/assessments/'+assessment['id'],headers=h));assert state['status']=='COMPLETED',state
    findings=check(client.get('/api/compliance/assessments/'+assessment['id']+'/findings',headers=h));finding=findings[0]
    assert finding['original']['provider']=='local-openai'
    assert finding['original']['validation_status']!='REJECTED_REQUIRES_REVIEW' or (finding['original']['compliance_status']=='INSUFFICIENT_EVIDENCE' and not finding['original']['citations'])
    results['real_llm']={'model':os.environ['LLM_MODEL'],'status':finding['original']['compliance_status'],'model_proposed_status':finding['original'].get('model_proposed_status'),'validation_limitations':finding['original'].get('validation_limitations',[]),'citations':finding['original']['citations'],'explanation':finding['original']['reasoning_summary'],'generation':finding['original'].get('generation_metadata',{})}
    results['real_llm']['validation_status']=finding['original']['validation_status']
    check(client.post('/api/compliance/findings/'+finding['id']+'/review',headers=h,json={'decision':'EVIDENCE_REQUESTED','classification':'INSUFFICIENT_EVIDENCE','explanation':'Controlled software review: request objective training effectiveness records.'}))
    risk=check(client.post('/api/risk/assess',headers=h,json={'finding_id':finding['id'],'severity':3,'likelihood':2,'detectability':3,'explanation':'Internal training documentation risk, controlled fixture.'}))
    capa=check(client.post('/api/capa',headers=h,json={'finding_id':finding['id'],'title':'Obtain objective training effectiveness evidence','owner':'QA test reviewer','due_date':'2026-12-31','root_cause':'Evidence not provided','corrective_action':'Review training effectiveness records','preventive_action':'Review evidence retention controls'}),201)
    attachment=check(client.post('/api/capa/'+capa['id']+'/attachments',headers=h,files={'file':('DEMONSTRATION-evidence.txt',b'DEMONSTRATION DATA controlled training evidence') }),201)
    check(client.post('/api/users',headers=h,json={'name':'Independent test reviewer','email':f'independent-{time.time_ns()}@example.com','password':'Independent-model-123','role':'Quality Assurance Manager'}),201)
    from app.db.database import Session
    from app.models.entities import User
    from sqlalchemy import select
    with Session() as db:reviewer=db.scalar(select(User).where(User.org_id==doc['org_id'],User.email.like('independent-%')));email=reviewer.email
    independent=check(client.post('/api/auth/login',json={'email':email,'password':'Independent-model-123'}));ih={'Authorization':'Bearer '+independent['access_token']}
    for status in ['IN_PROGRESS','VERIFICATION','CLOSED']:
        check(client.patch('/api/capa/'+capa['id'],headers=ih if status=='CLOSED' else h,json={'status':status,'implementation_evidence':'Controlled attached record '+attachment['id'],'effectiveness_review':'Independent test review only; not operational verification.'}))
    results['risk_and_capa']={'score':risk['score'],'capa_id':capa['id'],'closure':'independent reviewer','attachment_id':attachment['id']}
    for format in ['pdf','docx','csv']:
        report=check(client.post('/api/reports/generate',headers=h,json={'assessment_id':assessment['id'],'format':format}),201)
        download=client.get('/api/reports/'+report['id']+'/download',headers=h);assert download.status_code==200
        results.setdefault('reports',{})[format]=len(download.content)
    before=[c['id'] for c in sop_detail['chunks']]
    check(client.post('/api/documents/'+sop['id']+'/reindex',headers=h))
    after=check(client.get('/api/documents/'+sop['id'],headers=h));assert [c['id'] for c in after['chunks']]==before
    results['reindex_preserves_citations']=True
    integrity=check(client.get('/api/audit-logs/verify',headers=h));assert integrity['valid'];results['audit_sealed_records']=integrity['sealed_records']
results['elapsed_seconds']=time.perf_counter()-started
(root/'docs'/'REAL_STACK_RESULTS.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
