#!/opt/homebrew/bin/python3.13
"""OSTI Knowledge Graph — web API + companion exploration site.

Serves:
  GET  /                      -> the exploration SPA
  GET  /api/stats             -> graph totals by kind/rel
  GET  /api/search?q=&kind=   -> FTS node search
  GET  /api/node/{id}         -> node detail + degree
  GET  /api/neighbors/{id}    -> neighborhood subgraph (nodes+edges)
  GET  /api/paper/{osti_id}   -> a paper's full entity neighborhood
  GET  /api/path?a=&b=        -> shortest path between two nodes
  GET  /api/top/{kind}        -> most-referenced nodes of a kind

Reads ~/code/osti-kg/osti_kg.sqlite (read-only). No farm impact.
"""
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import kg_query as kg

app = FastAPI(title="OSTI Knowledge Graph", version="1.0")

@app.get("/api/stats")
def api_stats():
    return kg.stats()

@app.get("/api/search")
def api_search(q: str = Query(...), kind: str | None = None, limit: int = 25):
    return kg.search(q, kind, min(limit, 100))

@app.get("/api/node/{nid:path}")
def api_node(nid: str):
    n = kg.get_node(nid)
    if not n:
        raise HTTPException(404, "node not found")
    return n

@app.get("/api/neighbors/{nid:path}")
def api_neighbors(nid: str, rel: str | None = None, direction: str = "both", limit: int = 60):
    return kg.neighbors(nid, rel, direction, min(limit, 300))

@app.get("/api/paper/{osti_id}")
def api_paper(osti_id: str):
    return kg.paper_entities(osti_id)

@app.get("/api/path")
def api_path(a: str, b: str, max_hops: int = 4):
    p = kg.find_path(a, b, min(max_hops, 6))
    return {"a": a, "b": b, "path": p, "hops": (len(p) - 1) if p else None}

@app.get("/api/top/{kind}")
def api_top(kind: str, limit: int = 20):
    return kg.top_connected(kind, min(limit, 100))

