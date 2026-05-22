"""LLM clients — OpenAI (paid), Ollama (free local), Groq (free tier)."""

from __future__ import annotations

import logging
import os

from aion.utils.retry import is_retryable_error, is_schema_validation_failure, sleep_before_retry

logger = logging.getLogger(__name__)

PROVIDERS = ("openai", "ollama", "groq")

GROQ_STRICT_SCHEMA_MODELS = frozenset({
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
})


def _openai_sdk_available() -> bool:
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


class LLMClient:
    """Unified LLM for Coding Agent with automatic retries on transient errors."""

    def __init__(
        self,
        enabled: bool = False,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        base_url: str | None = None,
        max_retries: int = 4,
        retry_base_seconds: float = 2.0,
    ):
        self.provider = (provider or "openai").lower().strip()
        if self.provider not in PROVIDERS:
            self.provider = "openai"

        self.model = model
        self.base_url = base_url
        self._client = None
        self.last_error: str | None = None
        self.max_retries = max(1, max_retries)
        self.retry_base_seconds = retry_base_seconds
        self.last_attempts: int = 0

        has_sdk = _openai_sdk_available()
        if not has_sdk:
            self.enabled = False
            self.last_error = 'Install SDK: pip install openai  (or pip install -e ".[llm]")'
            return

        if self.provider == "ollama":
            self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.model = os.getenv("OLLAMA_MODEL", model or "llama3.2")
            self.enabled = enabled
            self.last_error = None if enabled else "Set llm.enabled: true in config"
        elif self.provider == "groq":
            self.base_url = base_url or "https://api.groq.com/openai/v1"
            key = os.getenv("GROQ_API_KEY", "").strip()
            self.enabled = enabled and bool(key)
            self.last_error = None if self.enabled else "Add GROQ_API_KEY to .env (free at console.groq.com)"
        else:
            self.provider = "openai"
            key = os.getenv("OPENAI_API_KEY", "").strip()
            self.enabled = enabled and bool(key)
            self.last_error = None if self.enabled else "Add OPENAI_API_KEY to .env (paid) or switch to ollama/groq"

    def supports_strict_schema(self) -> bool:
        return self.provider == "groq" and self.model in GROQ_STRICT_SCHEMA_MODELS

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 4000,
        json_mode: bool = False,
        json_schema: dict | None = None,
        schema_name: str = "coding_project",
    ) -> str | None:
        if not self.enabled:
            return None

        tokens = max_tokens
        active_schema = json_schema
        active_json_mode = json_mode
        for attempt in range(self.max_retries):
            self.last_attempts = attempt + 1
            if attempt > 0:
                logger.info("LLM retry %s/%s (%s)", attempt + 1, self.max_retries, self.last_error)
                sleep_before_retry(attempt, self.last_error, self.retry_base_seconds)
                if self.last_error and ("413" in self.last_error or "TPM" in self.last_error.upper()):
                    tokens = max(1200, int(tokens * 0.75))

            result = self._complete_once(
                system, user, tokens, active_json_mode, active_schema, schema_name
            )
            if result:
                self.last_error = None
                return result

            if active_schema and is_schema_validation_failure(self.last_error):
                logger.info("Groq schema validation failed; retrying with json_object mode")
                active_schema = None
                active_json_mode = True
                result = self._complete_once(
                    system, user, tokens, active_json_mode=True, json_schema=None, schema_name=schema_name
                )
                if result:
                    self.last_error = None
                    return result

            if not is_retryable_error(self.last_error):
                break

        return None

    def _complete_once(
        self,
        system: str,
        user: str,
        max_tokens: int,
        json_mode: bool,
        json_schema: dict | None,
        schema_name: str,
    ) -> str | None:
        try:
            from openai import OpenAI

            kwargs: dict = {}
            if self.provider == "ollama":
                kwargs["base_url"] = self.base_url
                kwargs["api_key"] = "ollama"
            elif self.provider == "groq":
                kwargs["base_url"] = self.base_url
                kwargs["api_key"] = os.getenv("GROQ_API_KEY", "")
            else:
                kwargs["api_key"] = os.getenv("OPENAI_API_KEY", "")

            if self._client is None:
                self._client = OpenAI(**kwargs)

            create_kwargs: dict = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "timeout": 120.0,
            }
            if json_schema and self.provider == "groq":
                # Strict JSON schema only when every nested object has additionalProperties: false
                schema_allows_strict = json_schema.get("x_groq_strict", True) is not False
                use_strict = self.model in GROQ_STRICT_SCHEMA_MODELS and schema_allows_strict
                api_schema = {k: v for k, v in json_schema.items() if not str(k).startswith("x_")}
                create_kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": use_strict,
                        "schema": api_schema,
                    },
                }
            elif json_mode and self.provider in ("groq", "openai"):
                create_kwargs["response_format"] = {"type": "json_object"}

            resp = self._client.chat.completions.create(**create_kwargs)
            content = resp.choices[0].message.content
            if not content or not content.strip():
                self.last_error = "Empty LLM response"
                return None
            return content
        except Exception as e:
            self.last_error = str(e)
            logger.warning("LLM call failed (%s): %s", self.provider, e)
            return None

    def status(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "enabled": self.enabled,
            "base_url": self.base_url if self.provider != "openai" else None,
            "last_error": self.last_error,
            "max_retries": self.max_retries,
        }
