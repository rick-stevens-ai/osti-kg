# OSTI Knowledge Graph

A knowledge graph built from the OSTI x-Cards corpus: **540,538 nodes** and
**2,748,864 edges** derived from 184K extracted cards across 77,309 papers.
Nodes include papers, authors, datasets, models, instruments, facilities,
simulations, and workflows; edges connect papers to everything they mention.

👉 **Start here: [TUTORIAL.md](TUTORIAL.md)** — a hands-on guide covering all
three access paths (web explorer, REST API, MCP server) with copy-paste examples.

## Components

| File | What it is |
|---|---|
| `build_kg.py` | Builds `osti_kg.sqlite` from the x-Cards corpus DB. |
| `kg_query.py` | Shared read-only query engine (FTS over labels, degree-capped traversal). |
| `kg_api.py` | FastAPI web explorer + REST API (embedded D3 graph SPA). |
| `kg_mcp.py` | MCP server (streamable-HTTP) exposing 7 graph tools to AI agents. |
| `mcp_smoke.py` | Smoke test for the MCP endpoints. |

## The data artifact

`osti_kg.sqlite` (~464 MB) is **not** committed (GitHub's 100 MB limit). Rebuild it
locally with `build_kg.py` against the x-Cards corpus DB, or copy it from the host
running the service.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install fastapi uvicorn fastmcp

# Web explorer + REST API
python kg_api.py          # -> http://localhost:8097

# MCP server for agents
python kg_mcp.py          # -> http://localhost:8098/mcp/
```

See **[TUTORIAL.md](TUTORIAL.md)** for the full walkthrough.
