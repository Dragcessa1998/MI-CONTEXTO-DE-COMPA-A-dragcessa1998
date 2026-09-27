from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_and_readiness():
    assert client.get('/health').json() == {'status':'ok'}
    assert client.get('/ready').json()['status'] == 'ready'

def test_request_is_observable():
    response = client.get('/hello?name=Franchesco')
    assert response.json()['message'] == 'Hello, Franchesco!'
    assert 'X-Request-Duration-Ms' in response.headers
    assert 'http_requests_total' in client.get('/metrics').text
