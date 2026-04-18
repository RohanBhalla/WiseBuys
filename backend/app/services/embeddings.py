"""Gemini text embeddings for hybrid recommendations (google-genai SDK)."""

from __future__ import annotations

import logging
import math
import time
from typing import Callable, TypeVar

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def l2_normalize(values: list[float]) -> list[float]:
    s = math.sqrt(sum(x * x for x in values))
    if s == 0:
        return values
    return [x / s for x in values]


def _client() -> genai.Client | None:
    s = get_settings()
    if not (s.gemini_api_key and str(s.gemini_api_key).strip()):
        return None
    return genai.Client(api_key=s.gemini_api_key)


def _with_retries(fn: Callable[[], T]) -> T | None:
    s = get_settings()
    delay = 0.5
    last_exc: Exception | None = None
    for attempt in range(s.embeddings_max_retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("Embedding attempt %s failed: %s", attempt, exc)
            if attempt >= s.embeddings_max_retries:
                break
            time.sleep(delay)
            delay *= 2
    if last_exc:
        logger.warning("Embedding failed after retries: %s", last_exc)
    return None


def embed_query(text: str) -> list[float] | None:
    """Single customer-side vector (RETRIEVAL_QUERY)."""
    client = _client()
    if not client:
        return None
    stripped = (text or "").strip()
    if not stripped:
        return None
    s = get_settings()

    def call() -> list[float]:
        result = client.models.embed_content(
            model=s.embeddings_model,
            contents=stripped,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=s.embeddings_dim,
            ),
        )
        if not result.embeddings:
            raise RuntimeError("embed_content returned no embeddings")
        return l2_normalize(list(result.embeddings[0].values))

    return _with_retries(call)


def embed_documents(texts: list[str]) -> list[list[float]] | None:
    """Batch catalog-side vectors (RETRIEVAL_DOCUMENT)."""
    client = _client()
    if not client:
        return None
    if not texts:
        return []
    s = get_settings()
    batch_size = max(1, s.embeddings_batch_size)
    out: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = [(t or "").strip() or " " for t in texts[start : start + batch_size]]

        def call() -> list[list[float]]:
            result = client.models.embed_content(
                model=s.embeddings_model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=s.embeddings_dim,
                ),
            )
            if not result.embeddings or len(result.embeddings) != len(batch):
                raise RuntimeError("embed_content length mismatch")
            return [l2_normalize(list(e.values)) for e in result.embeddings]

        chunk = _with_retries(call)
        if chunk is None:
            return None
        out.extend(chunk)
    return out
