#!/opt/homebrew/bin/python3.13
"""Build an OSTI knowledge graph from the existing x-cards DB.

Nodes: papers, + 7 card-entity types (model/data/instrument/facility/agent/
simulation/workflow), authors.
Edges: card DESCRIBES paper; paper AUTHORED_BY author; paper CO_AUTHOR paper
(shared author); entity MENTIONED_IN paper.

Reads ~/code/osti-cards-site/data/osti_cards.sqlite (read-only).
Writes a self-contained graph SQLite at ~/code/osti-kg/osti_kg.sqlite
(nodes + edges tables) — portable, queryable, and loadable into Neo4j/networkx
later. Zero impact on the pecans extraction farm.

Idempotent: DROPs+rebuilds graph tables each run (fast, deterministic).
"""
import sqlite3, os, json, hashlib, time, re

CARDS = os.path.expanduser("~/code/osti-cards-site/data/osti_cards.sqlite")
OUTDIR = os.path.expanduser("~/code/osti-kg")
KG = os.path.join(OUTDIR, "osti_kg.sqlite")
os.makedirs(OUTDIR, exist_ok=True)

def norm_author(a):
    return re.sub(r"\s+", " ", a.strip()).strip(" ,;").lower()

def main():
    t0 = time.time()
    src = sqlite3.connect(f"file:{CARDS}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    g = sqlite3.connect(KG)
    g.executescript("""
    DROP TABLE IF EXISTS nodes;
    DROP TABLE IF EXISTS edges;
    CREATE TABLE nodes(id TEXT PRIMARY KEY, kind TEXT, label TEXT, props TEXT);
    CREATE TABLE edges(src TEXT, rel TEXT, dst TEXT, props TEXT);
    CREATE INDEX ix_nodes_kind ON nodes(kind);
    CREATE INDEX ix_edges_src ON edges(src);
    CREATE INDEX ix_edges_dst ON edges(dst);
    CREATE INDEX ix_edges_rel ON edges(rel);
    """)
    nodes = {}   # id -> (kind, label, props)
    edges = set()  # (src, rel, dst)

    def add_node(nid, kind, label, props=None):
        if nid not in nodes:
            nodes[nid] = (kind, label, json.dumps(props or {}))

    # author -> set of papers (for co-author edges)
    author_papers = {}

    rows = src.execute("SELECT osti_id,year,mode,title,authors,doi,url FROM cards")
    n_cards = 0
    for r in rows:
        n_cards += 1
        osti = (r["osti_id"] or "").strip()
        if not osti:
            continue
        paper_id = f"paper:{osti}"
        add_node(paper_id, "paper", (r["title"] or osti)[:200],
                 {"year": r["year"], "doi": r["doi"], "url": r["url"]})
        # entity node per card (mode = entity type)
        mode = (r["mode"] or "unknown").strip()
        ent_id = f"{mode}:{osti}"
        add_node(ent_id, mode, (r["title"] or "")[:200], {"osti_id": osti, "year": r["year"]})
        edges.add((ent_id, "DESCRIBES", paper_id))
        # authors
        auth_raw = r["authors"] or ""
        for a in re.split(r"[;|]|\band\b|,(?=\s*[A-Z])", auth_raw):
            a = norm_author(a)
            if len(a) < 4 or len(a) > 80:
                continue
            aid = "author:" + hashlib.md5(a.encode()).hexdigest()[:12]
            add_node(aid, "author", a.title())
            edges.add((paper_id, "AUTHORED_BY", aid))
            author_papers.setdefault(aid, set()).add(paper_id)

    # co-author edges (papers sharing >=1 author) — capped to avoid O(n^2) blowup
    coauth = 0
    for aid, papers in author_papers.items():
        pl = sorted(papers)
        if len(pl) > 50:   # a mega-author; skip pairwise (would explode)
            continue
        for i in range(len(pl)):
            for j in range(i+1, len(pl)):
                edges.add((pl[i], "SHARES_AUTHOR", pl[j]))
                coauth += 1

    g.executemany("INSERT OR IGNORE INTO nodes VALUES(?,?,?,?)",
                  [(nid, k, lbl, pr) for nid,(k,lbl,pr) in nodes.items()])
    g.executemany("INSERT INTO edges(src,rel,dst) VALUES(?,?,?)", list(edges))
    g.commit()

    # summary
    nn = g.execute("SELECT count(*) FROM nodes").fetchone()[0]
    ne = g.execute("SELECT count(*) FROM edges").fetchone()[0]
    bykind = dict(g.execute("SELECT kind,count(*) FROM nodes GROUP BY kind").fetchall())
    byrel = dict(g.execute("SELECT rel,count(*) FROM edges GROUP BY rel").fetchall())
    print(f"cards scanned: {n_cards}")
    print(f"nodes: {nn}  {bykind}")
    print(f"edges: {ne}  {byrel}")
    print(f"KG written: {KG}  ({time.time()-t0:.1f}s)")
    g.close(); src.close()

if __name__ == "__main__":
    main()
