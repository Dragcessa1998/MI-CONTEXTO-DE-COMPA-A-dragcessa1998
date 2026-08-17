from fastapi.testclient import TestClient

import routes.agent as agent_routes


def test_agent_endpoint_is_thin_and_returns_run_id(
    client: TestClient, monkeypatch,
) -> None:
    monkeypatch.setattr(
        agent_routes,
        "run_agent",
        lambda question: {
            "run_id": "run-123",
            "answer": f"Respuesta trazable para: {question}",
            "trace": [],
        },
    )
    response = client.post(
        "/agent/query",
        json={"question": "¿Qué incluye headhunting?"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-123",
        "conversation_id": "support-user-1",
        "answer": "Respuesta trazable para: ¿Qué incluye headhunting?",
        "memory_proposal": None,
        "memory_decision": None,
        "recalled_memories": [],
    }


def test_agent_endpoint_hides_internal_errors(
    client: TestClient, monkeypatch,
) -> None:
    monkeypatch.setattr(
        agent_routes,
        "run_agent",
        lambda _question: (_ for _ in ()).throw(RuntimeError("secret-provider-path")),
    )
    response = client.post("/agent/query", json={"question": "precio"})
    assert response.status_code == 503
    assert response.json() == {
        "detail": "El agente de soporte no está disponible temporalmente."
    }
    assert "secret" not in response.text and "provider" not in response.text


def test_trace_endpoint_returns_consultable_events(
    client: TestClient, monkeypatch,
) -> None:
    trace = {
        "run_id": "trace-1",
        "started_at": "2026-08-12T10:00:00+00:00",
        "completed_at": "2026-08-12T10:00:01+00:00",
        "events": [{"sequence": 1, "node": "receive_question", "output": {}}],
    }
    monkeypatch.setattr(agent_routes.trace_store, "get", lambda run_id: trace if run_id == "trace-1" else None)
    assert client.get("/agent/traces/trace-1").json() == trace
    assert client.get("/agent/traces/missing").status_code == 404
