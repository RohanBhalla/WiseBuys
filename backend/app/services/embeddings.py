"""Gemini text embeddings for hybrid recommendations (google-genai SDK).

Quota / batching notes
----------------------

The Gemini Embeddings API has a per-minute request quota (free tier: 100 RPM
on ``gemini-embedding-001``). To stay well under that limit on busy syncs:

1. We batch ``RETRIEVAL_DOCUMENT`` calls (one HTTP request can carry many
   inputs). The SDK only allows a single ``title`` per request, so we
   *inline* the title into the body (``"{title}\\n\\n{body}"``) — this
   preserves the title-weighting benefit while letting us batch fully.
2. A module-level RPM limiter (``_RpmLimiter``) self-throttles requests so
   we never exceed ``settings.embeddings_max_rpm`` per rolling minute.
3. Retries are 429-aware: when Gemini returns ``RESOURCE_EXHAUSTED`` with a
   ``retryDelay``, we honor it (capped) instead of using exponential
   backoff.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import deque
from typing import Callable, TypeVar

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Hard ceiling on how long we'll sleep waiting for a retry budget to free up.
# Beyond this we give up so callers can fall back to non-vector paths instead
# of stalling a request.
_MAX_RETRY_SLEEP_S = 65.0

# Used to extract the suggested wait time from Gemini's 429 message body.
_RETRY_DELAY_RE = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)


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


class _RpmLimiter:
    """Sliding-window RPM limiter + minimum-gap throttle.

    Two guarantees on every ``acquire``:
      1. We never have more than ``max_rpm`` requests in any rolling 60s
         window (sliding-window cap).
      2. At least ``min_interval_s`` seconds have elapsed since the previous
         request (paced gap, useful to avoid bursting into the API even when
         we're nominally under the per-minute cap).

    Sleeping happens outside the internal lock so other threads can still
    trim the window and queue up.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._times: deque[float] = deque()
        self._last_request_at: float = 0.0

    def acquire(self, max_rpm: int, min_interval_s: float = 0.0) -> None:
        if max_rpm <= 0 and min_interval_s <= 0:
            return
        window = 60.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._times and now - self._times[0] >= window:
                    self._times.popleft()

                rpm_wait = 0.0
                if max_rpm > 0 and len(self._times) >= max_rpm:
                    rpm_wait = window - (now - self._times[0])

                gap_wait = 0.0
                if min_interval_s > 0 and self._last_request_at > 0:
                    elapsed = now - self._last_request_at
                    if elapsed < min_interval_s:
                        gap_wait = min_interval_s - elapsed

                wait = max(rpm_wait, gap_wait)
                if wait <= 0:
                    self._times.append(now)
                    self._last_request_at = now
                    return

            # Released the lock — sleep then loop to re-check (another thread
            # may have consumed our slot in the meantime).
            if rpm_wait > 0:
                logger.info(
                    "Embedding RPM cap (%s) reached; sleeping %.2fs",
                    max_rpm,
                    wait,
                )
            else:
                logger.debug(
                    "Embedding pacing gap (%.2fs); sleeping %.2fs",
                    min_interval_s,
                    wait,
                )
            time.sleep(wait)


_LIMITER = _RpmLimiter()


def _is_quota_error(exc: BaseException) -> tuple[bool, float | None]:
    """Detect Gemini 429 / RESOURCE_EXHAUSTED.

    Returns ``(is_quota, retry_delay_s)``. The SDK currently raises a
    ``ClientError`` (or ``APIError``) with a stringified body that includes
    ``"retry in 50.351449648s"`` — we extract that to align our backoff with
    what Google asked for instead of guessing.
    """
    msg = str(exc)
    is_quota = (
        "RESOURCE_EXHAUSTED" in msg
        or "exceeded your current quota" in msg
        or "code: 429" in msg.lower()
        or " 429 " in msg
    )
    if not is_quota:
        return False, None
    m = _RETRY_DELAY_RE.search(msg)
    if not m:
        return True, None
    try:
        return True, float(m.group(1))
    except ValueError:
        return True, None


def _with_retries(fn: Callable[[], T]) -> T | None:
    s = get_settings()
    delay = 0.5
    last_exc: Exception | None = None
    for attempt in range(s.embeddings_max_retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            quota, suggested = _is_quota_error(exc)
            if quota:
                # Honor the API's RetryInfo if present (capped); otherwise
                # fall back to the standard exponential delay.
                wait = min(_MAX_RETRY_SLEEP_S, suggested + 0.5) if suggested else delay
                logger.warning(
                    "Embedding quota hit (attempt %s); sleeping %.2fs before retry",
                    attempt,
                    wait,
                )
                if attempt >= s.embeddings_max_retries:
                    break
                time.sleep(wait)
                # Don't double-grow the exponential delay on quota retries —
                # we already slept the suggested duration.
                if not suggested:
                    delay *= 2
                continue
            logger.warning("Embedding attempt %s failed: %s", attempt, exc)
            if attempt >= s.embeddings_max_retries:
                break
            time.sleep(delay)
            delay *= 2
    if last_exc:
        logger.warning("Embedding failed after retries: %s", last_exc)
    return None


def _embed_request(contents: list[str], task_type: str) -> list[list[float]] | None:
    """Issue a single, RPM-throttled embed_content request and L2-normalize."""
    client = _client()
    if not client:
        return None
    s = get_settings()

    def call() -> list[list[float]]:
        _LIMITER.acquire(
            s.embeddings_max_rpm,
            min_interval_s=s.embeddings_min_interval_s,
        )
        result = client.models.embed_content(
            model=s.embeddings_model,
            contents=contents,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=s.embeddings_dim,
            ),
        )
        if not result.embeddings or len(result.embeddings) != len(contents):
            raise RuntimeError("embed_content length mismatch")
        return [l2_normalize(list(e.values)) for e in result.embeddings]

    return _with_retries(call)


def embed_query(text: str) -> list[float] | None:
    """Single customer-side vector (RETRIEVAL_QUERY)."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    out = _embed_request([stripped], task_type="RETRIEVAL_QUERY")
    if out is None:
        return None
    return out[0]


def embed_documents(texts: list[str]) -> list[list[float]] | None:
    """Batch catalog-side vectors (RETRIEVAL_DOCUMENT) without titles."""
    return embed_documents_with_titles([(None, t) for t in texts])


def embed_documents_with_titles(
    items: list[tuple[str | None, str]],
) -> list[list[float]] | None:
    """Batch ``RETRIEVAL_DOCUMENT`` vectors with title-weighted bodies.

    Best practice for retrieval embeddings (per Google's docs) is to surface
    the document title prominently because the model weights it more heavily.
    The SDK API only accepts ONE ``title`` per ``embed_content`` call though,
    which would force one HTTP request per item when titles vary — that
    quickly trips per-minute quota limits on the free tier (100 RPM).

    The pragmatic alternative is to inline the title into the body
    (``"{title}\\n\\n{body}"``). That keeps the title prominent in the
    encoded text while letting us send many items in a single batched
    request. Empirically this gives nearly the same retrieval quality as the
    config-level title at a fraction of the request count.
    """
    if not items:
        return []

    s = get_settings()
    bodies: list[str] = []
    for title, body in items:
        title_part = (title or "").strip()
        body_part = (body or "").strip()
        if title_part and body_part:
            bodies.append(f"{title_part}\n\n{body_part}")
        else:
            bodies.append(title_part or body_part or " ")

    batch_size = max(1, s.embeddings_batch_size)
    out: list[list[float]] = []
    for start in range(0, len(bodies), batch_size):
        chunk_bodies = bodies[start : start + batch_size]
        chunk = _embed_request(chunk_bodies, task_type="RETRIEVAL_DOCUMENT")
        if chunk is None:
            return None
        out.extend(chunk)
    return out
