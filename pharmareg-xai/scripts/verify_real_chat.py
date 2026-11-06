import os,sys,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];storage=root/'storage'/'real-chat-verification';storage.mkdir(parents=True,exist_ok=True)
os.environ.update(STORAGE_DIR=str(storage),DATABASE_URL='sqlite:///'+str(storage/'pharmareg.db'),LLM_PROVIDER='local-openai',LLM_MODEL='llama3.2:1b',OPENAI_BASE_URL='http://localhost:11434/v1',LLM_TIMEOUT='240',EMBEDDING_PROVIDER='hash-local',EMBEDDING_MODEL='sha256-feature-hash-v1',VECTOR_STORE='sql',JOB_MODE='test-inline')
sys.path.insert(0,str(root/'backend'));os.chdir(root/'backend')
from alembic import command
from alembic.config import Config
command.upgrade(Config('alembic.ini'),'head')
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    r=client.post('/api/auth/register',json={'name':'Controlled generative chat','organization':'DEMONSTRATION DATA real chat','email':f'chat-{time.time_ns()}@example.com','password':'Real-chat-password-123'});assert r.status_code==201,r.text
    h={'Authorization':'Bearer '+r.json()['access_token']}
    doc=client.post('/api/documents/upload',headers=h,files={'file':('DEMONSTRATION-training.txt',b'DEMONSTRATION DATA\nThe Quality Assurance manager retains signed training records. Operators receive training before operating equipment.')});assert doc.status_code==201,doc.text
    session=client.post('/api/conversations',headers=h,json={'title':'Controlled training record conversation'}).json()
    results=[]
    for question in ['Who retains signed training records?','When do operators receive training?']:
        response=client.post('/api/conversations/'+session['id']+'/messages',headers=h,json={'query':question,'document_ids':[doc.json()['id']],'top_k':2});assert response.status_code==200,response.text
        results.append(response.json()['response'])
    history=client.get('/api/conversations/'+session['id'],headers=h).json();assert len(history['turns'])==2
    output={'real_model':'llama3.2:1b','validated_turns':len(results),'responses':results}
    (root/'docs'/'REAL_CHAT_RESULTS.json').write_text(json.dumps(output,indent=2),encoding='utf-8');print(json.dumps({'real_model':output['real_model'],'validated_turns':len(results)},indent=2))
