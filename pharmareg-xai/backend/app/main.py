import logging, time, os, threading
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.api.workflows import router as workflow_router
from app.api.research import router as research_router
from app.api.conversations import router as conversation_router
from app.api.identity import router as identity_router
from app.api.sso import router as sso_router
from app.api.notifications import router as notification_router
from app.api.signatures import router as signature_router
from app.api.validation import router as validation_router
from app.api.readiness import router as readiness_router
from app.db.database import Session
from app.models.entities import Document, Assessment
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
@asynccontextmanager
async def lifespan(app):
    stop=threading.Event();worker=None
    if os.getenv('JOB_MODE','embedded')=='embedded':
        def loop():
            from app.services.job_service import execute
            last_notifications=0
            while not stop.is_set():
                try:
                    if time.time()-last_notifications>=60:
                        from app.workers.notifications import once
                        once();last_notifications=time.time()
                    if not execute():stop.wait(1)
                except Exception:logging.exception('Embedded durable worker failed');stop.wait(2)
        worker=threading.Thread(target=loop,daemon=True);worker.start()
    yield
    stop.set()
    if worker:worker.join(timeout=3)
app=FastAPI(title='PharmaReg-XAI',version='0.1.0',lifespan=lifespan)
app.include_router(router)
app.include_router(workflow_router)
app.include_router(research_router)
app.include_router(conversation_router)
app.include_router(identity_router)
app.include_router(sso_router)
app.include_router(notification_router)
app.include_router(signature_router)
app.include_router(validation_router)
app.include_router(readiness_router)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Authorization','Content-Type'])
requests=defaultdict(deque)
@app.middleware('http')
async def security_headers(request:Request,call_next):
    sensitive_auth=request.url.path.startswith('/api/auth') and (request.method!='GET' or request.url.path.endswith('/oidc/start'))
    is_api=request.url.path.startswith('/api/')
    key=(request.client.host if request.client else 'unknown', 'auth' if sensitive_auth else 'api')
    limit=20 if sensitive_auth else max(60,int(os.getenv('API_RATE_LIMIT_PER_MINUTE','600')))
    if is_api and os.getenv('REDIS_URL'):
        from app.services.job_service import redis_client
        from starlette.concurrency import run_in_threadpool
        import hashlib
        redis_key='pharmareg:rate:'+hashlib.sha256((key[0]+':'+key[1]).encode()).hexdigest()+':'+str(int(time.time())//60)
        try:
            count=await run_in_threadpool(redis_client().eval,"local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],65) end; return n",1,redis_key)
            if count>limit:return JSONResponse({'detail':'Rate limit exceeded'},status_code=429)
        except Exception:
            if os.getenv('REDIS_REQUIRED','false')=='true':return JSONResponse({'detail':'Rate limiting service temporarily unavailable'},status_code=503)
    queue=requests[key];now=time.monotonic()
    while queue and queue[0]<now-60: queue.popleft()
    if is_api and len(queue)>=limit: return JSONResponse({'detail':'Rate limit exceeded'},status_code=429)
    if is_api:queue.append(now)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'" if request.url.path not in {'/docs','/redoc'} else "frame-ancestors 'none'"
    if request.url.path.startswith('/api'): response.headers['Cache-Control']='no-store'
    return response
@app.exception_handler(Exception)
async def unhandled(request,exc):
    logging.exception('Unhandled request error',exc_info=exc)
    return JSONResponse({'detail':'Internal service error; see server logs'},status_code=500)
@app.exception_handler(ValueError)
async def invalid_operation(request,exc):
    return JSONResponse({'detail':str(exc)},status_code=422)
@app.get('/health')
def health(): return {'status':'ok'}
dist=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if dist.exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/{path:path}')
    def spa(path:str):
        if path.startswith('api/'): return JSONResponse({'detail':'Not found'},status_code=404)
        return FileResponse(dist/'index.html')
