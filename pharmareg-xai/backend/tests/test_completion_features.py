import os,secrets
from pathlib import Path
from sqlalchemy import select
from conftest import account
from test_workflow import setup_assessment,upload,pdf
from app.db.database import Session
from app.models.entities import Document,Report,AssessmentDocument,AssessmentRequirement

def test_encrypted_source_processing_preview_and_report_download(client,monkeypatch):
    monkeypatch.setenv('ENCRYPT_STORAGE','true');monkeypatch.setenv('STORAGE_ENCRYPTION_KEY',secrets.token_hex(32));h=account(client)
    aid,reg,sop=setup_assessment(client,h)
    with Session() as db:
        doc=db.get(Document,reg['id']);assert doc.path.endswith('.enc')
        assert Path(doc.path).read_bytes().startswith(b'PHARMAREG-FILE-v1')
        assert not Path(doc.path.removesuffix('.enc')).exists()
        assert len(list(db.scalars(select(AssessmentDocument).where(AssessmentDocument.assessment_id==aid))))==2
        assert len(list(db.scalars(select(AssessmentRequirement).where(AssessmentRequirement.assessment_id==aid))))==1
    original=client.get('/api/documents/'+reg['id']+'/preview',headers=h);assert original.status_code==200 and original.content.startswith(b'%PDF-')
    page=client.get('/api/documents/'+reg['id']+'/pages/1',headers=h);assert page.status_code==200 and page.content.startswith(b'\x89PNG')
    report=client.post('/api/reports/generate',headers=h,json={'assessment_id':aid,'format':'pdf'});assert report.status_code==201,report.text
    rid=report.json()['id']
    with Session() as db:assert db.get(Report,rid).path.endswith('.enc')
    download=client.get('/api/reports/'+rid+'/download',headers=h);assert download.status_code==200 and download.content.startswith(b'%PDF-')
    # A wrong file key fails closed; it never returns corrupt or unauthenticated plaintext.
    monkeypatch.setenv('STORAGE_ENCRYPTION_KEY',secrets.token_hex(32))
    from app.services.storage_service import read
    import pytest
    with pytest.raises(Exception):read(doc.path)
def test_paginated_filters_risk_grouping_and_current_review_elements(client):
    h=account(client);aid,reg,sop=setup_assessment(client,h)
    client.patch('/api/documents/'+sop['id']+'/metadata',headers=h,json={'department':'Quality'})
    finding=client.get('/api/compliance/assessments/'+aid+'/findings',headers=h).json()[0]
    client.post('/api/risk/assess',headers=h,json={'finding_id':finding['id'],'severity':4,'likelihood':4,'detectability':3,'explanation':'Controlled high-risk test factors.'})
    grouped=client.get('/api/records/findings?department=Quality&risk=HIGH&group_by=risk&limit=1',headers=h)
    assert grouped.status_code==200,grouped.text
    data=grouped.json();assert data['total']==1 and data['groups']=={'HIGH':1};assert data['items'][0]['latest_risk']['score']==48
    assert data['items'][0]['departments']==['Quality']
    assert data['items'][0]['categories']==[sop['category']]
    assert data['items'][0]['source_document_ids']==[sop['id']]
    assert client.get('/api/records/findings?group_by=category',headers=h).json()['groups']=={sop['category']:1}
    assert client.get('/api/records/findings?risk=LOW',headers=h).json()['total']==0
    docs=client.get('/api/records/documents?kind=organizational&department=Quality&limit=1',headers=h).json();assert docs['total']==1 and docs['items'][0]['id']==sop['id']
    rid=finding['requirement_id'];review=client.post('/api/regulations/requirements/'+rid+'/review',headers=h,json={'decision':'APPROVED','explanation':'Split reviewed material obligations.','material_elements':['Role-specific training','Objective completion records']});assert review.status_code==200
    current=client.get('/api/regulations/'+reg['id']+'/requirements',headers=h).json()[0];assert current['material_elements']==['Role-specific training','Objective completion records']
def test_validation_records_require_evidence_and_authorized_reviewer(client):
    h=account(client)
    assert client.post('/api/validation',headers=h,json={'area':'SECURITY','status':'VERIFIED','statement':'Not enough evidence.'}).status_code==422
    result=client.post('/api/validation',headers=h,json={'area':'FUNCTIONAL','status':'IN_REVIEW','statement':'Controlled software verification is complete; qualified domain review is not claimed.','evidence':{'reference':'docs/backend-tests.xml','reviewer_qualification':'Test fixture account; not a qualified domain expert'}})
    assert result.status_code==201,result.text
    assert client.get('/api/validation',headers=h).json()[0]['status']=='IN_REVIEW'
    readiness=client.get('/api/system/readiness',headers=h);assert readiness.status_code==200 and not readiness.json()['production_certified']
