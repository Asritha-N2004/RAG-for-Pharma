import logging,time,os,tempfile
from pathlib import Path
from app.services.job_service import execute,redis_client
logging.basicConfig(level=logging.INFO)
def main():
    heartbeat=Path(tempfile.gettempdir())/'pharmareg-worker-heartbeat'
    last_notifications=0
    while True:
        heartbeat.write_text(str(time.time()))
        if time.time()-last_notifications>=60:
            try:
                from app.workers.notifications import once
                once();last_notifications=time.time()
            except Exception:logging.exception('Reminder scheduler failed')
        if execute():continue
        try:
            client=redis_client()
            if client:client.brpop('pharmareg:jobs:wakeup',timeout=2)
            else:time.sleep(1)
        except Exception:time.sleep(1)
if __name__=='__main__':main()
