import io
import pymupdf
from conftest import account
from app.db.database import Session
from app.models.entities import User
from sqlalchemy import select

def pdf(text):
    doc=pymupdf.open();page=doc.new_page();page.insert_textbox((50,50,550,750),text,fontsize=11);return doc.tobytes()
def upload(client,headers,name,text,kind='organizational'):
    response=client.post('/api/documents/upload',headers=headers,data={'kind':kind,'jurisdiction':'India','version':'test-1'},files={'file':(name,pdf(text),'application/pdf')})
    assert response.status_code==201,response.text
    identifier=response.json()['id']
    source=client.get('/api/documents/'+identifier,headers=headers).json()
    assert source['status']=='Indexed',source
    return source

def setup_assessment(client,headers):
    reg=upload(client,headers,'DEMONSTRATION-regulation.pdf','DEMONSTRATION DATA - NOT OFFICIAL REGULATION\n1 Training\nPersonnel must receive training before operating equipment.','regulatory')
    assert reg['chunks'][0]['page']==1
    assert len(reg['checksum'])==64
    review=client.post('/api/regulations/'+reg['id']+'/applicability',headers=headers,json={'status':'CURRENT_APPROVED','explanation':'Synthetic applicability approved for controlled test only.'})
    assert review.status_code==200,review.text
    requirements=client.get('/api/regulations/'+reg['id']+'/requirements',headers=headers).json()
    assert requirements
    for req in requirements:
        r=client.post('/api/regulations/requirements/'+req['id']+'/review',headers=headers,json={'decision':'APPROVED','explanation':'Reviewed original source in controlled test.','designation':'MANDATORY'})
        assert r.status_code==200,r.text
    sop=upload(client,headers,'DEMONSTRATION-SOP.pdf','DEMONSTRATION DATA\n1 Training\nEquipment operators receive training. Signed records are retained by Quality Assurance.')
    config={'name':'Controlled test assessment','regulatory_document_ids':[reg['id']],'organizational_document_ids':[sop['id']],'requirement_ids':[r['id'] for r in requirements],'scope':'Documentary review of operator training','jurisdiction':'India'}
    assessment=client.post('/api/compliance/assessments',headers=headers,json=config)
    assert assessment.status_code==201,assessment.text
    identifier=assessment.json()['id']
    run=client.post('/api/compliance/assessments/'+identifier+'/run',headers=headers)
    assert run.status_code==200,run.text
    state=client.get('/api/compliance/assessments/'+identifier,headers=headers).json()
    assert state['status']=='COMPLETED',state
    return identifier,reg,sop

def test_end_to_end(client):
    headers=account(client)
    login=client.post('/api/auth/login',json={'email':'reviewer@example.com','password':'A-secure-password-123'})
    assert login.status_code==200
    identifier,reg,sop=setup_assessment(client,headers)
    findings=client.get('/api/compliance/assessments/'+identifier+'/findings',headers=headers).json()
    assert findings
    finding=findings[0]
    assert finding['original']['compliance_status']=='INSUFFICIENT_EVIDENCE'
    assert finding['original']['organizational_evidence'][0]['document_id']==sop['id']
    assert finding['original']['regulatory_evidence'][0]['page']==1
    r=client.post('/api/compliance/findings/'+finding['id']+'/review',headers=headers,json={'decision':'EVIDENCE_REQUESTED','classification':'INSUFFICIENT_EVIDENCE','explanation':'Obtain signed training completion records before determining compliance.'})
    assert r.status_code==200
    assert r.json()['original']==finding['original']
    risk=client.post('/api/risk/assess',headers=headers,json={'finding_id':finding['id'],'severity':3,'likelihood':2,'detectability':4,'explanation':'Training documentation requires investigation.'})
    assert risk.json()['score']==24
    capa=client.post('/api/capa',headers=headers,json={'finding_id':finding['id'],'title':'Obtain training records','owner':'QA Manager','due_date':'2026-12-31','root_cause':'Under investigation','corrective_action':'Collect and review training evidence','preventive_action':'Review record retention process'})
    assert capa.status_code==201,capa.text
    cid=capa.json()['id']
    member=client.post('/api/users',headers=headers,json={'email':'independent@example.com','name':'Independent reviewer','password':'Independent-reviewer-123','role':'Quality Assurance Manager'})
    assert member.status_code==201
    independent=client.post('/api/auth/login',json={'email':'independent@example.com','password':'Independent-reviewer-123'}).json()
    approver={'Authorization':'Bearer '+independent['access_token']}
    for status in ['IN_PROGRESS','VERIFICATION','CLOSED']:
        r=client.patch('/api/capa/'+cid,headers=approver if status=='CLOSED' else headers,json={'status':status,'implementation_evidence':'Reviewed record TR-001, synthetic test only','effectiveness_review':'QA confirmed evidence retention in controlled test'})
        assert r.status_code==200,r.text
    for fmt in ['pdf','docx','csv']:
        report=client.post('/api/reports/generate',headers=headers,json={'assessment_id':identifier,'format':fmt})
        assert report.status_code==201,report.text
        data=client.get('/api/reports/'+report.json()['id']+'/download',headers=headers)
        assert data.status_code==200 and len(data.content)>100
        if fmt=='pdf':
            with pymupdf.open(stream=data.content,filetype='pdf') as doc:
                text=''.join(p.get_text() for p in doc)
                assert 'INSUFFICIENT_EVIDENCE' in text
                assert reg['id'] in text
    summary=client.get('/api/dashboard/summary',headers=headers).json()
    assert summary['documents']==2 and summary['assessments']==1 and summary['findings']==len(findings)
    assert len(client.get('/api/audit-logs',headers=headers).json())>=10
    assert client.post('/api/compliance/assessments/'+identifier+'/run',headers=headers).status_code==409

