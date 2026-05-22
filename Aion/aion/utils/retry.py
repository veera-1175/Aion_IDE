"""Retry helpers for transient Groq/API failures."""

from __future__ import annotations

import time

RETRYABLE_MARKERS = (
    "rate_limit",
    "429",
    "413",
    "timeout",
    "timed out",
    "connection",
    "overloaded",
    "503",
    "502",
    "500",
    "temporarily unavailable",
    "json parse",
    "json_validate",
    "failed to validate json",
    "empty llm",
    "tokens per minute",
    "tpm",
)


def is_schema_validation_failure(message: str | None) -> bool:
    if not message:
        return False
    text = message.lower()
    return "json_validate" in text or "failed to validate json" in text


def is_retryable_error(message: str | None) -> bool:
    if not message:
        return False
    text = message.lower()
    return any(m in text for m in RETRYABLE_MARKERS)


def retry_delay(attempt: int, base_seconds: float = 2.0, tpm_error: bool = False) -> float:
    """Exponential backoff; longer wait for Groq TPM/rate limits."""
    delay = min(base_seconds ** attempt, 45.0)
    if tpm_error:
        delay = max(delay, 12.0 + attempt * 8)
    return delay


def sleep_before_retry(attempt: int, last_error: str | None, base_seconds: float = 2.0) -> float:
    tpm = last_error and ("413" in last_error or "tpm" in last_error.lower() or "429" in last_error)
    delay = retry_delay(attempt, base_seconds, tpm_error=bool(tpm))
    time.sleep(delay)
    return delay
