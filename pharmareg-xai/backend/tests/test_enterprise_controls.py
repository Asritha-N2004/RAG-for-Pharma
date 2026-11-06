import json,time,base64,secrets
from urllib.parse import urlsplit,parse_qs
import httpx,jwt,pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from conftest import account
from test_workflow import setup_assessment,upload
from app.services.mfa_service import code

def test_totp_rfc_vector_and_recovery_login(client):
    assert code(base64.b32encode(b'12345678901234567890').decode(),1)=='287082'
    h=account(client);password='A-secure-password-123'
    enroll=client.post('/api/auth/mfa/enroll',headers=h,json={'password':password});assert enroll.status_code==200,enroll.text
    secret=enroll.json()['secret']
    confirm=client.post('/api/auth/mfa/confirm',headers=h,json={'code':code(secret)});assert confirm.status_code==200,confirm.text
    recovery=confirm.json()['recovery_codes'];assert len(set(recovery))==10
    assert client.get('/api/auth/me',headers=h).status_code==401
    assert client.post('/api/auth/login',json={'email':'reviewer@example.com','password':password}).status_code==401
    login=client.post('/api/auth/login',json={'email':'reviewer@example.com','password':password,'code':recovery[0]});assert login.status_code==200,login.text
    assert client.post('/api/auth/login',json={'email':'reviewer@example.com','password':password,'code':recovery[0]}).status_code==401
    refreshed={'Authorization':'Bearer '+login.json()['access_token']}
    assert client.get('/api/auth/mfa',headers=refreshed).json()['unused_recovery_codes']==9
    disabled=client.post('/api/auth/mfa/disable',headers=refreshed,json={'password':password,'code':recovery[1]});assert disabled.status_code==200,disabled.text
    new={'Authorization':'Bearer '+disabled.json()['access_token']}
    assert not client.get('/api/auth/mfa',headers=new).json()['enabled']

def oidc_fixture(client,monkeypatch,h):
    from app.services import oidc_service as oidc
    issuer='https://identity.example.test';monkeypatch.setenv('OIDC_ISSUER',issuer);monkeypatch.setenv('OIDC_CLIENT_ID','fixture-client');monkeypatch.setenv('OIDC_REDIRECT_URI','http://127.0.0.1:8010/auth/callback')
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048);public=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));public.update(kid='fixture-key',use='sig',alg='RS256')
    state={'nonce':'','audience':'fixture-client','subject':'verified-provider-subject'}
    def get(url,**kwargs):
        value={'issuer':issuer,'authorization_endpoint':issuer+'/authorize','token_endpoint':issuer+'/token','jwks_uri':issuer+'/jwks'} if url.endswith('configuration') else {'keys':[public]}
        return httpx.Response(200,json=value,request=httpx.Request('GET',url))
    def post(url,**kwargs):
        assert len(kwargs['data']['code_verifier'])>=43
        token=jwt.encode({'iss':issuer,'aud':state['audience'],'sub':state['subject'],'iat':int(time.time()),'exp':int(time.time())+120,'nonce':state['nonce']},key,algorithm='RS256',headers={'kid':'fixture-key'})
        return httpx.Response(200,json={'id_token':token},request=httpx.Request('POST',url))
    monkeypatch.setattr(oidc.httpx,'get',get);monkeypatch.setattr(oidc.httpx,'post',post)
    user=client.get('/api/auth/me',headers=h).json()
    link=client.post('/api/auth/oidc/links',headers=h,json={'user_id':user['id'],'subject':state['subject']});assert link.status_code==201,link.text
    return state
def begin(client,state):
    response=client.get('/api/auth/oidc/start');assert response.status_code==200,response.text
    query=parse_qs(urlsplit(response.json()['authorization_url']).query);state['nonce']=query['nonce'][0]
    assert query['code_challenge_method']==['S256']
    return query['state'][0]
def test_oidc_signature_nonce_pkce_browser_binding_and_replay(client,monkeypatch):
    h=account(client);state=oidc_fixture(client,monkeypatch,h);value=begin(client,state)
    response=client.post('/api/auth/oidc/exchange',json={'code':'fixture-code','state':value});assert response.status_code==200,response.text
    assert 'access_token' in response.json()
    assert client.post('/api/auth/oidc/exchange',json={'code':'fixture-code','state':value}).status_code==401
    value=begin(client,state);client.cookies.clear()
    assert client.post('/api/auth/oidc/exchange',json={'code':'fixture-code','state':value}).status_code==401
    value=begin(client,state);state['audience']='wrong-client'
    assert client.post('/api/auth/oidc/exchange',json={'code':'fixture-code','state':value}).status_code==401