INDEX = """<!doctype html><html><head><meta charset=utf-8>
<title>OSTI Knowledge Graph Explorer</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);height:100vh;display:flex;flex-direction:column}
header{padding:10px 16px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0;color:var(--acc)}
#stats{color:var(--mut);font-size:12px}
input,select,button{background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:13px}
button{cursor:pointer}button:hover{border-color:var(--acc)}
#main{flex:1;display:flex;min-height:0}
#side{width:320px;border-right:1px solid var(--line);overflow:auto;padding:12px}
#graph{flex:1;position:relative}
.res{padding:7px 9px;border:1px solid var(--line);border-radius:6px;margin-bottom:6px;cursor:pointer}
.res:hover{border-color:var(--acc);background:var(--panel)}
.kind{display:inline-block;font-size:10px;padding:1px 6px;border-radius:10px;margin-right:6px;text-transform:uppercase}
.k-paper{background:#1f6feb33;color:#58a6ff}.k-author{background:#8957e533;color:#bc8cff}
.k-facility{background:#23863633;color:#3fb950}.k-instrument{background:#9e6a0333;color:#e3b341}
.k-model{background:#da373333;color:#ff7b72}.k-data{background:#1158c733;color:#79c0ff}
.k-simulation{background:#bf4b8a33;color:#ff9bce}.k-workflow{background:#0e766e33;color:#56d4bd}
.k-agent{background:#57606a33;color:#adbac7}
#detail{margin-top:14px;font-size:12px}#detail b{color:var(--acc)}
svg{width:100%;height:100%}.node circle{cursor:pointer;stroke:#0d1117;stroke-width:1.5}
.node text{font-size:10px;fill:var(--fg);pointer-events:none}
.link{stroke:#30363d;stroke-opacity:.6}.link-label{fill:var(--mut);font-size:8px}
.hint{color:var(--mut);font-size:12px;margin:8px 0}
</style></head><body>
<header>
  <h1>OSTI Knowledge Graph</h1>
  <input id=q placeholder="search entities, papers, authors..." style="width:260px" autofocus>
  <select id=kind><option value="">any kind</option>
    <option>paper</option><option>author</option><option>facility</option>
    <option>instrument</option><option>model</option><option>data</option>
    <option>simulation</option><option>workflow</option><option>agent</option></select>
  <button onclick=doSearch()>Search</button>
  <span id=stats></span>
</header>
<div id=main>
  <div id=side>
    <div class=hint>Search, then click a result to expand its neighborhood. Click any graph node to expand further.</div>
    <div id=results></div>
    <div id=detail></div>
  </div>
  <div id=graph><svg id=svg></svg></div>
</div>
<script>
const KCOL={paper:'#58a6ff',author:'#bc8cff',facility:'#3fb950',instrument:'#e3b341',model:'#ff7b72',data:'#79c0ff',simulation:'#ff9bce',workflow:'#56d4bd',agent:'#adbac7'};
let gnodes=new Map(), glinks=[], sim, svg=d3.select('#svg'), g=svg.append('g');
svg.call(d3.zoom().on('zoom',e=>g.attr('transform',e.transform)));
fetch('/api/stats').then(r=>r.json()).then(s=>{
  document.getElementById('stats').textContent=`${s.nodes.toLocaleString()} nodes · ${s.edges.toLocaleString()} edges`;});
function doSearch(){
  const q=document.getElementById('q').value, k=document.getElementById('kind').value;
  if(!q)return;
  fetch(`/api/search?q=${encodeURIComponent(q)}&kind=${k}&limit=30`).then(r=>r.json()).then(rows=>{
    const el=document.getElementById('results');
    el.innerHTML=rows.length?'':'<div class=hint>no matches</div>';
    rows.forEach(n=>{const d=document.createElement('div');d.className='res';
      d.innerHTML=`<span class="kind k-${n.kind}">${n.kind}</span>${n.label||n.id}`;
      d.onclick=()=>expand(n.id);el.appendChild(d);});
  });}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')doSearch();});
function expand(id){
  fetch(`/api/neighbors/${encodeURIComponent(id)}?limit=60`).then(r=>r.json()).then(sub=>{
    sub.nodes.forEach(n=>{if(n&&!gnodes.has(n.id))gnodes.set(n.id,{...n});});
    sub.edges.forEach(e=>{if(!glinks.find(l=>l.source.id===e.src&&l.target.id===e.dst&&l.rel===e.rel))
      glinks.push({source:e.src,target:e.dst,rel:e.rel});});
    showDetail(id);render();});}
function showDetail(id){
  fetch(`/api/node/${encodeURIComponent(id)}`).then(r=>r.json()).then(n=>{
    let h=`<b>${n.label||n.id}</b><br><span class="kind k-${n.kind}">${n.kind}</span>`;
    h+=`<br>out-degree ${n.degree_out} · in-degree ${n.degree_in}`;
    const p=n.props||{};for(const k in p)if(p[k])h+=`<br><span style=color:#8b949e>${k}:</span> ${p[k]}`;
    if(n.kind==='paper'&&p.url)h+=`<br><a href="${p.url}" target=_blank style=color:#58a6ff>open on OSTI</a>`;
    document.getElementById('detail').innerHTML=h;});}
function render(){
  const nodes=[...gnodes.values()];
  const links=glinks.map(l=>({...l,source:l.source.id||l.source,target:l.target.id||l.target}));
  g.selectAll('*').remove();
  const link=g.append('g').selectAll('line').data(links).join('line').attr('class','link');
  const node=g.append('g').selectAll('g').data(nodes,d=>d.id).join('g').attr('class','node')
    .call(d3.drag().on('start',ds).on('drag',dd).on('end',de));
  node.append('circle').attr('r',d=>d.kind==='paper'?8:6).attr('fill',d=>KCOL[d.kind]||'#888')
    .on('click',(e,d)=>expand(d.id));
  node.append('text').attr('x',10).attr('y',4).text(d=>(d.label||d.id).slice(0,28));
  node.append('title').text(d=>`${d.kind}: ${d.label}`);
  sim=d3.forceSimulation(nodes).force('link',d3.forceLink(links).id(d=>d.id).distance(70))
    .force('charge',d3.forceManyBody().strength(-180)).force('center',d3.forceCenter(
      document.getElementById('graph').clientWidth/2,document.getElementById('graph').clientHeight/2))
    .on('tick',()=>{link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
      .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
      node.attr('transform',d=>`translate(${d.x},${d.y})`);});}
function ds(e,d){if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;}
function dd(e,d){d.fx=e.x;d.fy=e.y;}
function de(e,d){if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("KG_PORT", "8097")))
