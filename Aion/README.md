# AION

### Multi-agent software engineering with Noesis persistent memory

Part of the **[Aion_IDE](https://github.com/veera-1175/Aion_IDE)** monorepo. See the [root README](../README.md) for the product overview.

AION orchestrates specialized agents (memory, coding, debug, testing) so a user request becomes a generated, validated project — with **Noesis** as the shared long-term memory across runs.

---

## Pipeline

```
User request → Coordinator
  → Memory (Noesis recall)
  → Coding
  → Debug
  → Testing
  → Insights written back to Noesis
```

---

## Quick start

```powershell
cd Aion
.\scripts\setup.ps1
.\.venv\Scripts\Activate.ps1

# CLI
aion run "build a BMI calculator" --project bmi_app --output "D:\Projects"

# Web UI — http://localhost:8090
aion serve
```

From the monorepo root you can also run `start-aion.bat`.

---

## Optional LLM (OpenAI)

Never commit API keys.

```powershell
copy .env.example .env
# OPENAI_API_KEY=...
pip install -e ".[llm]"
```

With a key, the coding agent can generate across languages. Without it, local synthesizer / templates still handle Python-focused flows.

---

## Structure

```
Aion/
├── aion/
│   ├── coordinator.py
│   ├── noesis_bridge.py
│   ├── agents/
│   ├── codegen/
│   ├── ide/
│   ├── tools/
│   ├── api/
│   └── ui/static/
├── workspace/
├── data/
└── examples/
```

Depends on sibling **`../Noesis_v1`**.

---

## CLI

```powershell
aion run "Build REST API with FastAPI and Redis"
aion demo
aion stats
aion serve --port 8090
```

---

## Stack

| Layer | Tech |
|-------|------|
| Agents | Python orchestrator |
| Memory | Noesis (compression, graph, SQLite) |
| API / UI | FastAPI, Uvicorn, static dashboard |
| Optional LLM | OpenAI |

---

## License

MIT © [Veerasegaran V P](https://github.com/veera-1175)
