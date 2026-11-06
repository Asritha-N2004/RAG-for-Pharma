import time,argparse,logging
from app.db.database import Session
from app.services.notification_service import sync_all
def once():
    with Session() as db:sync_all(db);db.commit()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    while True:
        try:once()
        except Exception:logging.exception('Reminder generation failed')
        if args.once:break
        time.sleep(60)
