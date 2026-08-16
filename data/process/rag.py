"""Preparación semántica e indexación Qdrant de la base comercial de Nexova."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from openai import AsyncOpenAI, OpenAI
from qdrant_client import QdrantClient, models


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIRECTORY = REPO_ROOT / "docs" / "company-knowledge-base"
COLLECTION_NAME = "nexova_knowledge"
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DOCUMENTS = {
    "nexova-service-lines.es.md": "service-lines",
    "nexova-pricing-model.es.md": "pricing-model",
    "nexova-hiring-process-sla.es.md": "hiring-process-sla",
    "nexova-objection-handling.es.md": "objection-handling",
}


@dataclass(frozen=True)
class KnowledgeChunk:
    """Unidad semántica autocontenida que se conserva como payload en Qdrant."""

    id: str
    source_document: str
    section: str
    company: str
    language: str
    chunk_index: int
    text: str

    def payload(self) -> dict[str, str | int]:
        payload = asdict(self)
        payload.pop("id")
        return payload


def _merge_short_blocks(blocks: list[str], minimum_length: int = 80) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(blocks):
        current = blocks[index]
        if len(current) < minimum_length and index + 1 < len(blocks):
            current = f"{current}\n\n{blocks[index + 1]}"
            index += 1
        merged.append(current)
        index += 1
    return merged


def _semantic_blocks(markdown: str) -> tuple[str, list[str]]:
    """Divide sólo en blancos entre unidades; nunca corta una regla o condición."""

    title = "Documento de Nexova"
    body_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("# ") and title == "Documento de Nexova":
            title = line.removeprefix("# ").strip()
        elif not line.startswith("# "):
            body_lines.append(line.rstrip())
    body = "\n".join(body_lines).strip()
    blocks = [re.sub(r"\n{3,}", "\n\n", item.strip()) for item in re.split(r"\n\s*\n", body)]
    return title, _merge_short_blocks([item for item in blocks if item])


def _section_name(title: str, block: str, index: int) -> str:
    first_line = block.splitlines()[0].strip().strip('"')
    first_line = re.sub(r"^[-*]\s+", "", first_line)
    first_line = re.sub(r"^\d+\.\s+", "", first_line)
    if first_line.endswith(":"):
        first_line = first_line[:-1]
    if len(first_line) < 12 or first_line.lower().startswith(("nexova opera", "tiempos de")):
        return f"{title} — bloque {index + 1}"
    return first_line[:120]


def load_chunks(corpus_directory: Path = CORPUS_DIRECTORY) -> list[KnowledgeChunk]:
    """Carga los cuatro documentos requeridos y genera IDs deterministas."""

    chunks: list[KnowledgeChunk] = []
    missing = [name for name in DOCUMENTS if not (corpus_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Faltan documentos de conocimiento: {', '.join(missing)}")

    for filename, source_document in DOCUMENTS.items():
        title, blocks = _semantic_blocks((corpus_directory / filename).read_text(encoding="utf-8"))
        if len(blocks) < 3:
            raise ValueError(f"{filename} debe producir al menos tres chunks semánticos")
        for chunk_index, block in enumerate(blocks):
            text = f"# {title}\n\n{block}"
            identity = f"nexova:{source_document}:{chunk_index}:{text}"
            chunks.append(
                KnowledgeChunk(
                    id=str(uuid5(NAMESPACE_URL, identity)),
                    source_document=source_document,
                    section=_section_name(title, block, chunk_index),
                    company="nexova",
                    language="es",
                    chunk_index=chunk_index,
                    text=text,
                )
            )
    return chunks


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return OpenAI(timeout=30.0, max_retries=2)


@lru_cache(maxsize=1)
def get_async_openai_client() -> AsyncOpenAI:
    """Cliente asíncrono para cerrar el stream HTTP al cancelar una generación."""

    return AsyncOpenAI(timeout=30.0, max_retries=2)


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL")
    if url:
        return QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"), timeout=10)
    path = Path(os.getenv("QDRANT_PATH", str(REPO_ROOT / "data" / "qdrant"))).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))


def embed(text: str) -> list[float]:
    """Genera un vector con el modelo exclusivo de embeddings configurado."""

    normalized = " ".join(text.split())
    if not normalized:
        raise ValueError("No se puede generar un embedding de texto vacío")
    response = get_openai_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=normalized,
        encoding_format="float",
    )
    vector = list(response.data[0].embedding)
    if not vector:
        raise RuntimeError("El proveedor devolvió un embedding vacío")
    return vector


def setup() -> dict[str, Any]:
    """Recrea e indexa la colección completa; repetir no duplica puntos."""

    chunks = load_chunks()
    vectors = [embed(chunk.text) for chunk in chunks]
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        raise RuntimeError("Los embeddings no comparten una dimensión estable")

    client = get_qdrant_client()
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
    )
    client.upsert(
        collection_name=COLLECTION_NAME,
        wait=True,
        points=[
            models.PointStruct(id=chunk.id, vector=vector, payload=chunk.payload())
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )
    per_document = {
        source: sum(chunk.source_document == source for chunk in chunks)
        for source in DOCUMENTS.values()
    }
    return {
        "collection": COLLECTION_NAME,
        "chunk_count": len(chunks),
        "vector_dimension": dimension,
        "embedding_model": EMBEDDING_MODEL,
        "chunks_per_document": per_document,
    }
