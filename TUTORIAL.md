# Exploring the OSTI Datasets with the Knowledge Graph

A hands-on guide to using the OSTI Knowledge Graph (KG) to discover datasets,
models, instruments, facilities, and the papers and people connected to them.

The KG is built from the OSTI x-Cards corpus: **540,538 nodes** and
**2,748,864 edges** derived from 184K extracted cards across 77,309 papers.

There are three ways to use it, in rough order of how most people will reach for them:

1. **The web explorer** — point-and-click graph browsing (no code).
2. **The REST API** — scriptable queries (`curl`, Python, notebooks).
3. **The MCP server** — let an AI model/agent traverse the graph for you.

---

## 0. What's in the graph (the data model)

**Node kinds** (what things are):

| kind | count | what it is |
|---|---|---|
| `author` | 278,874 | paper authors |
| `paper` | 77,309 | OSTI publications (the hub of everything) |
| `instrument` | 47,916 | detectors, beamlines, microscopes, telescopes |
| `facility` | 39,853 | DOE user facilities (APS, NERSC, SNS…) |
| `simulation` | 38,037 | simulation codes / runs |
| `workflow` | 32,560 | computational workflows / pipelines |
| `model` | 13,256 | models (ML and physical) |
| `data` | 11,085 | **datasets** |
| `agent` | 1,648 | software agents |

**Edge relations** (how they connect):

| relation | meaning |
|---|---|
| `DESCRIBES` | an entity card → the paper it was extracted from |
| `AUTHORED_BY` | paper → author |
| `SHARES_AUTHOR` | paper ↔ paper (co-authorship link, 1.7M edges) |

**ID format:** every node id is `<kind>:<osti_id>` for entities/papers
(e.g. `data:1490807`, `facility:1762836`, `paper:942684`) or
`author:<hash>` for authors. Entity cards are *per-paper* — the same facility
(say, APS) appears once per paper that uses it, which is how we count
"APS appears in 5,580 papers."

---

## 1. The web explorer (no code)

Open **http://100.86.220.115:8097/** on the tailnet.

**The workflow:**

1. **Search.** Type in the box (e.g. `advanced photon source`, `HydraGNN`,
   a dataset name, or an author). Optionally narrow by kind in the dropdown
   (e.g. `data` to find only datasets).
2. **Click a result.** Its neighborhood renders as a force-directed graph —
   the entity in the center, connected papers/authors/other entities around it.
