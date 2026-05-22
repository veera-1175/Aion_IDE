# Noesis User Guide

A simple guide to understanding and using the Noesis Memory Engine.

---

## Table of Contents

1. [What Is Noesis?](#1-what-is-noesis)
2. [What Problem Does It Solve?](#2-what-problem-does-it-solve)
3. [How Is It Different From ChatGPT?](#3-how-is-it-different-from-chatgpt)
4. [Installation](#4-installation)
5. [Quick Start (5 Minutes)](#5-quick-start-5-minutes)
6. [Using the Web Dashboard](#6-using-the-web-dashboard)
7. [Using the Command Line](#7-using-the-command-line)
8. [Using Python in Your Code](#8-using-python-in-your-code)
9. [Understanding Memory Types](#9-understanding-memory-types)
10. [The Five Innovations](#10-the-five-innovations)
11. [Multi-Agent Memory Sharing](#11-multi-agent-memory-sharing)
12. [REST API Reference](#12-rest-api-reference)
13. [Demos and Examples](#13-demos-and-examples)
14. [Configuration](#14-configuration)
15. [Troubleshooting](#15-troubleshooting)
16. [Noesis Presentation Tips](#16-noesis-presentation-tips)
17. [Glossary](#17-glossary)

---

## 1. What Is Noesis?

**Noesis** is a **long-term memory system for AI**. It does not chat with you by itself. It **remembers**, **compresses**, **connects**, and **recalls** knowledge — like a brain layer behind an assistant, robot, or app.

**One-line definition:**

> Noesis turns many conversations into small, meaningful memories and finds them later through ideas and relationships — not by storing every message you ever typed.

---

## 2. What Problem Does It Solve?

| Problem | Without Noesis | With Noesis |
|---------|-------------------|----------------|
| Sessions end | AI forgets everything | Memories persist in a database |
| Storage | Huge raw chat logs | Compressed insights |
| Retrieval | “Find similar text” | “Follow concept links” |
| Multiple devices | Each AI is isolated | Memory packets can sync |
| Old junk | Everything kept forever | Low-value memories fade |

---

## 3. How Is It Different From ChatGPT?

| | ChatGPT / Normal Chatbot | Noesis |
|---|--------------------------|-----------|
| **Role** | Talks and answers | Stores and recalls knowledge |
| **Memory** | Recent messages in the prompt | Compressed insights in a database |
| **Storage** | Full conversation text | Meaning (e.g. “User knows FastAPI + Redis”) |
| **Search** | Similar text chunks | Knowledge graph + meaning |
| **Runs on** | Cloud | Your PC (edge-friendly) |

**You can use both:** ChatGPT for answers, Noesis for what the AI should **remember long-term**.

---

## 4. Installation

### Requirements

- Windows 10/11 (or Linux/macOS)
- Python 3.10 or newer
- Internet (first run only — downloads a small AI model ~90MB)

### Setup (Windows)

Open PowerShell in the project folder:

```powershell
cd "v:\Aion_IDE\Noesis_v1"
.\scripts\setup.ps1
```

Or manually:

```powershell
cd "v:\Aion_IDE\Noesis_v1"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -e ".[api]"
```

---

## 5. Quick Start (5 Minutes)

### Step 1 — Start the server

```powershell
.\.venv\Scripts\Activate.ps1
noesis serve
```

### Step 2 — Open the dashboard

In your browser go to:

**http://localhost:8080**

### Step 3 — Teach it three facts

In **Memory Chat**, type these one at a time and click **Remember & Recall**:

1. `my name is veera`
2. `I am building Noesis for AI memory systems`
3. `I use FastAPI and Redis for backend scaling`

### Step 4 — Ask it back

Type:

- `what is my name`
- `what is my Noesis project about`
- `what backend technologies do I use`

You should see **Stored** and **Recall** messages with the right context.

### Step 5 — Look at the graph

The **Knowledge Graph** (middle panel) shows concepts as dots and relationships as lines. Click **Refresh Graph** if needed.

**Congratulations — you just used Noesis.**

---

## 6. Using the Web Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  Noesis          Memories | Graph | Compression | Agent │
├──────────────┬──────────────────────┬───────────────────────┤
│ MEMORY CHAT  │  KNOWLEDGE GRAPH     │  COMPRESSED MEMORIES  │
│              │                      │                       │
│ Type here    │  [interactive graph] │  Insight cards        │
│              │                      │                       │
│ [Remember &  │  [Explore] [Refresh] │  [Forget] [Demo]    │
│  Recall]     │                      │                       │
└──────────────┴──────────────────────┴───────────────────────┘
```

### Memory Chat (left)

| Action | What happens |
|--------|----------------|
| Type a message | Noesis **stores** compressed meaning |
| Click Remember & Recall | Also **finds** related past memories |
| **Stored:** line | What was saved (the insight, not raw text) |
| **Recall:** line | What past memories match your message |

**Good things to store:**

- Facts about you (name, goals, preferences)
- Things you learned (technologies, problems solved)
- Workflows (Docker → Redis → Nginx)
- Events (deployed X on date Y)

**Ignored (low value):**

- `ok`, `thanks`, `hi`, very short noise

### Knowledge Graph (middle)

- **Dots** = concepts (FastAPI, Redis, Veera, etc.)
- **Lines** = relationships (relates_to, associated)
- **Explore** — type a concept name (e.g. `Fastapi`) and click Explore
- **Refresh Graph** — reload after new memories

The graph has a **fixed height** — it should not scroll endlessly. If it looks empty, add memories via chat first.

### Compressed Memories (right)

Lists what Noesis actually keeps:

| Badge | Meaning |
|-------|---------|
| **episodic** | A specific event |
| **semantic** | General knowledge / facts |
| **procedural** | A workflow or sequence |
| **insight** | High-level conclusion after many related inputs |

**Buttons:**

- **Run Forgetting Cycle** — removes weak/old redundant memories
- **Demo Compression** — shows how 5 raw messages become fewer insights

---

## 7. Using the Command Line

Activate the environment first:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Core commands

```powershell
# Store a memory
noesis remember "User deployed Redis for FastAPI scaling"

# Find related memories
noesis recall "backend scaling"

# Explain how recall works (graph vs vector DB)
noesis explain-query "FastAPI Redis"

# List all memories
noesis list

# Engine statistics
noesis stats

# Export portable memory file
noesis export M-ABC12345

# Import from another agent
noesis import data\sync_exports\agent-default_M-xxx.json --agent remote-agent

# Run forgetting
noesis forget-cycle
```

### Server and demos

```powershell
noesis serve              # Web dashboard
noesis demo               # Full pipeline demo
noesis innovation         # 5 innovations vs traditional AI
noesis multi-agent        # Two agents sharing memory
noesis chat               # Terminal chat with memory
```

### Recall modes

```powershell
noesis recall "scaling" --mode hybrid    # default — graph + meaning
noesis recall "scaling" --mode graph      # concept links only
noesis recall "scaling" --mode semantic   # similarity only
```

---

## 8. Using Python in Your Code

### Basic engine

```python
from noesis import NoesisEngine

engine = NoesisEngine()  # uses data/noesis.db

# Remember
result = engine.remember("my name is veera")
print(result["summary"])       # Profile: User's name is Veera.
print(result["memory_id"])     # M-XXXXXXXX

# Recall
contexts = engine.recall("what is my name")
for ctx in contexts:
    print(ctx.summary)
    print(ctx.confidence)

# Compare vs storing raw chat
print(engine.compare_with_traditional([
    "User asked about Redis",
    "User asked about async workers",
    "User asked about scaling",
]))
```

### Persistent agent (easier wrapper)

```python
from noesis.agents import PersistentAgent

agent = PersistentAgent(agent_id="my-assistant")

response = agent.chat("I am learning FastAPI with Redis")
print(response["memory_context"])

# Use with any LLM — paste into system prompt:
print(response["suggested_system_prompt"])
```

### LangChain (optional)

```powershell
pip install -e ".[agents]"
```

```python
from noesis.agents import NoesisMemory

memory = NoesisMemory()
lc_memory = memory.langchain_memory  # use in LangChain chains
```

---

## 9. Understanding Memory Types

Noesis organizes memory like cognitive science:

| Type | What it stores | Example |
|------|----------------|---------|
| **Episodic** | A specific event | “User deployed Redis on May 20” |
| **Semantic** | Facts and knowledge | “User’s name is Veera” |
| **Procedural** | Steps / workflows | “Docker → Redis → Nginx → Gunicorn” |
| **Insight** | Pattern after many events | “User specializes in backend scaling” |

**Many short messages about the same topic** → eventually become one **insight**.

---

## 10. The Five Innovations

### 1. Semantic Compression

**Before:** 5 separate chat messages stored as 5 chunks.  
**After:** 1 insight — “User is learning backend scaling with FastAPI and Redis.”

**Try:** Dashboard → **Demo Compression** button.

---

### 2. Symbolic Portable Memory

Memories are packed into small **bytecode packets** (not just database rows). You can **export** and **import** them — like moving a memory file to another machine.

```powershell
noesis export M-ABC12345
# File appears in data\sync_exports\
```

---

### 3. Distributed Shared Memory

Agent A learns something → exports packet → Agent B imports → B “knows” it without the original conversation.

```powershell
python examples\multi_agent_demo.py
```

Or over LAN (mesh server):

```powershell
# Machine 1
noesis mesh-serve --port 8765

# Machine 2
noesis sync-pull http://192.168.1.10:8765
```

---

### 4. Knowledge Graph Recall

Concepts link together:

```
FastAPI ↔ Redis ↔ Async Workers ↔ Scalability
```

When you ask about “scaling”, Noesis walks the graph — not just “text that looks similar.”

**Try:** `noesis explain-query "FastAPI Redis"`

---

### 5. Adaptive Forgetting

- Low-value messages (`ok`, `thanks`) → skipped or removed
- Important memories → strengthened when recalled
- Duplicate memories → merged

```powershell
noesis forget-cycle
```

---

## 11. Multi-Agent Memory Sharing

**Scenario:** Laptop agent learns from user; server agent needs the same knowledge.

```
Agent A (your PC)                    Agent B (another PC)
     │                                      │
     │  remember("deployed Redis")          │
     │                                      │
     │  export memory packet ──────────────►│  import packet
     │                                      │
     │                                      │  recall("Redis")
```

**Demo:**

```powershell
python examples\multi_agent_demo.py
```

---

## 12. REST API Reference

Start server: `noesis serve`  
Docs: **http://localhost:8080/docs**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/health` | GET | Status check |
| `/remember` | POST | Store memory `{"text": "..."}` |
| `/recall` | POST | Find memories `{"query": "..."}` |
| `/chat` | POST | Remember + recall in one call |
| `/memories` | GET | List all memories |
| `/graph` | GET | Full knowledge graph |
| `/graph/{concept}` | GET | Subgraph around a concept |
| `/compare` | POST | Demo compression `{"texts": [...]}` |
| `/forget` | POST | Run forgetting cycle |
| `/stats` | GET | Engine statistics |

**Example (PowerShell):**

```powershell
$body = '{"text": "my name is veera"}' 
Invoke-RestMethod -Uri http://localhost:8080/remember -Method POST -Body $body -ContentType "application/json"
```

---

## 13. Demos and Examples

| File | Command | What it shows |
|------|---------|---------------|
| `examples/demo_workflow.py` | `python examples\demo_workflow.py` | Full 10-step pipeline |
| `examples/innovation_demo.py` | `python examples\innovation_demo.py` | All 5 vs traditional AI |
| `examples/multi_agent_demo.py` | `python examples\multi_agent_demo.py` | Collective memory |
| `examples/chat_agent_demo.py` | `noesis chat` | Interactive terminal agent |

---

## 14. Configuration

Edit `config/settings.yaml`:

```yaml
engine:
  agent_id: "agent-default"    # Your agent's name

storage:
  path: "data/noesis.db"    # Where memories are saved

semantic:
  min_importance: 0.15         # Lower = store more messages
  similarity_threshold: 0.75   # Recall strictness

sync:
  mesh_port: 8765              # LAN sync port

api:
  port: 8080                   # Dashboard port
```

Copy `.env.example` to `.env` for environment overrides.

---

## 15. Troubleshooting

### Dashboard does not open

- Check terminal shows: `Uvicorn running on http://127.0.0.1:8080`
- Try: http://127.0.0.1:8080
- Firewall: allow Python on port 8080

### “Recalled 0 related memories”

- Store a fact first, then ask about it
- Use specific words from what you stored
- For names: say `my name is X` first, then `what is my name`
- Hard refresh browser: **Ctrl+Shift+R**

### Graph panel empty or too long

- Add memories via chat, then click **Refresh Graph**
- Hard refresh after updates (**Ctrl+Shift+R**)
- Graph should be ~300px tall, not endless scroll

### First command is slow

- First run downloads embedding model (~90MB) — normal
- Later runs are faster

### Tests

```powershell
pytest tests/ -v
```

Expected: all tests pass.

### Reset all memories

Delete the database file and restart:

```powershell
Remove-Item data\noesis.db -ErrorAction SilentlyContinue
noesis serve
```

---

## 16. Noesis Presentation Tips

### 30-second pitch

> “AI assistants forget users every session. Noesis is a cognitive memory engine that compresses experiences into insights, maps concept relationships, packages memory symbolically, syncs across agents, and forgets low-value data — moving beyond raw chat logs and vector databases.”

### 5-minute live demo order

1. Open dashboard (`noesis serve`)
2. Store 3 facts in chat (name, project, tech stack)
3. Ask them back — show recall works
4. Show knowledge graph updating
5. Click **Demo Compression**
6. Run `python examples\multi_agent_demo.py` — collective memory

### Slide titles (suggested)

1. Problem: AI Has No Real Long-Term Memory  
2. Solution: Noesis Architecture  
3. Innovation 1–5 (one slide each)  
4. Live Demo  
5. Results: Compression ratio, graph size, tests  
6. Future Work: LLM integration, Neo4j, edge deployment  

More detail: [NOESIS_PRESENTATION.md](NOESIS_PRESENTATION.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 17. Glossary

| Term | Meaning |
|------|---------|
| **Semantic compression** | Storing meaning, not full text |
| **Symbolic packet** | Small portable binary memory file |
| **Knowledge graph** | Network of concepts and relationships |
| **Cluster** | Group of related memories merged together |
| **Insight** | High-level summary after many similar events |
| **Recall** | Finding relevant memories for a query |
| **Embedding** | AI number-vector representing meaning |
| **Forgetting cycle** | Removing weak/redundant memories |
| **Mesh sync** | Sharing memories between agents over network |
| **Importance score** | 0–1 rating of how valuable a memory is |

---

## Where to Get Help

| Resource | Location |
|----------|----------|
| Technical architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Developer README | [README.md](README.md) |
| Presentation script | [NOESIS_PRESENTATION.md](NOESIS_PRESENTATION.md) |
| API docs (when server running) | http://localhost:8080/docs |

---

## Quick Reference Card

```
START:     noesis serve  →  http://localhost:8080
REMEMBER:  Type in chat  OR  noesis remember "..."
RECALL:    Ask in chat    OR  noesis recall "..."
GRAPH:     Middle panel   OR  noesis graph Fastapi
STATS:     Header bar      OR  noesis stats
DEMO:      innovation / multi-agent / demo_workflow
RESET:     Delete data\noesis.db
```

---

*Noesis v1.0 — Semantic + Symbolic AI Memory Engine. You built a memory brain, not just another chatbot.*