def test_organization_isolation(client):
    a=account(client,'a@example.com');b=account(client,'b@example.com')
    source=upload(client,a,'source.pdf','DEMONSTRATION DATA\nTraining records are retained.')
    for suffix in ['', '/preview','/status']:
        assert client.get('/api/documents/'+source['id']+suffix,headers=b).status_code==404
    assert client.get('/api/documents',headers=b).json()==[]
    assert client.post('/api/retrieval/search',headers=b,json={'query':'training','document_ids':[source['id']]}).json()==[]

def test_file_validation_and_rbac(client):
    headers=account(client)
    assert client.post('/api/documents/upload',headers=headers,files={'file':('bad.pdf',b'not pdf')}).status_code==415
    assert client.post('/api/documents/upload',headers=headers,files={'file':('evil.exe',b'example')}).status_code==415
    with Session() as db:
        user=db.scalar(select(User));user.role='Standard User';db.commit()
    assert client.post('/api/documents/upload',headers=headers,files={'file':('test.txt',b'test')}).status_code==403
    assert client.get('/api/audit-logs',headers=headers).status_code==403

def test_token_rotation_and_logout(client):
    headers=account(client)
    login=client.post('/api/auth/login',json={'email':'reviewer@example.com','password':'A-secure-password-123'}).json()
    assert client.post('/api/auth/refresh',json={'refresh_token':login['access_token']}).status_code==401
    assert client.post('/api/auth/refresh',json={'refresh_token':login['refresh_token']}).status_code==200
    assert client.post('/api/auth/refresh',json={'refresh_token':login['refresh_token']}).status_code==401
    assert client.post('/api/auth/logout',headers=headers).status_code==200
    assert client.get('/api/auth/me',headers=headers).status_code==401

def test_current_approval_gate(client):
    h=account(client)
    reg=upload(client,h,'draft.pdf','DEMONSTRATION DATA\nPersonnel shall complete training.','regulatory')
    req=client.get('/api/regulations/'+reg['id']+'/requirements',headers=h).json()[0]
    sop=upload(client,h,'sop.pdf','DEMONSTRATION DATA\nPersonnel training record.')
    r=client.post('/api/compliance/assessments',headers=h,json={'name':'Blocked draft','regulatory_document_ids':[reg['id']],'organizational_document_ids':[sop['id']],'requirement_ids':[req['id']],'scope':'Documentary training review','jurisdiction':'India'})
    assert r.status_code==422

def test_chat_and_evaluation(client):
    h=account(client)
    doc=upload(client,h,'training.pdf','DEMONSTRATION DATA\nTraining records for operators are approved.')
    r=client.post('/api/chat',headers=h,json={'query':'training records'})
    assert r.status_code==200 and r.json()['organizational_evidence']
    result=client.post('/api/evaluation/run',headers=h,json={'k':1,'cases':[{'query':'training','relevant_chunk_ids':[doc['chunks'][0]['id']]}]})
    assert result.status_code==200,result.text
    assert result.json()['metrics']['hybrid']['precision_at_k']==1
