# Aion_IDE

Capstone workspace: **AION** multi-agent coding IDE + **Noesis** persistent memory.

## GitHub

| Repo | Use when |
|------|----------|
| **[Aion_IDE](https://github.com/veera-1175/Aion_IDE)** | Full capstone workspace (`Aion/` + `Noesis_v1/`) |
| **[Noesis](https://github.com/veera-1175/Noesis)** | Noesis only — clone and run on another machine without Aion |

## Projects

| Folder | Description |
|--------|-------------|
| **[Noesis_v1/](Noesis_v1/)** | Semantic + symbolic distributed AI **memory engine** |
| **[Aion/](Aion/)** | Multi-agent **software engineering** IDE powered by Noesis |

```
Aion_IDE/
├── Noesis_v1/     ← Core memory brain
└── Aion/             ← AION coding IDE (uses Noesis)
```

---

## Quick Start

### Noesis (memory engine + dashboard, optional)

```powershell
cd "v:\Aion_IDE\Noesis_v1"
.\scripts\setup.ps1
noesis serve
```

→ http://localhost:8080

### AION (main IDE — what you usually run)

```powershell
cd "v:\Aion_IDE\Aion"
.\scripts\setup.ps1
aion serve
# Or from repo root: start-aion.bat
```

→ http://localhost:8090

---

## Documentation

| Project | Guide |
|---------|-------|
| Noesis | [Noesis_v1/USER_GUIDE.md](Noesis_v1/USER_GUIDE.md) |
| AION | [Aion/README.md](Aion/README.md) |
| Presentation | [Noesis_v1/NOESIS_PRESENTATION.md](Noesis_v1/NOESIS_PRESENTATION.md) |