def test_oidc_does_not_bypass_enabled_mfa(client,monkeypatch):
    h=account(client);state=oidc_fixture(client,monkeypatch,h)
    enrolled=client.post('/api/auth/mfa/enroll',headers=h,json={'password':'A-secure-password-123'}).json()
    enabled=client.post('/api/auth/mfa/confirm',headers=h,json={'code':code(enrolled['secret'])}).json()
    value=begin(client,state);challenge=client.post('/api/auth/oidc/exchange',json={'code':'fixture-code','state':value})
    assert challenge.status_code==200 and challenge.json()['mfa_required']
    result=client.post('/api/auth/oidc/mfa',json={'challenge_token':challenge.json()['challenge_token'],'code':enabled['recovery_codes'][0]})
    assert result.status_code==200 and 'access_token' in result.json()

def test_scope_exclusions_are_recorded_and_no_model_call_is_made(client,monkeypatch):
    h=account(client);identifier,reg,sop=setup_assessment(client,h)
    old=client.get('/api/compliance/assessments/'+identifier,headers=h).json();config=old['config'];rid=config['requirement_ids'][0]
    config['requirement_ids']=[];config['excluded_requirements']={rid:'Excluded because the documented assessment scope covers only packaging, not equipment operation.'}
    draft=client.post('/api/compliance/assessments',headers=h,json=config);assert draft.status_code==201,draft.text
    from app.services import compliance_service
    monkeypatch.setattr(compliance_service,'assess',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Excluded requirement must not call an LLM')))
    aid=draft.json()['id'];assert client.post('/api/compliance/assessments/'+aid+'/run',headers=h).status_code==200
    finding=client.get('/api/compliance/assessments/'+aid+'/findings',headers=h).json()[0]
    assert finding['original']['compliance_status']=='NOT_APPLICABLE'
    assert finding['original']['scope_evidence']['reviewer_id']==client.get('/api/auth/me',headers=h).json()['id']
    assert finding['review_status']=='PENDING'
def test_notifications_are_deduplicated_private_and_readable(client):
    h=account(client);identifier,reg,sop=setup_assessment(client,h)
    first=client.get('/api/notifications',headers=h).json();assert first['unread_count']>=1
    assert client.get('/api/notifications',headers=h).json()['total']==first['total']
    other=account(client,'other@example.com');nid=first['items'][0]['id']
    assert client.post('/api/notifications/'+nid+'/read',headers=other).status_code==404
    assert client.post('/api/notifications/'+nid+'/read',headers=h).status_code==200
    assert client.post('/api/notifications/read-all',headers=h).status_code==200
    assert client.get('/api/notifications',headers=h).json()['unread_count']==0
def test_reauthenticated_attestations_detect_subsequent_record_changes(client):
    h=account(client);identifier,reg,sop=setup_assessment(client,h)
    finding=client.get('/api/compliance/assessments/'+identifier+'/findings',headers=h).json()[0]
    payload={'target_type':'finding','target_id':finding['id'],'meaning':'REVIEWED','statement':'I reviewed the controlled source evidence and recorded the limitations.','consent':True,'password':'A-secure-password-123'}
    assert client.post('/api/signatures',headers=h,json={**payload,'password':'wrong'}).status_code==401
    signed=client.post('/api/signatures',headers=h,json=payload);assert signed.status_code==201,signed.text
    before=client.get('/api/signatures/finding/'+finding['id'],headers=h).json()[0];assert before['seal_valid'] and before['record_unchanged']
    client.post('/api/compliance/findings/'+finding['id']+'/review',headers=h,json={'decision':'EVIDENCE_REQUESTED','classification':'INSUFFICIENT_EVIDENCE','explanation':'Additional source evidence required after attestation.'})
    after=client.get('/api/signatures/finding/'+finding['id'],headers=h).json()[0];assert after['seal_valid'] and not after['record_unchanged']
