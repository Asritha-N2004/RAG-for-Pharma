"""Run a real PostgreSQL FK/audit-lock concurrency regression on an isolated fixture org."""
import json,os,sys,secrets,threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1];config=dotenv_values(root/'storage/vercel-deploy/.env.local');os.environ['DATABASE_URL']=config['DATABASE_URL'];os.environ.update(json.loads((root/'storage/cloud-runtime.json').read_text()));sys.path.insert(0,str(root/'backend'))
from app.db.database import Session
from app.models.entities import Organization,User,Notification
from app.services.audit_service import append,verify
from app.core.security import hasher
with Session() as db:
    org=Organization(name='DEMONSTRATION isolated PostgreSQL concurrency test');db.add(org);db.flush();user=User(org_id=org.id,name='Concurrency fixture',email='pg-audit-'+secrets.token_hex(12)+'@example.com',password=hasher.hash(secrets.token_urlsafe(32)));db.add(user);db.commit();oid=org.id;uid=user.id
barrier=threading.Barrier(2)
def concurrent(index):
    with Session() as db:
        user=db.get(User,uid)
        # Flushing a child takes a PostgreSQL KEY SHARE lock on its organization.
        db.add(Notification(org_id=oid,user_id=uid,event_key='fixture-'+str(index),title='Controlled concurrency test',message='Synthetic data only',link='/validation'));db.flush();barrier.wait(timeout=30)
        append(db,user,'CONCURRENCY_FIXTURE',str(index),{'synthetic':True});db.commit()
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(concurrent,range(2)))
with Session() as db:
    result=verify(db,oid);assert result['valid'] and result['sealed_records']==2,result
output={'passed':True,'database':'actual Neon PostgreSQL','concurrent_child_and_audit_transactions':2,'audit_chain_valid':True,'lock':'FOR NO KEY UPDATE','fixture_organization_id':oid}
(root/'docs/POSTGRES_AUDIT_RESULTS.json').write_text(json.dumps(output,indent=2),encoding='utf-8');print('Actual PostgreSQL concurrent FK/audit transactions passed; chain valid.')
