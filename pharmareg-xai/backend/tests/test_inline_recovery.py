from conftest import account
from test_workflow import upload
from app.db.database import Session
from app.models.entities import Document,ProcessingJob
from app.services.job_service import enqueue

def test_request_mode_recovers_queued_work_without_worker_and_is_tenant_scoped(client,monkeypatch):
    headers=account(client);doc=upload(client,headers,'recovery.pdf','DEMONSTRATION training evidence retained by Quality Assurance.')
    with Session() as db:
        source=db.get(Document,doc['id']);source.status='Queued';job=enqueue(db,source.org_id,'reindex',source.id);db.commit();jid=job.id
    other=account(client,'unrelated@example.com');monkeypatch.setenv('JOB_MODE','inline')
    assert client.get('/api/documents/'+doc['id'],headers=other).status_code==404
    with Session() as db:assert db.get(ProcessingJob,jid).state=='QUEUED'
    assert client.get('/api/documents/'+doc['id'],headers=headers).status_code==200
    with Session() as db:assert db.get(ProcessingJob,jid).state=='SUCCEEDED'
    assert client.get('/api/documents/'+doc['id'],headers=headers).json()['status']=='Indexed'
