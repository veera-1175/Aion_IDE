"""LLM-powered code creation — retries + Groq Structured Outputs."""

from __future__ import annotations

import json
import logging
import re

from aion.codegen.file_sanitizer import normalize_files, validate_web_project
from aion.codegen.groq_schema import (
    WEB_PROJECT_SCHEMA_STRICT,
    build_edit_schema_strict,
)
from aion.codegen.planner import TaskPlan
from aion.llm import LLMClient
from aion.utils.retry import is_retryable_error

logger = logging.getLogger(__name__)


class LLMCoder:
    def __init__(
        self,
        llm: LLMClient,
        auto_repair_web: bool = False,
        use_structured_outputs: bool = True,
        max_attempts: int = 3,
    ):
        self.llm = llm
        self.auto_repair_web = auto_repair_web
        self.use_structured_outputs = use_structured_outputs
        self.max_attempts = max(1, max_attempts)
        self.last_error: str | None = None

    def create_project(
        self, plan: TaskPlan, task: str, memory_context: str = ""
    ) -> tuple[dict[str, str], str] | None:
        self.last_error = None
        if not self.llm.enabled:
            self.last_error = self.llm.last_error or "LLM not enabled"
            return None

        is_web = plan.app_type in ("calendar_html", "static_web") or plan.language == "web"
        schema = None
        use_json_object = False
        if self.use_structured_outputs and self.llm.provider == "groq":
            if is_web and plan.app_type == "calendar_html":
                schema = WEB_PROJECT_SCHEMA_STRICT
            elif is_web:
                # Portfolios / static sites — strict schema often hits json_validate_failed
                use_json_object = True
            else:
                use_json_object = True

        system = (
            "Expert coding agent. Return JSON with exactly two top-level keys: "
            '"files" (object mapping filename → full file source) and "summary" (short string). '
            "Do not put filenames at the top level. Include all files needed to run the project."
        )
        user = (
            f"Task: {task}\nLang: {plan.language} | Type: {plan.app_type}\n"
            'Return {"files": {"main.py": "...", ...}, "summary": "..."}. '
            "Vanilla HTML/CSS/JS for web. No CDN libraries."
        )
        max_out = 2600 if self.llm.supports_strict_schema() else 3200

        for attempt in range(self.max_attempts):
            if attempt > 0:
                logger.info("Coding generation retry %s/%s: %s", attempt + 1, self.max_attempts, self.last_error)
                user_attempt = f"{user}\n\nPrevious attempt failed: {self.last_error}. Fix and return valid JSON."
            else:
                user_attempt = user

            raw = self.llm.complete(
                system,
                user_attempt,
                max_tokens=max_out,
                json_mode=use_json_object or schema is None,
                json_schema=schema,
            )
            if not raw:
                self.last_error = self.llm.last_error or "Empty LLM response"
                if not is_retryable_error(self.last_error):
                    break
                continue

            parsed = self._parse_and_fix(raw, plan, is_web)
            if parsed:
                return parsed

            if not is_retryable_error(self.last_error):
                break

        self.last_error = self.last_error or self.llm.last_error or "Generation failed after retries"
        return None

    def edit_project(
        self,
        plan: TaskPlan,
        task: str,
        existing_files: dict[str, str],
    ) -> tuple[dict[str, str], str] | None:
        """Modify an existing project — LLM returns updated file contents."""
        self.last_error = None
        if not self.llm.enabled:
            self.last_error = self.llm.last_error or "LLM not enabled"
            return None
        if not existing_files:
            self.last_error = "No existing files to edit"
            return None

        is_web = plan.language == "web" or any(f.endswith(".html") for f in existing_files)
        paths = sorted(existing_files.keys())
        schema = None
        use_json_object = True
        if self.use_structured_outputs and self.llm.provider == "groq":
            if is_web and set(paths) >= {"index.html", "styles.css"}:
                schema = WEB_PROJECT_SCHEMA_STRICT
                use_json_object = False
            else:
                schema = build_edit_schema_strict(paths)
                use_json_object = schema is None

        file_list = ", ".join(paths)
        snippets = []
        budget = 12000
        used = 0
        for path, body in existing_files.items():
            chunk = body if used + len(body) < budget else body[: max(400, budget - used)]
            snippets.append(f"### {path}\n{chunk}")
            used += len(chunk)

        system = (
            "You are an expert coding agent EDITING an existing project. "
            "Apply the user's change request. Return JSON: files (all project files with full updated content), summary. "
            "Include every file that must exist after the edit. Keys = filenames only."
        )
        user = (
            f"Change request: {task}\n"
            f"Project type: {plan.app_type} | Language: {plan.language}\n"
            f"Existing files: {file_list}\n\n"
            + "\n\n".join(snippets)
        )
        max_out = 3200

        for attempt in range(self.max_attempts):
            raw = self.llm.complete(
                system,
                user if attempt == 0 else f"{user}\n\nFix errors: {self.last_error}",
                max_tokens=max_out,
                json_mode=use_json_object,
                json_schema=schema,
            )
            if not raw:
                self.last_error = self.llm.last_error or "Empty LLM response"
                if not is_retryable_error(self.last_error):
                    break
                continue
            parsed = self._parse_and_fix(raw, plan, is_web, existing_files=existing_files)
            if parsed:
                return parsed
            if not is_retryable_error(self.last_error):
                break
        return None

    def _parse_and_fix(
        self,
        raw: str,
        plan: TaskPlan,
        is_web: bool,
        existing_files: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], str] | None:
        data = self._parse_raw(raw)
        if not data:
            return None

        data = self._coerce_project_shape(data)
        files = data.get("files") or {}
        if not isinstance(files, dict) or not files:
            self.last_error = "JSON missing files object"
            return None

        files = normalize_files({str(k): str(v) for k, v in files.items() if v is not None})

        if is_web:
            check_files = files
            if existing_files:
                check_files = {**existing_files, **files}
                files = check_files
            errors = validate_web_project(check_files)
            if errors:
                self.last_error = f"Invalid output: {', '.join(errors)}"
                if self.auto_repair_web:
                    from aion.codegen.file_sanitizer import ensure_calendar_html_links
                    files = ensure_calendar_html_links(check_files)
                    if not validate_web_project(files):
                        return None
                else:
                    return None

        summary = data.get("summary") or "LLM-generated project"
        if not files:
            self.last_error = "No valid files after parsing"
            return None
        return files, str(summary)

    def _coerce_project_shape(self, data: dict) -> dict:
        """Accept LLM responses that put filenames at top level instead of under files."""
        files = data.get("files")
        if isinstance(files, dict) and files:
            return data

        reserved = {"summary", "files", "project", "description"}
        flat: dict[str, str] = {}
        for key, value in data.items():
            if key in reserved or not isinstance(value, str):
                continue
            if "." in key or "/" in key or "\\" in key:
                flat[str(key)] = value
        if flat:
            return {"files": flat, "summary": data.get("summary") or "LLM-generated project"}
        return data

    def _parse_raw(self, raw: str) -> dict | None:
        try:
            cleaned = raw.strip()
            if "```" in cleaned:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
                if m:
                    cleaned = m.group(1)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            self.last_error = f"JSON parse error: {e}"
            return None
