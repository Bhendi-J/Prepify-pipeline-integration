from dataclasses import dataclass
from pathlib import Path


class UnsupportedDocumentTypeError(ValueError):
    pass


@dataclass(frozen=True)
class TextChunk:
    content: str
    token_count: int


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix.lower() != ".txt":
        raise UnsupportedDocumentTypeError("Only .txt uploads are supported for now")

    return path.read_text(encoding="utf-8")


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
