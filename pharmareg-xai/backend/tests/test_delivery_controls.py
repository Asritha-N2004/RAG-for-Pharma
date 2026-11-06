from conftest import account

def test_smtp_delivery_uses_starttls_without_exposing_token(client,monkeypatch):
    from app.services import mail_service
    sent=[]
    class SMTP:
        def __init__(self,*a,**k):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def starttls(self,context):sent.append('TLS')
        def login(self,*a):sent.append('AUTH')
        def send_message(self,message):sent.append(message)
    h=account(client)
    monkeypatch.setattr(mail_service.smtplib,'SMTP',SMTP)
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('SMTP_HOST','smtp.fixture.invalid');monkeypatch.setenv('SMTP_FROM','noreply@example.com')
    result=client.post('/api/auth/password-reset/request',json={'email':'reviewer@example.com'})
    assert result.status_code==200 and 'token' not in result.json()
    assert sent[0]=='TLS' and sent[1]['To']=='reviewer@example.com'
def test_redis_limiter_can_fail_closed(client,monkeypatch):
    from app.services import job_service
    h=account(client)
    class Redis:
        def eval(self,*a):return 999
    monkeypatch.setenv('REDIS_URL','redis://fixture.invalid');monkeypatch.setattr(job_service,'redis_client',lambda:Redis())
    assert client.get('/api/settings',headers=h).status_code==429
    class Unavailable:
        def eval(self,*a):raise ConnectionError('fixture unavailable')
    monkeypatch.setattr(job_service,'redis_client',lambda:Unavailable());monkeypatch.setenv('REDIS_REQUIRED','true')
    assert client.get('/api/settings',headers=h).status_code==503
    assert client.get('/health').status_code==200
