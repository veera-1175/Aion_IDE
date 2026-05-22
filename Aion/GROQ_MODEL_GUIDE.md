# Groq model guide for AION

Use this with your [Groq models page](https://console.groq.com/docs/models).

## Recommended for AION (HTML / multi-file code)

| Model ID | Why |
|----------|-----|
| **`openai/gpt-oss-20b`** | Fast (~1000 t/s), supports **Structured Outputs strict mode** — JSON always matches schema |
| **`openai/gpt-oss-120b`** | Stronger coding; same strict JSON guarantee |

Set in `config/settings.yaml`:

```yaml
llm:
  provider: groq
  model: openai/gpt-oss-20b
  structured_outputs: true
  auto_repair_web: false
```

## Other production models

| Model ID | Use case |
|----------|----------|
| `llama-3.3-70b-versatile` | Better reasoning; use **JSON object mode** only (no strict schema) |
| `llama-3.1-8b-instant` | Cheap/fast — **often breaks** HTML-in-JSON; not recommended for calendars |

## What you must do

1. `.env`:
   ```
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_...
   ```

2. Optional override in `.env`:
   ```
   GROQ_MODEL=openai/gpt-oss-20b
   ```

3. Restart:
   ```powershell
   aion serve
   ```

4. Task text — be explicit (Groq fills the schema):
   ```
   Build a calendar with HTML, CSS, and vanilla JavaScript.
   Month view with previous/next buttons. No external libraries.
   ```

5. Check `index.html` starts with `<!DOCTYPE html>` — if it starts with `{"`, pick a better model or re-run.

## Rate limits

If you see **413 / tokens per minute**, the request is too large:

- Use a **shorter task** in the UI
- AION caps output tokens (~2800) for `gpt-oss-20b`
- Wait 1 minute and retry, or upgrade tier on Groq console

Docs list higher TPM on paid tiers; free/on-demand may be lower.

## Structured Outputs (why this fixes bad calendars)

Groq **strict mode** forces:

```json
{
  "files": {
    "index.html": "<!DOCTYPE html>...",
    "styles.css": "...",
    "script.js": "...",
    "README.md": "..."
  },
  "summary": "..."
}
```

HTML cannot be used as a JSON **key** anymore — that was the main bug with `llama-3.1-8b-instant`.

Docs: https://console.groq.com/docs/structured-outputs
