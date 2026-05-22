# Noesis Memory Engine

**A Semantic + Symbolic Distributed AI Memory Architecture**

> The innovation is not *"AI remembers."*  
> The innovation is **HOW** memory is represented, compressed, evolved, shared, and reconstructed.

[![Tests](https://img.shields.io/badge/tests-26%2B%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Phases](https://img.shields.io/badge/phases%201--5-complete-purple)](#all-features)

---

> **New to Noesis?** Read the full **[USER_GUIDE.md](USER_GUIDE.md)** — plain-language explanation, setup, dashboard, CLI, and presentation tips.

## Quick Start (60 seconds)

```powershell
# Windows
.\scripts\setup.ps1
.\.venv\Scripts\Activate.ps1
noesis serve
```

Open **http://localhost:8080** — interactive dashboard with knowledge graph, chat, and memory viewer.

---

## Five Innovations vs Traditional AI

| # | Innovation | Traditional (ChatGPT/RAG) | Noesis |
|---|------------|---------------------------|-----------|
| 1 | **Semantic Compression** | Store full conversations | Store compressed insights |
| 2 | **Symbolic Portable Memory** | Cloud embeddings only | Bytecode packets — transferable |
| 3 | **Distributed Shared Memory** | Isolated agents | Mesh sync — collective intelligence |
| 4 | **Knowledge Graph Recall** | Vector chunk similarity | Concept graph traversal |
| 5 | **Adaptive Forgetting** | Accumulate forever | Decay + merge + prune |

---

## Full Feature List

### Core Engine (Phases 1–5)
- Conversation / log / event ingestion
- Semantic parsing, importance scoring, clustering
- Memory hierarchy: episodic, semantic, procedural, insight
- Knowledge graph (NetworkX) with associative recall
- SentencePiece symbolic tokenization + msgpack bytecode
- Portable memory packets + HTTP mesh sync
- Adaptive forgetting + redundancy elimination
- Predictive recall + memory evolution

### Enhancements
- **Web Dashboard** — graph visualization, chat, memory browser
- **REST API** — FastAPI with OpenAPI docs at `/docs`
- **Persistent Agent** — drop-in assistant with long-term memory
- **LangChain adapter** — optional `NoesisMemory` backend
- **Docker** — single-command deployment
- **Presentation guide** — see [NOESIS_PRESENTATION.md](NOESIS_PRESENTATION.md)

---

## Commands

```powershell
# Web dashboard + API
noesis serve                    # http://localhost:8080
noesis serve --port 9000

# Memory operations
noesis remember "User deployed Redis for FastAPI"
noesis recall "backend scaling" --mode hybrid
noesis explain-query "FastAPI Redis"
noesis list
noesis stats
noesis forget-cycle

# Distributed sync
noesis mesh-serve --port 8765
noesis sync-push http://peer:8765
noesis sync-pull http://peer:8765

# Demos
noesis demo
noesis innovation
noesis multi-agent
noesis chat                       # terminal persistent agent
```

---

## Python API

```python
from noesis import NoesisEngine
from noesis.agents import PersistentAgent

# Low-level engine
engine = NoesisEngine()
engine.remember("User asked about Redis async scaling")
contexts = engine.recall("backend scaling", mode="hybrid")
engine.compare_with_traditional(["asked Redis", "asked workers", "asked scaling"])
engine.export_memory(memory_id)
engine.sync_from_peer("http://192.168.1.10:8765")

# High-level persistent agent
agent = PersistentAgent(agent_id="my-assistant")
response = agent.chat("What do you know about my backend stack?")
print(response["memory_context"])
print(response["suggested_system_prompt"])  # inject into any LLM
```

---

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/docs` | GET | OpenAPI documentation |
| `/health` | GET | Health check |
| `/remember` | POST | Store compressed memory |
| `/recall` | POST | Hybrid graph+semantic recall |
| `/chat` | POST | Remember + recall for assistants |
| `/graph` | GET | Full knowledge graph |
| `/memories` | GET | List compressed memories |
| `/compare` | POST | Demo vs traditional storage |
| `/forget` | POST | Forgetting cycle |

---

## Docker

```bash
docker compose up --build
# Dashboard at http://localhost:8080

# Multi-agent profile
docker compose --profile multi-agent up
```

---

## Project Structure

```
noesis/
├── core/           # Engine orchestrator
├── semantic/       # Compression, clustering, evolution
├── symbolic/       # Tokenization, bytecode, packets
├── graph/          # Knowledge graph + recall
├── sync/           # Mesh server/client, packet merge
├── forgetting/     # Decay, redundancy
├── recall/         # Predictive recall
├── api/            # FastAPI + web dashboard
├── agents/         # PersistentAgent, LangChain memory
└── storage/        # SQLite

examples/           # Demos (workflow, innovation, multi-agent, chat)
scripts/            # setup.ps1, run_server.py
NOESIS_PRESENTATION.md  # Demo & presentation guide
ARCHITECTURE.md     # Technical deep dive
```

---

## Install Options

```powershell
pip install -e .              # Core only
pip install -e ".[api]"       # + Dashboard
pip install -e ".[agents]"    # + LangChain
pip install -e ".[all]"       # Everything
```

---

## Tests

```powershell
pytest tests/ -v
```

---

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical innovation deep dive
- [NOESIS_PRESENTATION.md](NOESIS_PRESENTATION.md) — Presentation & demo script

---

## License

MIT — Noesis Memory Engine Project
