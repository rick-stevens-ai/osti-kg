#!/usr/bin/env python3
"""Smoke-test the KG MCP server over streamable-HTTP using the fastmcp client."""
import asyncio, json
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8098/mcp/") as c:
        tools = await c.list_tools()
        print("TOOLS:", [t.name for t in tools])
        r = await c.call_tool("kg_stats", {})
        s = json.loads(r.content[0].text) if r.content else {}
        print("STATS nodes/edges:", s.get("nodes"), s.get("edges"))
        r = await c.call_tool("kg_search", {"query": "advanced photon source", "kind": "facility", "limit": 2})
        print("SEARCH:", r.content[0].text[:160])
        r = await c.call_tool("kg_top_connected", {"kind": "facility", "limit": 3})
        print("TOP FACILITIES:", r.content[0].text[:200])
        r = await c.call_tool("kg_paper_entities", {"osti_id": "942684"})
        pe = json.loads(r.content[0].text)
        print("PAPER 942684: nodes=", len(pe["nodes"]), "edges=", len(pe["edges"]))
        print("ALL TOOLS CALLABLE — MCP OK")

asyncio.run(main())
