import hashlib
import math
from collections.abc import Sequence
from typing import Any

from app.core.config import settings


class EmbeddingConfigurationError(RuntimeError):
    pass


def get_embeddings(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []

    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai":
        return _get_openai_embeddings(texts)
    if provider in {"huggingface", "hf"}:
        return _get_huggingface_embeddings(texts)
    if provider == "local":
        return [_get_local_embedding(text) for text in texts]

    raise EmbeddingConfigurationError(f"Unsupported embedding provider: {provider}")


def _get_openai_embeddings(texts: Sequence[str]) -> list[list[float]]:
    if settings.LLM_API_KEY is None:
        raise EmbeddingConfigurationError("LLM_API_KEY is required for OpenAI embeddings")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise EmbeddingConfigurationError("Install openai to use OpenAI embeddings") from exc

    client = OpenAI(api_key=settings.LLM_API_KEY)
    response = client.embeddings.create(
        input=list(texts),
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
        encoding_format="float",
    )
    return [
        item.embedding
        for item in sorted(response.data, key=lambda item: item.index)
    ]


def _get_huggingface_embeddings(texts: Sequence[str]) -> list[list[float]]:
    if not settings.HF_TOKEN:
        raise EmbeddingConfigurationError("HF_TOKEN is required for Hugging Face embeddings")

    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:
        raise EmbeddingConfigurationError(
            "Install huggingface_hub to use Hugging Face embeddings"
        ) from exc

    client = InferenceClient(
        provider=settings.HUGGINGFACE_PROVIDER,
        api_key=settings.HF_TOKEN,
    )
    raw_embeddings = client.feature_extraction(
        list(texts),
        model=settings.HUGGINGFACE_EMBEDDING_MODEL,
    )
    embeddings = _coerce_embeddings(raw_embeddings)
    return [_validate_embedding_dimension(embedding) for embedding in embeddings]


def _get_local_embedding(text: str) -> list[float]:
    values: list[float] = []
    seed = text.encode("utf-8")
    counter = 0

    while len(values) < settings.EMBEDDING_DIMENSIONS:
        digest = hashlib.sha256(counter.to_bytes(4, "big") + seed).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1

    vector = values[: settings.EMBEDDING_DIMENSIONS]
    magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / magnitude for value in vector]


def _coerce_embeddings(raw_embeddings: Any) -> list[list[float]]:
    if hasattr(raw_embeddings, "tolist"):
        raw_embeddings = raw_embeddings.tolist()

    if not raw_embeddings:
        return []

    first = raw_embeddings[0]
    if isinstance(first, int | float):
        return [[float(value) for value in raw_embeddings]]

    return [[float(value) for value in embedding] for embedding in raw_embeddings]


def _validate_embedding_dimension(embedding: list[float]) -> list[float]:
    actual_dimensions = len(embedding)
    if actual_dimensions != settings.EMBEDDING_DIMENSIONS:
        raise EmbeddingConfigurationError(
            "Embedding dimension mismatch: "
            f"got {actual_dimensions}, expected {settings.EMBEDDING_DIMENSIONS}"
        )
    return embedding
