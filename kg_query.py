#!/opt/homebrew/bin/python3.13
"""Shared KG query engine over osti_kg.sqlite.

Used by both the FastAPI web API and the MCP server. Read-only, fast,
degree-capped so a mega-hub (ATLAS collaboration) can't blow up a query.
"""
import sqlite3, os, json

KG = os.environ.get("OSTI_KG_DB", os.path.expanduser("~/code/osti-kg/osti_kg.sqlite"))

def _conn():
    c = sqlite3.connect(f"file:{KG}?mode=ro", uri=True, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def stats():
    c = _conn()
    try:
        nn = c.execute("SELECT count(*) FROM nodes").fetchone()[0]
        ne = c.execute("SELECT count(*) FROM edges").fetchone()[0]
        bykind = {r[0]: r[1] for r in c.execute("SELECT kind,count(*) FROM nodes GROUP BY kind ORDER BY 2 DESC")}
        byrel = {r[0]: r[1] for r in c.execute("SELECT rel,count(*) FROM edges GROUP BY rel ORDER BY 2 DESC")}
        return {"nodes": nn, "edges": ne, "node_kinds": bykind, "edge_rels": byrel, "db": KG}
    finally:
        c.close()

def search(q, kind=None, limit=25):
    """Full-text search node labels. Optional kind filter."""
    c = _conn()
    try:
        q = (q or "").strip()
        if not q:
            return []
        # FTS5 prefix match on each term
        terms = " ".join(f'"{t}"*' for t in q.split() if t)
        sql = ("SELECT f.id, f.label, f.kind FROM node_fts f "
               "WHERE node_fts MATCH ? ")
        args = [terms]
        if kind:
            sql += "AND f.kind = ? "
            args.append(kind)
        sql += "LIMIT ?"
        args.append(limit)
        rows = c.execute(sql, args).fetchall()
        return [{"id": r["id"], "label": r["label"], "kind": r["kind"]} for r in rows]
    finally:
        c.close()

def get_node(nid):
    c = _conn()
    try:
        r = c.execute("SELECT id,kind,label,props FROM nodes WHERE id=?", (nid,)).fetchone()
        if not r:
            return None
        deg_out = c.execute("SELECT count(*) FROM edges WHERE src=?", (nid,)).fetchone()[0]
        deg_in = c.execute("SELECT count(*) FROM edges WHERE dst=?", (nid,)).fetchone()[0]
        return {"id": r["id"], "kind": r["kind"], "label": r["label"],
                "props": json.loads(r["props"] or "{}"),
                "degree_out": deg_out, "degree_in": deg_in}
    finally:
        c.close()

def neighbors(nid, rel=None, direction="both", limit=60):
    """Return neighboring nodes + the connecting edges. Degree-capped."""
    c = _conn()
    try:
        edges, seen = [], {}
        def add(src, r, dst):
            other = dst if src == nid else src
            if other not in seen:
                nr = c.execute("SELECT id,kind,label FROM nodes WHERE id=?", (other,)).fetchone()
                if nr:
                    seen[other] = {"id": nr["id"], "kind": nr["kind"], "label": nr["label"]}
            edges.append({"src": src, "rel": r, "dst": dst})
        if direction in ("out", "both"):
            sql = "SELECT src,rel,dst FROM edges WHERE src=?"
            args = [nid]
            if rel: sql += " AND rel=?"; args.append(rel)
            sql += " LIMIT ?"; args.append(limit)
            for e in c.execute(sql, args): add(e["src"], e["rel"], e["dst"])
        if direction in ("in", "both"):
            sql = "SELECT src,rel,dst FROM edges WHERE dst=?"
            args = [nid]
            if rel: sql += " AND rel=?"; args.append(rel)
            sql += " LIMIT ?"; args.append(limit)
            for e in c.execute(sql, args): add(e["src"], e["rel"], e["dst"])
        center = get_node(nid)
        nodes = [center] if center else []
        nodes += list(seen.values())
        return {"center": nid, "nodes": nodes, "edges": edges,
                "truncated": len(edges) >= limit}
    finally:
        c.close()

def paper_entities(osti_id):
    """All entity cards + authors for a paper."""
    pid = osti_id if osti_id.startswith("paper:") else f"paper:{osti_id}"
    return neighbors(pid, limit=200)

def find_path(a, b, max_hops=4):
    """BFS shortest path a->b on the undirected graph. Hub-capped."""
    c = _conn()
    try:
        if a == b:
            return [a]
        from collections import deque
        prev = {a: None}
        dq = deque([(a, 0)])
        while dq:
            cur, d = dq.popleft()
            if d >= max_hops:
                continue
            rows = c.execute(
                "SELECT dst AS o FROM edges WHERE src=? UNION SELECT src AS o FROM edges WHERE dst=? LIMIT 400",
                (cur, cur)).fetchall()
            for r in rows:
                o = r["o"]
                if o not in prev:
                    prev[o] = cur
                    if o == b:
                        path = [b]
                        while prev[path[-1]] is not None:
                            path.append(prev[path[-1]])
                        return list(reversed(path))
                    dq.append((o, d + 1))
        return None
    finally:
        c.close()

def top_connected(kind, limit=20):
    """Most-referenced nodes of a kind (by DESCRIBES in-degree for entities)."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT n.id, n.label, count(*) c FROM edges e JOIN nodes n ON n.id=e.src "
            "WHERE e.rel='DESCRIBES' AND n.kind=? GROUP BY n.label ORDER BY c DESC LIMIT ?",
            (kind, limit)).fetchall()
        return [{"id": r["id"], "label": r["label"], "count": r["c"]} for r in rows]
    finally:
        c.close()

if __name__ == "__main__":
    import pprint
    pprint.pprint(stats())
    print("--- search 'photon' ---")
    pprint.pprint(search("photon", limit=5))
    print("--- top facilities ---")
    pprint.pprint(top_connected("facility", 5))
