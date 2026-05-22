# Noesis — Presentation & Demo Guide

## Elevator Pitch (30 seconds)

> Traditional AI forgets everything after each session and stores huge raw chat logs in cloud vector databases. **Noesis** is a cognitive memory architecture that **compresses meaning**, **builds concept graphs**, **packages memory symbolically**, and **shares knowledge across agents** — like a human brain, not a filing cabinet.

## Live Demo Script (5 minutes)

### 1. Start Dashboard (1 min)

```powershell
cd "v:\Aion_IDE\Noesis_v1"
.\scripts\setup.ps1
noesis serve
```

Open http://localhost:8080

### 2. Show Innovation #1 — Semantic Compression (1 min)

Click **Demo Compression** in dashboard, or:

```powershell
noesis remember "User asked about Redis"
noesis remember "User asked about async workers"
noesis remember "User asked about FastAPI scaling"
noesis list
```

Point out: **3 conversations → compressed insights**, not 3 raw chunks.

### 3. Show Innovation #4 — Knowledge Graph (1 min)

Type in chat: `FastAPI scaling with Redis`  
Show graph visualization: **FastAPI ↔ Redis ↔ Scaling**

### 4. Show Innovation #2 & #3 — Portable + Shared Memory (1 min)

```powershell
python examples\multi_agent_demo.py
```

Agent Alpha learns → exports packet → Agent Beta imports → recalls without original chat.

### 5. Show Innovation #5 — Forgetting (30 sec)

```powershell
noesis remember "ok"
noesis forget-cycle
```

## Comparison Slide Content

| | ChatGPT / RAG | Noesis |
|---|---------------|-----------|
| Storage | Raw text chunks | Semantic insights |
| Format | Embeddings in cloud DB | Symbolic bytecode packets |
| Retrieval | Vector similarity | Graph traversal |
| Multi-agent | Isolated | Sync via packets |
| Growth | Unlimited | Adaptive forgetting |

## Architecture Diagram (for slides)

```
Input → Semantic Engine → Knowledge Graph → Symbolic Packets → Storage
                ↓                                    ↓
           Insights only                      Mesh Sync → Other Agents
```

## Research Areas Covered

- Cognitive AI / long-term memory
- Semantic compression
- Knowledge representation (graphs)
- Distributed cognition / multi-agent
- Edge AI (local embeddings, SQLite)
- Symbolic AI (SentencePiece + msgpack)

## FAQ Preparation

**Q: How is this different from a vector database?**  
A: Vector DBs store and retrieve *chunks*. Noesis stores *compressed meaning* and recalls via *concept relationships*.

**Q: Does it need cloud/GPU?**  
A: No. Runs on laptop, Raspberry Pi class devices with local sentence-transformers.

**Q: Can multiple robots/agents share memory?**  
A: Yes — export symbolic packets, sync over HTTP mesh.

## Project Stats to Mention

- 5 innovation pillars implemented
- 28+ automated tests
- REST API + web dashboard
- LangChain integration optional
- Docker deployment ready

## Files Reviewers Should Open

1. `noesis/core/engine.py` — main orchestrator
2. `noesis/semantic/insights.py` — semantic compression
3. `noesis/graph/recall.py` — graph recall
4. `noesis/sync/packet_merge.py` — collective memory
5. `ARCHITECTURE.md` — technical deep dive
