#!/usr/bin/env python3
"""OSTI Knowledge Graph — MCP server (model-based access).

Exposes the KG as MCP tools so any model can traverse the graph:
  kg_stats              - totals by node-kind and edge-relation
  kg_search             - full-text search nodes (optional kind filter)
  kg_node               - node detail + in/out degree
  kg_neighbors          - a node's neighborhood subgraph
  kg_paper_entities     - all entities+authors for one paper (by OSTI id)
  kg_find_path          - shortest path between two nodes
  kg_top_connected      - most-referenced nodes of a kind (e.g. top facilities)

Transport: streamable-HTTP on 0.0.0.0:8098 (tailnet-reachable), matching the
existing OSTI-x-cards MCP pattern. Reads osti_kg.sqlite read-only.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kg_query as kg
from fastmcp import FastMCP

mcp = FastMCP("osti-knowledge-graph")

@mcp.tool()
def kg_stats() -> dict:
    """Return knowledge-graph totals: node counts by kind, edge counts by relation."""
    return kg.stats()

@mcp.tool()
def kg_search(query: str, kind: str = "", limit: int = 25) -> list:
    """Full-text search graph nodes by label. Optional kind filter
    (paper|author|facility|instrument|model|data|simulation|workflow|agent).
    Returns [{id,label,kind}]. Use the id with other tools."""
    return kg.search(query, kind or None, min(limit, 100))

@mcp.tool()
def kg_node(node_id: str) -> dict:
    """Get a node's detail (kind, label, props) and in/out degree. node_id is
    like 'paper:942684', 'facility:1762836', or 'author:<hash>'."""
    n = kg.get_node(node_id)
    return n or {"error": "node not found", "node_id": node_id}

@mcp.tool()
def kg_neighbors(node_id: str, rel: str = "", direction: str = "both", limit: int = 60) -> dict:
    """Return the neighborhood subgraph around node_id: {center, nodes, edges}.
    Optional rel filter (DESCRIBES|AUTHORED_BY|SHARES_AUTHOR). direction in
    both|in|out. Degree-capped by limit."""
    return kg.neighbors(node_id, rel or None, direction, min(limit, 300))

@mcp.tool()
def kg_paper_entities(osti_id: str) -> dict:
    """Return all extracted entities (models, data, instruments, facilities,
    simulations, workflows, agents) and authors for one paper, by OSTI id."""
    return kg.paper_entities(osti_id)

@mcp.tool()
def kg_find_path(node_a: str, node_b: str, max_hops: int = 4) -> dict:
    """Find the shortest path between two nodes (undirected). Returns the path
    as a list of node ids, or null if none within max_hops (<=6)."""
    p = kg.find_path(node_a, node_b, min(max_hops, 6))
    return {"a": node_a, "b": node_b, "path": p, "hops": (len(p) - 1) if p else None}

@mcp.tool()
def kg_top_connected(kind: str, limit: int = 20) -> list:
    """Most-referenced nodes of a kind, by how many papers describe them.
    e.g. kind='facility' -> top DOE user facilities. Returns [{id,label,count}]."""
    return kg.top_connected(kind, min(limit, 100))

if __name__ == "__main__":
    port = int(os.environ.get("KG_MCP_PORT", "8098"))
    mcp.run(transport="http", host="0.0.0.0", port=port)
