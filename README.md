# Aion IDE

### Autonomous multi-agent software engineering with persistent semantic memory

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/UI%2FAPI-local_stack-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Multi-agent coding system (plan → code → debug → test) backed by **Noesis** — a shared long-term memory so agents remember fixes, patterns, and architecture decisions across sessions.

Solo-built by **[Veerasegaran V P](https://github.com/veera-1175)** as an independent product exploring agent orchestration and durable engineering memory — not a one-shot codegen demo.

---

## What it does

```
User request
     ↓
Coordinator
     ├── Memory agent   → Noesis recall (prior fixes, patterns)
     ├── Coding agent   → LLM codegen or synthesizer
     ├── Debug agent    → Validate + auto-fix
     └── Testing agent  → Generate & run tests
     ↓
Outcomes written back to Noesis → reused on the next task
```

**Example:** *"Build an authentication API with FastAPI."*

| Agent | Action |
|-------|--------|
| Memory | Recalls prior FastAPI / JWT patterns from Noesis |
| Coding | Creates routes, auth, and scaffolding |
| Debug | Validates syntax, applies fixes |
| Testing | Runs pytest-style checks |
| Noesis | Stores compressed insights for the next run |

A second similar task can **recall** the first solution instead of starting from zero.

---

## Why memory matters

| Without Noesis | With Noesis |
|----------------|-------------|
| Agents forget every session | Persistent engineering knowledge |
| Repeat the same bugs | Recall prior fixes |
| Isolated agent context | Shared semantic + graph memory |
| Raw logs | Compressed, searchable insights |

This repo is a **monorepo**: the AION workspace plus a vendored Noesis memory engine.

---

## Table of contents

1. [Repo layout](#repo-layout)
2. [Quick start](#quick-start)
3. [LLM setup](#llm-setup)
4. [Noesis role](#noesis-role)
5. [Interview walkthrough](#interview-walkthrough)
6. [Related projects](#related-projects)
7. [License](#license)

---

## Repo layout

```
Aion_IDE/
├── Aion/              # Multi-agent IDE / orchestration product
│   ├── aion/          # Agents, tools, IDE bridges, UI static
│   ├── scripts/       # setup.ps1, serve.ps1
│   └── serve.bat
├── Noesis_v1/         # Semantic-symbolic memory engine (embedded)
└── start-aion.bat     # Launch from repo root
```

Standalone memory engine (evolved): **[Noesis](https://github.com/veera-1175/Noesis)**

---

## Quick start

```powershell
git clone https://github.com/veera-1175/Aion_IDE.git
cd Aion_IDE
```

From the root:

```bat
start-aion.bat
```

Or manually:

```powershell
cd Aion
.\scripts\setup.ps1
.\scripts\serve.ps1
# or: serve.bat
```

Follow `Aion/README.md` and `Aion/config/settings.yaml` for ports, workspace path, and model settings.

---

## LLM setup

Optional cloud codegen (keep keys out of git):

```powershell
cd Aion
copy .env.example .env
# Set OPENAI_API_KEY=...
pip install -e ".[llm]"
```

Local / offline-friendly setups can use configured local models where supported — see `Aion/aion/llm.py` and settings.

---

## Noesis role

**Noesis is not the code generator** — it is the shared brain every agent reads and writes.

| When | What happens |
|------|----------------|
| Before agents act | Memory agent recalls similar past tasks |
| After each agent | Compressed summaries stored (built / failed / fixed) |
| Across sessions | Later tasks reuse insights via semantic + graph recall |

Agents stay focused workers; **Noesis gives continuity**.

---

## Interview walkthrough

| Topic | Point to |
|-------|----------|
| Multi-agent design | Coordinator + specialized workers |
| Memory architecture | Noesis compression, graph, hybrid recall |
| Engineering loop | Code → debug → test with persistence |
| Monorepo craft | IDE product + embedded memory engine |

**Demo tip:** run a first task, show Noesis store / recall, then a related second task and highlight reuse.

---

## Related projects

- **[Noesis](https://github.com/veera-1175/Noesis)** — full memory engine (library + API + dashboard)
- **[Verdict](https://github.com/veera-1175/verdict)** — multi-agent PR review platform
- **[AtlasIQ](https://github.com/veera-1175/AtlasIQ)** — NL → SQL analytics with RBAC

---

## License

MIT © [Veerasegaran V P](https://github.com/veera-1175)

**Aion IDE** — agents that keep engineering memory.
