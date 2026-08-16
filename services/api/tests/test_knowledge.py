"""Contrato HTTP del adaptador RAG sin llamadas externas."""

from fastapi.testclient import TestClient

import routes.knowledge as knowledge_routes


def test_knowledge_endpoint_returns_only_generated_answer(
    client: TestClient, monkeypatch,
) -> None:
    monkeypatch.setattr(
        knowledge_routes,
        "query",
        lambda question: f"Respuesta comercial verificada para: {question}",
    )

    response = client.post(
        "/knowledge/query",
        json={"question": "¿Qué incluye headhunting?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Respuesta comercial verificada para: ¿Qué incluye headhunting?"
    }
    assert "chunks" not in response.text and "score" not in response.text


def test_knowledge_endpoint_validates_input(client: TestClient) -> None:
    assert client.post("/knowledge/query", json={"question": ""}).status_code == 422
    assert client.post(
        "/knowledge/query", json={"question": "válida", "internal": True}
    ).status_code == 422


def test_knowledge_endpoint_hides_provider_errors(
    client: TestClient, monkeypatch,
) -> None:
    def fail(_question: str) -> str:
        raise RuntimeError("sensitive-provider-detail-and-internal-vector-path")

    monkeypatch.setattr(knowledge_routes, "query", fail)
    response = client.post(
        "/knowledge/query",
        json={"question": "¿Qué precio tiene?"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "El asistente de conocimiento no está disponible temporalmente."
    }
    assert "secret" not in response.text and "vector" not in response.text
