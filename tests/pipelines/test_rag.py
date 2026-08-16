from __future__ import annotations

from collections import Counter
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from data.pipelines import rag as pipeline_rag
from data.process import rag as process_rag


ROOT = Path(__file__).resolve().parents[2]


def test_all_context_documents_produce_at_least_three_semantic_chunks() -> None:
    chunks = process_rag.load_chunks()
    counts = Counter(chunk.source_document for chunk in chunks)

    assert set(counts) == set(process_rag.DOCUMENTS.values())
    assert all(count >= 3 for count in counts.values())
    assert len({chunk.id for chunk in chunks}) == len(chunks)
    assert all(chunk.company == "nexova" and chunk.language == "es" for chunk in chunks)
    assert all(chunk.section and chunk.text for chunk in chunks)


def test_embed_uses_dedicated_model_and_rejects_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class Embeddings:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.2, 0.4])])

    monkeypatch.setattr(
        process_rag,
        "get_openai_client",
        lambda: SimpleNamespace(embeddings=Embeddings()),
    )

    assert process_rag.embed(" texto\n comercial ") == [0.2, 0.4]
    assert captured == {
        "model": process_rag.EMBEDDING_MODEL,
        "input": "texto comercial",
        "encoding_format": "float",
    }
    assert process_rag.EMBEDDING_MODEL != pipeline_rag.GENERATION_MODEL
    with pytest.raises(ValueError, match="vacío"):
        process_rag.embed("   ")


def test_retrieve_applies_threshold_and_returns_payloads_not_sdk_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict = {}
    payload = {
        "source_document": "pricing-model",
        "section": "Formación corporativa",
        "company": "nexova",
        "language": "es",
        "chunk_index": 2,
        "text": "Programa de 8 semanas: desde 6.200 USD.",
    }

    class Qdrant:
        def query_points(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(points=[SimpleNamespace(payload=payload, score=0.82)])

    monkeypatch.setattr(pipeline_rag, "embed", lambda _question: [0.1, 0.2])
    monkeypatch.setattr(pipeline_rag, "get_qdrant_client", lambda: Qdrant())

    result = pipeline_rag.retrieve("¿Cuánto cuesta?", k=3, min_score=0.51)

    assert result == [payload]
    assert calls["limit"] == 3
    assert calls["score_threshold"] == 0.51
    assert calls["with_payload"] is True
    assert "score" not in result[0]


def test_query_calls_retrieve_then_generation_once_with_same_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    context = [{"text": "Garantía de seis meses"}]

    def fake_retrieve(question: str):
        calls.append(("retrieve", question))
        return context

    def fake_generate(question: str, supplied_context: list[dict]):
        calls.append(("generate", supplied_context))
        assert question == "¿Qué garantía existe?"
        return "La garantía contractual es de seis meses."

    monkeypatch.setattr(pipeline_rag, "retrieve", fake_retrieve)
    monkeypatch.setattr(pipeline_rag, "generate_answer", fake_generate)

    answer = pipeline_rag.query("¿Qué garantía existe?")

    assert answer == "La garantía contractual es de seis meses."
    assert calls == [("retrieve", "¿Qué garantía existe?"), ("generate", context)]
    assert answer != context[0]["text"]


def test_generate_answer_uses_responses_api_and_handles_no_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text=pipeline_rag.NO_CONTEXT_ANSWER)

    monkeypatch.setattr(
        pipeline_rag,
        "get_openai_client",
        lambda: SimpleNamespace(responses=Responses()),
    )

    answer = pipeline_rag.generate_answer("¿Tenéis oficina en Tokio?", [])

    assert answer == pipeline_rag.NO_CONTEXT_ANSWER
    assert captured["model"] == pipeline_rag.GENERATION_MODEL
    assert "[SIN CONTEXTO RELEVANTE]" in captured["input"]
    assert "exclusivamente" in captured["instructions"]


def test_generate_answer_stream_forwards_provider_deltas_and_closes_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class Stream:
        closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            self.closed = True

        def __aiter__(self):
            async def events():
                yield SimpleNamespace(type="response.output_text.delta", delta="Hola ")
                yield SimpleNamespace(type="response.output_text.delta", delta="en vivo")

            return events()

    stream = Stream()

    class Responses:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return stream

    monkeypatch.setattr(
        pipeline_rag,
        "get_async_openai_client",
        lambda: SimpleNamespace(responses=Responses()),
    )

    async def collect() -> list[str]:
        return [chunk async for chunk in pipeline_rag.generate_answer_stream(
            "¿Qué incluye?",
            [{"source_document": "service-lines", "section": "Soporte", "text": "SLA de 24 horas"}],
        )]

    assert asyncio.run(collect()) == ["Hola ", "en vivo"]
    assert captured["model"] == pipeline_rag.GENERATION_MODEL
    assert stream.closed is True


def test_eval_file_covers_every_source_and_two_or_more_objections() -> None:
    import json

    rows = json.loads((ROOT / "data" / "eval" / "test-queries.json").read_text())
    counts = Counter(row["expected_source_document"] for row in rows)

    assert len(rows) >= 8
    assert set(counts) == set(process_rag.DOCUMENTS.values())
    assert counts["objection-handling"] >= 2
