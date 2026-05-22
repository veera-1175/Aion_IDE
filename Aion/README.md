# AION

## Autonomous Multi-Agent Software Engineering System with Persistent Semantic Memory

**Resume title:** *Autonomous Multi-Agent Software Engineering System with Semantic Memory Architecture*

AION is a **multi-agent AI system** that autonomously generates, debugs, and tests software — with **Noesis** as the shared long-term memory layer so agents **never forget** bug fixes, patterns, and architecture decisions.

---

## What It Does

```
User Request
     ↓
Coordinator Agent
     ├── Memory Agent   → Noesis recall (prior fixes, patterns)
     ├── Coding Agent   → LLM codegen (any language) or Python synthesizer
     ├── Debug Agent    → Syntax validation + auto-fix
     └── Testing Agent  → Pytest generation & execution
     ↓
All outcomes stored in Noesis → shared across future tasks
```

### Example

**User:** *"Build authentication API using FastAPI."*

| Agent | Action |
|-------|--------|
| **Memory** | Recalls prior FastAPI/JWT patterns from Noesis |
| **Coding** | Creates `main.py`, routes, auth, tests |
| **Debug** | Validates syntax, applies fixes |
| **Testing** | Runs pytest on auth endpoints |
| **Noesis** | Stores compressed insights for next time |

**Second task:** *"Build another auth API"* → agents **recall** the first solution automatically.

---

## Why This + Noesis Is Resume-Worthy

| Without Noesis | With Noesis |
|-------------------|----------------|
| Agents forget every session | Persistent engineering knowledge |
| Repeat same bugs | Recall prior fixes |
| Isolated agent context | Cross-agent semantic memory graph |
| Raw logs | Compressed insights |

**Demonstrates:** AI agents, memory architecture, automation, multi-agent orchestration, software engineering, distributed cognition.

---

## Noesis's Role in AION

**Noesis is not the code generator** — it is the **shared brain** every agent reads and writes.

| When | What Noesis does |
|------|---------------------|
| **Before agents act** | Memory Agent recalls similar past tasks (bug fixes, FastAPI patterns, test outcomes) |
| **After each agent** | Stores compressed summaries: what was built, what failed, what was fixed |
| **Across sessions** | Next task ("build BMI app") can recall insights from yesterday's calculator or auth API work |

AION agents are stateless workers; **Noesis gives them continuity** — like a team wiki that also understands meaning (semantic search + knowledge graph), not just keyword grep.

---

## OpenAI Setup (Cursor-like codegen)

**Never paste API keys in chat or commit them to git.**

```powershell
cd "v:\Aion_IDE\Aion"
copy .env.example .env
# Edit .env — add OPENAI_API_KEY=sk-...
pip install -e ".[llm]"
```

If you exposed a key publicly, **revoke it at platform.openai.com** and create a new one.

With the key in `.env`, the **Coding Agent uses GPT** to write projects in **any language** (Python, JS, Java, Go, etc.). Without it, Python-only tasks use the local synthesizer.

---

## Quick Start

```powershell
cd "v:\Aion_IDE\Aion"

# One-shot setup (venv + Noesis + AION)
.\scripts\setup.ps1
.\.venv\Scripts\Activate.ps1

# Or manual install:
# pip install -r requirements.txt
# pip install -e ../Noesis_v1
# pip install -e ".[llm]"

# Run with custom output folder
aion run "build a BMI weight finder" --project bmi_app --output "D:\Projects"

# Web UI (port 8090 — separate from Noesis dashboard)
aion serve
```

Open **http://localhost:8090** — set **Output folder** to choose where projects are created.

---

## Project Structure

```
Aion/
├── aion/
│   ├── coordinator.py      # Orchestrates pipeline
│   ├── noesis_bridge.py    # Noesis integration
│   ├── agents/             # Coding, Debug, Testing, Memory, Summary
│   ├── codegen/            # LLM planner, sanitizer, test generator
│   ├── ide/                # LSP bridge, checkpoints, codebase index
│   ├── tools/              # Workspace + test runner
│   ├── api/                # FastAPI + web UI
│   └── ui/static/          # Dashboard
├── workspace/              # Generated projects
├── data/                   # AION Noesis DB
└── examples/run_demo.py
```

**Depends on:** [../Noesis_v1](../Noesis_v1) (sibling project)

---

## CLI Commands

```powershell
aion run "Build REST API with FastAPI and Redis"
aion demo
aion stats
aion serve --port 8090

---

## Optional OpenAI Enhancement

Set in `config/settings.yaml`:

```yaml
llm:
  enabled: true
```

```powershell
$env:OPENAI_API_KEY = "your-key"
pip install openai
```

Agents use LLM when enabled; otherwise use production-quality templates.

---

## Resume Bullet Points

- Developed a multi-agent autonomous software engineering system using Python and Noesis semantic memory
- Designed persistent memory infrastructure for cross-agent knowledge reuse and contextual recall
- Implemented collaborative agents for coding, debugging, testing, and pipeline orchestration
- Built knowledge graph-backed memory layer enabling adaptive AI task execution across sessions
- Integrated symbolic memory compression for portable, evolving engineering knowledge

---

## Technologies

| Layer | Stack |
|-------|-------|
| Agents | Python, custom orchestrator (CrewAI/LangGraph-ready) |
| Memory | **Noesis** (semantic compression, graph, SQLite) |
| API | FastAPI, Uvicorn |
| Code gen | FastAPI, JWT, pytest templates |
| Optional LLM | OpenAI API |

---

## License

MIT
