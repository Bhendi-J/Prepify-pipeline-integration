from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


class UnsupportedDocumentTypeError(ValueError):
    pass


class EmptyDocumentTextError(ValueError):
    pass


@dataclass(frozen=True)
class TextChunk:
    content: str
    token_count: int


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _extract_pdf_text(path)

    raise UnsupportedDocumentTypeError("Only .txt and .pdf uploads are supported")


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text.strip():
        raise EmptyDocumentTextError(
            "This PDF does not contain extractable text. Scanned PDFs need OCR support."
        )
    return text


def chunk_text(
    text: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[TextChunk]:
    words = text.split()
    if not words:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk_words = words[start:end]
        chunks.append(
            TextChunk(content=" ".join(chunk_words), token_count=len(chunk_words))
        )

        if end == len(words):
            break
        start = max(end - overlap_tokens, start + 1)

    return chunks
