# Free LLM options for AION (no OpenAI billing)

You do **not** need OpenAI. Pick one path below.

---

## Option 1: No LLM at all (simplest)

Works today for **Python** tasks with no setup:

- `build a BMI weight finder`
- `build a simple calculator`
- `Build FastAPI authentication API`

The **synthesizer** writes the code locally. Noesis memory still works.

---

## Option 2: Ollama (recommended — free, private, on your PC)

1. Install [Ollama](https://ollama.com) for Windows.
2. In PowerShell:
   ```powershell
   ollama pull llama3.2
   ```
   For coding, also try: `ollama pull codellama` or `ollama pull qwen2.5-coder`

3. Edit `Aion/.env`:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2
   ```

4. Edit `config/settings.yaml`:
   ```yaml
   llm:
     enabled: true
     provider: ollama
     model: llama3.2
   ```

5. Restart AION: `aion serve`

Ollama runs at `http://localhost:11434` — no API key, no credit card.

---

## Option 3: Groq (free cloud API)

1. Sign up at [console.groq.com](https://console.groq.com) (free tier).
2. Create an API key.
3. `.env`:
   ```
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_...
   ```
4. `config/settings.yaml`:
   ```yaml
   llm:
     provider: groq
     model: llama-3.1-8b-instant
   ```

---

## Other free services (manual setup)

| Service | Notes |
|---------|--------|
| **Google Gemini** | Free tier on AI Studio — needs separate SDK (not built in yet) |
| **Hugging Face** | Free inference for some models — rate limited |
| **LM Studio** | Local GUI; can expose OpenAI-compatible URL like Ollama |
| **OpenRouter** | Some free models; OpenAI-compatible with `OPENAI_BASE_URL` |

---

## Remove OpenAI from `.env`

If you are not paying OpenAI, delete or comment out:

```
OPENAI_API_KEY=...
```

Use `LLM_PROVIDER=ollama` or `groq` instead so AION does not hit a quota error.
