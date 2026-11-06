import json
from conftest import account
from app.core.config import STORAGE

def test_member_role_and_profile(client):
    h=account(client)
    r=client.post('/api/users',headers=h,json={'name':'Document Manager','email':'manager@example.com','password':'New-member-password-123','role':'Document Manager'})
    assert r.status_code==201,r.text
    login=client.post('/api/auth/login',json={'email':'manager@example.com','password':'New-member-password-123'}).json()
    mh={'Authorization':'Bearer '+login['access_token']}
    assert client.get('/api/users',headers=mh).status_code==403
    assert client.patch('/api/auth/me',headers=mh,json={'name':'Updated profile'}).json()['name']=='Updated profile'
    assert client.post('/api/documents/upload',headers=mh,files={'file':('sample.txt',b'DEMONSTRATION DATA training records')}).status_code==201

def test_password_recovery_revokes_sessions(client):
    h=account(client)
    assert client.post('/api/auth/password-reset/request',json={'email':'reviewer@example.com'}).status_code==200
    messages=[json.loads(p.read_text()) for p in (STORAGE/'outbox').glob('*.json')]
    token=messages[-1]['token']
    r=client.post('/api/auth/password-reset/confirm',json={'token':token,'password':'New-reset-password-123'})
    assert r.status_code==200,r.text
    assert client.get('/api/auth/me',headers=h).status_code==401
    assert client.post('/api/auth/password-reset/confirm',json={'token':token,'password':'Another-password-123'}).status_code==400
    assert client.post('/api/auth/login',json={'email':'reviewer@example.com','password':'New-reset-password-123'}).status_code==200

def test_risk_matrix_isolation(client):
    a=account(client,'risk-a@example.com');b=account(client,'risk-b@example.com')
    assert client.patch('/api/settings/risk-matrix',headers=a,json={'medium':10,'high':30,'critical':60}).status_code==200
    assert client.get('/api/settings/risk-matrix',headers=a).json()['critical']==60
    assert client.get('/api/settings/risk-matrix',headers=b).json()['critical']==80
    assert client.patch('/api/settings/risk-matrix',headers=a,json={'medium':50,'high':30,'critical':60}).status_code==422
