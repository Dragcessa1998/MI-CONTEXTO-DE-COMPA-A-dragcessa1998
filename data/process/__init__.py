"""Preparación e indexación de fuentes de datos."""

from .rag import COLLECTION_NAME, KnowledgeChunk, embed, load_chunks, setup

__all__ = ["COLLECTION_NAME", "KnowledgeChunk", "embed", "load_chunks", "setup"]
