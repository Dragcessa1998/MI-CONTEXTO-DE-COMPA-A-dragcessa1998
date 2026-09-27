from fastapi.testclient import TestClient
from app.main import app, jobs

client = TestClient(app)

def setup_function():
    jobs.clear()

def test_health():
    assert client.get('/health').json() == {'status':'ok'}

def test_job_is_accepted_and_finishes():
    created = client.post('/jobs', json={'text':'hello async'} )
    assert created.status_code == 202
    job_id = created.json()['id']
    result = client.get(f'/jobs/{job_id}')
    assert result.status_code == 200
    assert result.json()['state'] == 'completed'
    assert result.json()['result'] == 'HELLO ASYNC'

def test_validation_and_missing_job():
    assert client.post('/jobs', json={'text':''}).status_code == 422
    assert client.get('/jobs/does-not-exist').status_code == 404
