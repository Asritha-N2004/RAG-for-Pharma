"""SQL durable queue, atomic leases, retry/backoff; Redis is a wake-up coordinator.

The authoritative work record lives in SQL, so a lost Redis notification cannot lose work.
Use a separate `python -m app.workers.worker` process in JOB_MODE=worker.
"""
import os,secrets,time,threading,logging
from functools import lru_cache
from sqlalchemy import select,update,or_
from sqlalchemy.exc import IntegrityError
from app.db.database import Session
from app.models.entities import ProcessingJob,Document,Assessment
log=logging.getLogger(__name__)

@lru_cache(maxsize=1)
def redis_client():
    if not os.getenv('REDIS_URL'): return None
    import redis
    return redis.Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=2,socket_timeout=3)
def enqueue(db,org_id,task,target_id):
    query=select(ProcessingJob).where(ProcessingJob.org_id==org_id,ProcessingJob.target_id==target_id,ProcessingJob.state.in_(['QUEUED','RUNNING','RETRY']))
    existing=db.scalar(query)
    if existing:return existing
    job=ProcessingJob(org_id=org_id,task=task,target_id=target_id);db.add(job)
    try:db.flush()
    except IntegrityError:
        db.rollback();existing=db.scalar(query)
        if existing:return existing
        raise
    return job
def notify():
    try:
        client=redis_client()
        if client:client.lpush('pharmareg:jobs:wakeup','1');client.ltrim('pharmareg:jobs:wakeup',0,999)
    except Exception:log.warning('Redis wakeup unavailable; SQL polling retains jobs')
def dispatch(background,db,org_id,task,target_id):
    job=enqueue(db,org_id,task,target_id);db.commit();notify()
    if os.getenv('JOB_MODE','embedded') in {'inline','test-inline'}:background.add_task(execute,job.id)
    return job
def claim(identifier=None):
    now=int(time.time());lease=secrets.token_hex(24)
    with Session() as db:
        db.execute(update(ProcessingJob).where(ProcessingJob.state=='RUNNING',ProcessingJob.lease_until<now,ProcessingJob.attempts>=ProcessingJob.max_attempts).values(state='FAILED',error='Worker lease expired after maximum attempts'))
        db.commit()
        eligible=or_(ProcessingJob.state.in_(['QUEUED','RETRY']), (ProcessingJob.state=='RUNNING') & (ProcessingJob.lease_until<now))
        statement=select(ProcessingJob).where(eligible,ProcessingJob.available_at<=now,ProcessingJob.attempts<ProcessingJob.max_attempts).order_by(ProcessingJob.created_at)
        if identifier:statement=statement.where(ProcessingJob.id==identifier)
        candidate=db.scalar(statement.limit(1))
        if not candidate:return None
        result=db.execute(update(ProcessingJob).where(ProcessingJob.id==candidate.id,eligible,ProcessingJob.attempts==candidate.attempts).values(state='RUNNING',attempts=ProcessingJob.attempts+1,lease_until=now+120,lease_token=lease))
        if result.rowcount!=1:db.rollback();return None
        db.commit();return candidate.id,lease
def heartbeat(identifier,lease,stop):
    while not stop.wait(20):
        if os.getenv('JOB_MODE')=='worker':
            import tempfile
            from pathlib import Path
            (Path(tempfile.gettempdir())/'pharmareg-worker-heartbeat').write_text(str(time.time()))
        with Session() as db:
            db.execute(update(ProcessingJob).where(ProcessingJob.id==identifier,ProcessingJob.lease_token==lease,ProcessingJob.state=='RUNNING').values(lease_until=int(time.time())+120));db.commit()
def execute(identifier=None):
    claimed=claim(identifier)
    if not claimed:return False
    identifier,lease=claimed;stop=threading.Event();thread=threading.Thread(target=heartbeat,args=(identifier,lease,stop),daemon=True);thread.start()
    try:
        with Session() as db:
            job=db.get(ProcessingJob,identifier);task,target=job.task,job.target_id
        if task=='document':
            from app.services.document_service import process_document
            process_document(target)
        elif task=='assessment':
            from app.services.compliance_service import run_assessment
            run_assessment(target)
        elif task=='reindex':
            from app.services.index_service import reindex_document
            reindex_document(target)
        else:raise ValueError('Unknown durable task')
        with Session() as db:
            record=db.get(Document,target) if task in {'document','reindex'} else db.get(Assessment,target)
            if not record:raise ValueError('Job target no longer exists')
            if record.status.lower()=='failed':raise ValueError(record.error)
            db.execute(update(ProcessingJob).where(ProcessingJob.id==identifier,ProcessingJob.lease_token==lease).values(state='SUCCEEDED',lease_until=0,error='',progress={'completed':True}));db.commit()
    except Exception as exc:
        with Session() as db:
            job=db.get(ProcessingJob,identifier)
            if job.lease_token==lease:
                job.error=str(exc)[:4000];job.state='FAILED' if job.attempts>=job.max_attempts else 'RETRY';job.available_at=int(time.time())+min(300,2**job.attempts);job.lease_until=0;db.commit()
        log.exception('Durable job failed: %s',identifier)
    finally:stop.set();thread.join(timeout=2)
    return True
