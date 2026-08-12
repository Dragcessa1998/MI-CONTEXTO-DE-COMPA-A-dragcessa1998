"""Conversión PDF→Markdown y métricas de costo de lectura."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from data.pipelines.rfp_intake.models import ReadabilityMetrics


def convert_pdf_to_markdown(pdf_path: Path) -> tuple[str, Path]:
    """Extrae texto página a página antes de que cualquier agente lo procese."""

    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Se requiere un archivo PDF existente")
    reader = PdfReader(pdf_path)
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"## Página {index}\n\n{text}")
    if not pages:
        raise ValueError("El PDF no contiene texto extraíble")
    markdown = f"# Documento recibido: {pdf_path.name}\n\n" + "\n\n".join(pages) + "\n"
    markdown_path = pdf_path.with_suffix(".md")
    markdown_path.write_text(markdown, encoding="utf-8")
    return markdown, markdown_path


def _syllables(word: str) -> int:
    groups = re.findall(r"[aeiouáéíóúü]+", word.lower())
    return max(1, len(groups))


def calculate_readability(markdown: str) -> ReadabilityMetrics:
    plain = re.sub(r"[#*_`>|-]", " ", markdown)
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", plain)
    sentences = [item for item in re.split(r"[.!?]+", plain) if item.strip()]
    word_count = len(words)
    sentence_count = max(1, len(sentences))
    syllable_count = sum(_syllables(word) for word in words)
    complex_count = sum(_syllables(word) >= 3 for word in words)
    words_per_sentence = word_count / sentence_count if word_count else 0
    syllables_per_word = syllable_count / word_count if word_count else 0
    flesch = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    fog = 0.4 * (words_per_sentence + 100 * complex_count / max(1, word_count))
    return ReadabilityMetrics(
        word_count=word_count,
        sentence_count=sentence_count,
        average_words_per_sentence=round(words_per_sentence, 2),
        flesch_reading_ease=round(flesch, 2),
        gunning_fog=round(fog, 2),
    )
