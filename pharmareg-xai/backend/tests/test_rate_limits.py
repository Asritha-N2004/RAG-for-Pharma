def test_auth_rate_limits_do_not_block_static_ui(client):
    from app.main import requests
    requests.clear()
    for _ in range(20):
        assert client.post('/api/auth/login',json={'email':'absent@example.com','password':'Not-a-valid-password-123'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'absent@example.com','password':'Not-a-valid-password-123'}).status_code==429
    assert client.get('/health').status_code==200
    assert client.get('/').status_code==200
    assert client.get('/api/auth/oidc/config').status_code==200
    requests.clear()