3. **Expand.** Click any node in the graph to pull in *its* neighbors. Keep
   clicking to walk the graph (paper → its author → that author's other papers
   → those papers' datasets…).
4. **Inspect.** The left panel shows the selected node's kind, in/out degree,
   properties (year, DOI), and an "open on OSTI" link for papers.
5. **Pan/zoom** with mouse drag and scroll; drag nodes to rearrange.

**A worked exploration — "what datasets come out of NERSC work?"**
Search `NERSC`, filter kind = `facility`, click a result → you land on a NERSC
facility node wired to its paper → click the paper → its `data`, `model`, and
`simulation` cards fan out → click a dataset to see which other papers share it.

---

## 2. The REST API (scriptable)

Base URL: `http://100.86.220.115:8097/api`

### Graph overview
```bash
curl -s http://100.86.220.115:8097/api/stats | python3 -m json.tool
```

### Search for datasets by name
```bash
# All "data" nodes (datasets) matching a term:
curl -s "http://100.86.220.115:8097/api/search?q=genome&kind=data&limit=10"
```
Returns `[{id, label, kind}]`. Leave off `&kind=` to search every kind at once.

### Find the most-used things of a kind
This is the fastest way to find the **important** datasets/facilities/instruments:
```bash
# Top datasets (by number of papers that describe them):
curl -s "http://100.86.220.115:8097/api/top/data?limit=20"

# Top facilities (verified live):
curl -s "http://100.86.220.115:8097/api/top/facility?limit=5"
# -> Advanced Photon Source (5580), Advanced Light Source (2244),
#    NERSC (1604), NSLS-II (1479), Spallation Neutron Source (1211)

# Top instruments:  ATLAS (319), ALICE (236), ATLAS detector (191) ...
# Top models:       DER-CAM (19), HydraGNN (8), Celeritas (7) ...
```

### Inspect a single node
```bash
curl -s "http://100.86.220.115:8097/api/node/facility:1762836"
# -> {id, kind:"facility", label:"Advanced Photon Source",
#     props:{...}, degree_out, degree_in}
```

### Explore a node's neighborhood (the core traversal)
```bash
# Everything one hop from a node (nodes + edges):
curl -s "http://100.86.220.115:8097/api/neighbors/data:1490807?limit=60"

# Narrow to a relation or direction:
curl -s "http://100.86.220.115:8097/api/neighbors/paper:942684?rel=AUTHORED_BY&direction=out"
```

### Everything a paper touches
```bash
# All entities + authors extracted from one paper, by OSTI id:
curl -s "http://100.86.220.115:8097/api/paper/942684"
# -> 7 nodes / 6 edges: the paper + its authors + instruments + related papers
```

### Connect two things (path finding)
```bash
# Shortest path between two nodes (e.g. does a dataset link to a facility?):
curl -s "http://100.86.220.115:8097/api/path?a=data:1490807&b=facility:1762836&max_hops=4"
# -> {a, b, path:[...node ids...], hops:N}  (path null if none within max_hops)
```

### A complete Python example — "dataset discovery"
```python
import requests
B = "http://100.86.220.115:8097/api"

# 1. Find the top datasets in the corpus
top = requests.get(f"{B}/top/data", params={"limit": 15}).json()
for d in top:
    print(f"{d['count']:4d} papers  {d['label']}  ({d['id']})")

# 2. Pick one and see which papers use it
ds = top[0]["id"]
nb = requests.get(f"{B}/neighbors/{ds}").json()
papers = [n for n in nb["nodes"] if n["kind"] == "paper"]
print(f"\n{ds} appears in these papers:")
for p in papers[:10]:
    print("  ", p["label"])

# 3. For one of those papers, pull its full entity set
osti = papers[0]["id"].split(":")[1]
full = requests.get(f"{B}/paper/{osti}").json()
kinds = {}
for n in full["nodes"]:
    kinds.setdefault(n["kind"], []).append(n["label"])
print("\nThat paper's entities by kind:")
for k, v in kinds.items():
    print(f"  {k}: {', '.join(x[:30] for x in v[:4])}")
```

---

## 3. The MCP server (model-based access)

Let an AI agent traverse the graph conversationally. The server speaks MCP
over streamable-HTTP at **http://100.86.220.115:8098/mcp/**.

### Register it (Hermes `config.yaml`)
```yaml
mcp_servers:
  osti-kg:
    transport: http
    url: http://100.86.220.115:8098/mcp/
```
(Any MCP client works — Claude Desktop, Hermes, custom clients. Point it at the
same URL.)

### The 7 tools the model gets
| tool | use it to |
|---|---|
| `kg_stats` | get graph totals by kind/relation |
| `kg_search` | find nodes by name (`query`, optional `kind`, `limit`) |
| `kg_node` | get one node's detail + degree |
| `kg_neighbors` | expand a node's neighborhood (`rel`, `direction`, `limit`) |
| `kg_paper_entities` | all entities+authors for a paper (`osti_id`) |
| `kg_find_path` | shortest path between two nodes |
| `kg_top_connected` | most-referenced nodes of a kind |

### What you can now just *ask*
Once registered, you ask the agent in plain language and it chains the tools:

- *"What are the top 10 datasets in the OSTI corpus and which facilities are they associated with?"*
  → `kg_top_connected(data)` → `kg_neighbors` on each → `kg_search`/`kg_node` for facilities.
- *"Find datasets related to the Advanced Photon Source and list the papers that use them."*
  → `kg_search("advanced photon source", facility)` → `kg_neighbors` → filter `data` + `paper`.
- *"Is there a connection between dataset X and model Y?"*
  → `kg_find_path(data:X, model:Y)`.
- *"Who are the most prolific authors working with NERSC, and what datasets do they produce?"*

### Verify the server (quick smoke)
```bash
cd ~/code/osti-kg && ./.venv/bin/python mcp_smoke.py
# -> lists all 7 tools and calls each; ends with "ALL TOOLS CALLABLE — MCP OK"
```

---

## 4. Common exploration recipes

**"Show me the DOE user facilities, ranked."**
`GET /api/top/facility?limit=25` — instantly ranks APS, ALS, NERSC, NSLS-II, SNS…

**"What datasets exist for topic X?"**
`GET /api/search?q=X&kind=data` → for each hit, `GET /api/neighbors/<id>` to see
the papers; `GET /api/paper/<osti>` to see co-located models/simulations.

**"Trace a research thread."**
Start at a paper → `neighbors` with `rel=AUTHORED_BY` → pick an author →
`neighbors` on the author (their papers via `SHARES_AUTHOR` partners) → each
paper's datasets. The web explorer does this visually with clicks.

**"Map the co-authorship network around a lab's work."**
Start at any paper, repeatedly expand `SHARES_AUTHOR` edges — the 1.7M-edge
co-authorship layer reveals collaboration clusters.

---

## 5. Notes & caveats

- **Read-only, fast, degree-capped.** Traversals are capped (default 60, max
  300 neighbors) so a mega-hub like the ATLAS collaboration can't blow up a
  query. Raise `limit` when you need more.
- **Entity cards are per-paper.** To get the *aggregate* importance of a thing
  (e.g. "how many papers use NERSC"), use `top_connected` / the count it returns,
  not the degree of a single `facility:<id>` node.
- **Labels can be empty.** A few extracted cards have blank labels (shown by id).
- **The graph refreshes** whenever the builder re-runs
  (`~/code/osti-kg/build_kg.py`) against updated cards — zero impact on the
  extraction farm.
- **Source of truth:** `~/code/osti-kg/osti_kg.sqlite` (399 MB). Everything
  above (web, API, MCP) reads this one file.

---

*Services:* web `http://100.86.220.115:8097/` · MCP `http://100.86.220.115:8098/mcp/`
*Code:* `~/code/osti-kg/` (`build_kg.py`, `kg_query.py`, `kg_api.py`, `kg_mcp.py`)
