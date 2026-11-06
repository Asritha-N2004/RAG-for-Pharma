import os, sys, tempfile
from pathlib import Path
test_root=Path(__file__).resolve().parents[2]/'storage'/'tests'
test_root.mkdir(parents=True,exist_ok=True)
os.environ['STORAGE_DIR']=tempfile.mkdtemp(prefix='run-',dir=test_root)
os.environ['DATABASE_URL']='sqlite:///'+str(Path(os.environ['STORAGE_DIR'])/'test.db')
os.environ['LLM_PROVIDER']='local-extractive'
os.environ['JOB_MODE']='test-inline'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from app.db.database import Base,engine
from app.main import app,requests

@pytest.fixture
def client():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);requests.clear()
    with TestClient(app) as client: yield client

def account(client,email='reviewer@example.com'):
    response=client.post('/api/auth/register',json={'email':email,'password':'A-secure-password-123','name':'Test reviewer','organization':'DEMONSTRATION DATA organization'})
    assert response.status_code==201,response.text
    return {'Authorization':'Bearer '+response.json()['access_token']}
