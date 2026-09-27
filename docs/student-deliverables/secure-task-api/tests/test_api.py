from fastapi.testclient import TestClient
from app.main import app, tasks

client = TestClient(app)

def setup_function():
    tasks.clear()

def login():
    r = client.post('/auth/login', data={'username':'demo@example.com','password':'correct-horse-battery-staple'})
    assert r.status_code == 200
    return {'Authorization': f"Bearer {r.json()['access_token']}"}

def test_health_is_public():
    assert client.get('/health').json() == {'status':'ok'}

def test_login_and_owner_scoped_tasks():
    headers = login()
    created = client.post('/tasks', headers=headers, json={'title':'Ship API'}).json()
    assert created['owner_id'] == 1
    assert client.get('/tasks', headers=headers).json()[0]['title'] == 'Ship API'

def test_invalid_token_is_rejected():
    r = client.get('/tasks', headers={'Authorization':'Bearer invalid'})
    assert r.status_code == 401

def test_validation_rejects_empty_title():
    r = client.post('/tasks', headers=login(), json={'title':''})
    assert r.status_code == 422
