from datetime import datetime
from zoneinfo import ZoneInfo
import os
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.entities import User,Capa,Finding,ProcessingJob,Notification,Setting
REVIEW={'System Administrator','Regulatory Affairs Specialist','Quality Assurance Manager','Compliance Auditor'}
def local_day():return datetime.now(ZoneInfo(os.getenv('APP_TIMEZONE','Asia/Kolkata'))).date()
def preferences(db,user):
    row=db.scalar(select(Setting).where(Setting.org_id==user.org_id,Setting.key=='notifications:'+user.id))
    return row.value if row else {'due_in_days':7,'pending_reviews':True,'failed_jobs':True,'enabled':True}
def add(db,user,key,title,message,link):
    if db.scalar(select(Notification.id).where(Notification.user_id==user.id,Notification.event_key==key)):return
    try:
        with db.begin_nested():db.add(Notification(org_id=user.org_id,user_id=user.id,event_key=key,title=title[:250],message=message,link=link));db.flush()
    except IntegrityError:pass
def sync(db,user):
    prefs=preferences(db,user)
    if not prefs['enabled']:return
    today=local_day()
    if user.role in REVIEW:
        for capa in db.scalars(select(Capa).where(Capa.org_id==user.org_id,Capa.status!='CLOSED')):
            try:due=__import__('datetime').date.fromisoformat(capa.data['due_date'])
            except (ValueError,KeyError,TypeError):continue
            days=(due-today).days
            if days<=prefs['due_in_days']:
                add(db,user,f'capa:{capa.id}:{due}:{today}',('Overdue CAPA: ' if days<0 else 'CAPA due soon: ')+capa.title,f'Due {due.isoformat()}; status {capa.status}. Review implementation and effectiveness evidence.','/capa')
        if prefs['pending_reviews']:
            for finding in db.scalars(select(Finding).where(Finding.org_id==user.org_id,Finding.review_status.in_(['PENDING','EVIDENCE_REQUESTED','INVESTIGATING']))):
                add(db,user,f'finding:{finding.id}:{finding.review_status}','Finding needs review',finding.original['requirement_text'][:1000],'/findings/'+finding.id)
    if prefs['failed_jobs'] and user.role in REVIEW|{'Document Manager'}:
        for job in db.scalars(select(ProcessingJob).where(ProcessingJob.org_id==user.org_id,ProcessingJob.state=='FAILED')):
            add(db,user,f'job:{job.id}:{job.attempts}','Processing job failed',job.error[:1000],'/assessments/'+job.target_id if job.task=='assessment' else '/documents/'+job.target_id)
def sync_all(db):
    for user in db.scalars(select(User)):sync(db,user)
