import os,shutil
from pathlib import Path
from fastapi import APIRouter,Depends,Request
from sqlalchemy import text
from app.db.database import get_db
from app.core.security import current_user,permit
router=APIRouter(prefix='/api/system')
@router.get('/readiness')
def readiness(request:Request,user=Depends(current_user),db=Depends(get_db)):
    permit(user,{'System Administrator'})
    checks={}
    try:db.execute(text('SELECT 1'));checks['database']={'status':'VERIFIED','engine':db.bind.dialect.name}
    except Exception:checks['database']={'status':'FAILED'}
    if os.getenv('REDIS_URL'):
        try:
            from app.services.job_service import redis_client
            checks['redis']={'status':'VERIFIED' if redis_client().ping() else 'FAILED'}
        except Exception:checks['redis']={'status':'FAILED'}
    else:checks['redis']={'status':'NOT_CONFIGURED','alternative':'Durable SQL queue and local rate limits'}
    if os.getenv('VECTOR_STORE')=='chroma':
        try:
            from app.services.vector_store_service import client
            client().heartbeat();checks['vector_store']={'status':'VERIFIED','mode':os.getenv('CHROMA_MODE','http')}
        except Exception:checks['vector_store']={'status':'FAILED'}
    else:checks['vector_store']={'status':'VERIFIED','mode':'SQL-backed vectors'}
    checks['processing']={'status':'CONFIGURED','mode':os.getenv('JOB_MODE','embedded'),'note':'Request-driven jobs resume during status polling and are subject to the function duration limit.' if os.getenv('JOB_MODE')=='inline' else 'Separate worker availability must be checked with the hosting provider.'}
    checks['file_encryption']={'status':'CONFIGURED' if os.getenv('ENCRYPT_STORAGE','false')=='true' else 'NOT_CONFIGURED','scope':'Original documents, CAPA attachments and generated report files; database-volume encryption remains an infrastructure control.'}
    checks['smtp']={'status':'CONFIGURED' if all(os.getenv(k) for k in ['SMTP_HOST','SMTP_FROM']) else 'NOT_CONFIGURED','note':'No test message is sent by this check.'}
    import json
    try:
        command=json.loads(os.getenv('MALWARE_SCANNER_COMMAND') or '[]');executable=command[0] if command else ''
        scanner=bool(executable and (Path(executable).is_file() or shutil.which(executable)))
    except Exception:scanner=False
    checks['malware_scanner']={'status':'CONFIGURED' if scanner else 'NOT_CONFIGURED','required':os.getenv('REQUIRE_MALWARE_SCAN','false')=='true'}
    checks['https']={'status':'VERIFIED' if request.url.scheme=='https' else 'NOT_OBSERVED','note':'External TLS termination must be verified from the public deployment endpoint.'}
    checks['oidc']={'status':'CONFIGURED' if all(os.getenv(k) for k in ['OIDC_ISSUER','OIDC_CLIENT_ID','OIDC_REDIRECT_URI']) else 'NOT_CONFIGURED'}
    checks['domain_and_regulatory_validation']={'status':'HUMAN_REVIEW_REQUIRED','note':'Use the release validation page to record qualified evidence and sign-off. Automated service checks do not certify legal or regulatory suitability.'}
    return {'checks':checks,'service_failures':[k for k,v in checks.items() if v['status']=='FAILED'],'production_certified':False}
