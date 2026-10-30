# routes/org.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os, json, datetime, re
from typing import List, Dict, Any
from neo4j import GraphDatabase
import numpy as np
from sentence_transformers import SentenceTransformer

from ..auth import get_current_user
from ..connections import make_neo4j_driver, resolve_neo4j_credentials

router = APIRouter()

NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD = resolve_neo4j_credentials()

# Initialize sentence transformer model for embeddings
try:
    sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    print(f"Warning: Could not load sentence transformer model: {e}")
    sentence_model = None

class VisualizeRequest(BaseModel):
    expanded_query_lucene: str
    min_fts_score: float = 1
    min_weight: int = 2
    sim_min: float = 0.5
    epsilon: float = 0.1
    limit: int = 1000
    run_louvain: bool = True
    graph_name: str = "orgOrg_hybrid"
    write_prop: str = "communityHybrid"

    # NEW: server-side viz filters
    min_weight_filter: int = 2       # edges: keep if r.weight >= this
    min_hybrid: float = 0           # edges: keep if r.hybrid >= this
    max_edges: int = 500              # cap edges (after filters) - reduced from 1000
    max_nodes: int = 100              # cap nodes (highest degree by hybrid first) - reduced from 200
    show_isolates: bool = False       # include nodes with no remaining edges

class VisualizeResponse(BaseModel):
    ok: bool
    url: str

class PartnerFinderRequest(BaseModel):
    query: str

class PartnerFinderResponse(BaseModel):
    ok: bool
    partners: List[Dict[str, Any]]
    original_query: str
    expanded_query: str

class PartnerFinderWithLuceneRequest(BaseModel):
    lucene_query: str

class PartnerFinderWithLuceneResponse(BaseModel):
    ok: bool
    partners: List[Dict[str, Any]]
    lucene_query: str

class CoParticipationWithLuceneRequest(BaseModel):
    lucene_query: str

class CoParticipationWithLuceneResponse(BaseModel):
    ok: bool
    url: str
    lucene_query: str

class HeatmapRequest(BaseModel):
    lucene_query: str
    metric: str = "projects" # "projects" or "ec_sum"
    min_score: float = 0.5
    limit_projects: int = 1000

class HeatmapResponse(BaseModel):
    ok: bool
    data: List[Dict[str, Any]]
    lucene_query: str
    metric: str


class DataSummaryResponse(BaseModel):
    ok: bool
    counts: Dict[str, int]

def sanitize_lucene_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="Query is empty")
    if len(query) > 1024:
        raise HTTPException(status_code=400, detail="Query too long (max 1024 characters)")
    return re.sub(r'[\x00-\x1f\x7f]', '', query).strip()

def check_neo4j_connection():
    try:
        driver = make_neo4j_driver(require_password=True)
        with driver.session() as session:
            session.run("RETURN 1 as ok").single()
            res = session.run("CALL gds.list() YIELD name RETURN count(*) AS c").single()
            if not res or res["c"] == 0:
                raise Exception("GDS procedures not available")
        driver.close()
        return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j connection failed: {str(e)}")

def fulltext_project_ids(session, lucene_query: str, min_fts_score: float, limit: int) -> List[int]:
    rows = session.run(
        """
        CALL db.index.fulltext.queryNodes('semanticNodeTextIndex', $q)
        YIELD node, score
        WHERE node:Project AND score >= $minScore
        RETURN id(node) AS pid
        ORDER BY score DESC
        LIMIT $limit
        """,
        q=lucene_query, minScore=float(min_fts_score), limit=int(limit)
    ).data()
    return [r["pid"] for r in rows]

def create_hybrid_edges(driver, lucene_query: str, min_fts_score: float, min_weight: int,
                        sim_min: float, epsilon: float, limit: int):
    with driver.session() as session:
        pids = fulltext_project_ids(session, lucene_query, min_fts_score, limit)
        if not pids:
            return 0, [], []
        # First, create/update relationships
        rec = session.run(
            """
            MATCH (o1:Organization)-[:PARTICIPATES_IN]->(p:Project)<-[:PARTICIPATES_IN]-(o2:Organization)
            WHERE id(p) IN $pids AND id(o1) < id(o2)
            WITH o1, o2, count(DISTINCT p) AS weight
            WHERE weight >= $minWeight
            WITH o1, o2, weight, o1.SemanticGNNEmbedding AS v1, o2.SemanticGNNEmbedding AS v2
            WITH o1, o2, weight,
                 CASE WHEN v1 IS NULL OR v2 IS NULL THEN 0.0
                      ELSE gds.similarity.cosine(v1, v2) END AS sim
            WHERE sim >= $simMin
            WITH o1, o2, weight, sim,
                 (toFloat(weight) * ($epsilon + sim)) AS hybrid
            MERGE (o1)-[r:CO_WORKED_HYBRID]->(o2)
            SET r.weight = weight,
                r.sim    = sim,
                r.hybrid = hybrid,
                r.query  = $lucene
            RETURN count(r) AS edges_created,
                   collect(DISTINCT o1.id) + collect(DISTINCT o2.id) AS org_ids
            """,
            pids=pids,
            minWeight=int(min_weight),
            simMin=float(sim_min),
            epsilon=float(epsilon),
            lucene=lucene_query,
        ).single()

        # Then, count existing relationships for this query (including newly created ones)
        
        count_rec = session.run(
            """
            MATCH ()-[r:CO_WORKED_HYBRID]->()
            WHERE r.query = $lucene
            RETURN count(r) AS total_edges
            """,
            lucene=lucene_query
        ).single()
        
        edges_created = int(count_rec["total_edges"]) if count_rec and "total_edges" in count_rec else 0
        org_ids = list(set(rec["org_ids"])) if rec and rec["org_ids"] else []
        return edges_created, pids, org_ids

def run_louvain_community_detection(driver, graph_name: str, write_prop: str):
    with driver.session() as session:
        try:
            session.run("CALL gds.graph.drop($name, false)", name=graph_name)
        except Exception:
            pass
        session.run(
            """
            CALL gds.graph.project(
              $name,
              'Organization',
              {CO_WORKED_HYBRID: {type:'CO_WORKED_HYBRID', orientation:'UNDIRECTED', properties:'hybrid'}}
            )
            """,
            name=graph_name,
        )
        
        # Run Louvain and write results back to the actual nodes
        res = session.run(
            f"""
            CALL gds.louvain.stream($name, {{
              relationshipWeightProperty: 'hybrid'
            }}) YIELD nodeId, communityId
            WITH nodeId, communityId
            MATCH (o:Organization) WHERE id(o) = nodeId
            SET o.{write_prop} = communityId
            RETURN count(o) as nodes_updated
            """,
            name=graph_name
        ).data()
        
        # Get statistics
        stats = session.run(
            """
            CALL gds.louvain.stats($name, {
              relationshipWeightProperty: 'hybrid'
            }) YIELD communityCount, modularity, ranLevels
            RETURN communityCount, modularity, ranLevels
            """,
            name=graph_name
        ).single()
        
        nodes_updated = res[0]['nodes_updated'] if res else 0
        print(f"Updated {nodes_updated} nodes with community values")
        
        # Debug: Check if values were actually written
        if nodes_updated > 0:
            debug_result = session.run(f"""
                MATCH (o:Organization) 
                WHERE o.{write_prop} IS NOT NULL AND o.{write_prop} != -1
                RETURN count(o) as valid_communities,
                       min(o.{write_prop}) as min_community,
                       max(o.{write_prop}) as max_community
            """)
            debug_stats = debug_result.single()
            print(f"DEBUG: Found {debug_stats['valid_communities']} nodes with valid community values")
            print(f"DEBUG: Community range: {debug_stats['min_community']} to {debug_stats['max_community']}")
        
        return stats

def fetch_graph_for_query(driver, lucene_query: str, write_prop: str, *,
                          min_weight_filter: int, min_hybrid: float,
                          max_edges: int, max_nodes: int, show_isolates: bool) -> Dict[str, Any]:
    with driver.session() as session:
        # 1) First try exact query match
        exact_edges = session.run(
            """
            MATCH (o1:Organization)-[r:CO_WORKED_HYBRID]->(o2:Organization)
            WHERE r.query = $q AND r.hybrid IS NOT NULL
              AND r.weight >= $minW AND r.hybrid >= $minH
            RETURN o1.id AS src_id, o2.id AS dst_id,
                   r.weight AS weight, r.sim AS sim, r.hybrid AS hybrid
            ORDER BY r.hybrid DESC, r.weight DESC
            LIMIT $maxE
            """,
            q=lucene_query,
            minW=int(min_weight_filter),
            minH=float(min_hybrid),
            maxE=int(max_edges),
        ).data()
        
        query_matched = bool(exact_edges)
        edges = exact_edges
        
        # 2) If no edges found, try to find edges that contain the query as a substring
        if not edges:
            print(f"No edges found for exact query '{lucene_query}', trying substring match...")
            edges = session.run(
                """
                MATCH (o1:Organization)-[r:CO_WORKED_HYBRID]->(o2:Organization)
                WHERE r.query CONTAINS $q AND r.hybrid IS NOT NULL
                  AND r.weight >= $minW AND r.hybrid >= $minH
                RETURN o1.id AS src_id, o2.id AS dst_id,
                       r.weight AS weight, r.sim AS sim, r.hybrid AS hybrid
                ORDER BY r.hybrid DESC, r.weight DESC
                LIMIT $maxE
                """,
                q=lucene_query,
                minW=int(min_weight_filter),
                minH=float(min_hybrid),
                maxE=int(max_edges),
            ).data()
            if edges:
                print(f"Found {len(edges)} edges with substring match")
        
        # 3) If still no edges, try to find any edges and show them
        if not edges:
            print(f"No edges found for query '{lucene_query}', showing any available edges...")
            edges = session.run(
                """
                MATCH (o1:Organization)-[r:CO_WORKED_HYBRID]->(o2:Organization)
                WHERE r.hybrid IS NOT NULL
                  AND r.weight >= $minW AND r.hybrid >= $minH
                RETURN o1.id AS src_id, o2.id AS dst_id,
                       r.weight AS weight, r.sim AS sim, r.hybrid AS hybrid
                ORDER BY r.hybrid DESC, r.weight DESC
                LIMIT $maxE
                """,
                minW=int(min_weight_filter),
                minH=float(min_hybrid),
                maxE=int(max_edges),
            ).data()
            if edges:
                print(f"Found {len(edges)} edges without query filter")

        node_ids = {e["src_id"] for e in edges} | {e["dst_id"] for e in edges}

        # 2) Nodes: only those in edges, unless show_isolates=True (izoleler eklensin)
        if node_ids:
            nodes = session.run(
                f"""
                MATCH (o:Organization)
                WHERE o.id IN $ids
                RETURN o.id AS id,
                       coalesce(o.name, o.id) AS name,
                       coalesce(o.acronym, '') AS acronym,
                       -1 AS community
                """,
                ids=list(node_ids)
            ).data()
            
            # Debug: Check community values in fetched nodes
            if nodes:
                minus_ones = [n for n in nodes if n['community'] == -1]
                valid_communities = [n for n in nodes if n['community'] != -1]
                print(f"DEBUG: Fetched {len(nodes)} nodes")
                print(f"DEBUG: Nodes with community = -1: {len(minus_ones)}")
                print(f"DEBUG: Nodes with valid community: {len(valid_communities)}")
                if valid_communities:
                    sample_communities = [n['community'] for n in valid_communities[:5]]
                    print(f"DEBUG: Sample community values: {sample_communities}")
        else:
            nodes = []

        # 3) (Optional) include isolates from topic projects
        if show_isolates:
            # Isolated nodes: organizations that participated in relevant projects
            # but have no edges remaining after filtering.
            extra_nodes = session.run(
                f"""
                CALL db.index.fulltext.queryNodes('semanticNodeTextIndex', $q) YIELD node, score
                WHERE node:Project
                WITH collect(id(node)) AS pids
                MATCH (o:Organization)-[:PARTICIPATES_IN]->(p:Project)
                WHERE id(p) IN pids AND NOT o.id IN $edgeIds
                RETURN DISTINCT o.id AS id,
                       coalesce(o.name, o.id) AS name,
                       coalesce(o.acronym, '') AS acronym,
                       -1 AS community
                LIMIT $cap
                """,
                q=lucene_query, edgeIds=list(node_ids), cap=max(0, max_nodes - len(nodes))
            ).data()
            nodes += [n for n in extra_nodes if n["id"] not in {x["id"] for x in nodes}]

        # 4) Node cap by degree (keep highest degree first)
        if nodes and edges and max_nodes > 0 and len(nodes) > max_nodes:
            deg = {}
            for e in edges:
                deg[e["src_id"]] = deg.get(e["src_id"], 0) + e["hybrid"]
                deg[e["dst_id"]] = deg.get(e["dst_id"], 0) + e["hybrid"]
            nodes_sorted = sorted(nodes, key=lambda n: deg.get(n["id"], 0.0), reverse=True)
            keep_ids = {n["id"] for n in nodes_sorted[:max_nodes]}
            nodes = [n for n in nodes if n["id"] in keep_ids]
            edges = [e for e in edges if e["src_id"] in keep_ids and e["dst_id"] in keep_ids]

        # 5) Label map for tooltips (simplified)
        if nodes:
            label_map = {r["id"]: (r["name"], r["acronym"]) for r in nodes}
            for e in edges:
                n1 = label_map.get(e["src_id"], ("", ""))
                n2 = label_map.get(e["dst_id"], ("", ""))
                e["src_label"] = n1[1] or n1[0] or str(e["src_id"])
                e["dst_label"] = n2[1] or n2[0] or str(e["dst_id"])

        return {"nodes": nodes, "edges": edges, "query_matched": query_matched}

def generate_html(filepath: str, lucene_query: str, graph: dict, write_prop: str, query_matched: bool = True):
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    template = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Co-participation (Hybrid) — __LUCENE__</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  html,body { 
    margin:0; padding:0; 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
    min-height: 100vh;
  }
  #wrap { 
    padding:24px; 
    max-width: 1400px; 
    margin: 0 auto;
  }
  #meta { 
    margin-bottom:20px; 
    background: rgba(255,255,255,0.95); 
    padding: 20px; 
    border-radius: 12px; 
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  }
  #meta h2 { 
    margin:0 0 12px 0; 
    color: #2d3748; 
    font-size: 28px; 
    font-weight: 600;
  }
  #meta code { 
    background: #edf2f7; 
    padding: 4px 8px; 
    border-radius: 4px; 
    font-family: 'Monaco', 'Menlo', monospace;
  }
  #controls {
    display:flex; flex-wrap:wrap; gap:16px; align-items:center;
    background: rgba(255,255,255,0.95); 
    border: 1px solid #e2e8f0; 
    border-radius: 12px; 
    padding: 20px; 
    margin-bottom: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  }
  #graph { 
    background: white; 
    border-radius: 12px; 
    overflow: hidden; 
    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
  }
  .link { stroke:#3182ce; stroke-opacity:0.5; }  /* stroke-width set dynamically */
  .node { stroke:#fff; stroke-width:2px; }
  label { font-size:14px; color:#2d3748; font-weight: 500; }
  input[type="range"] { 
    width: 200px; 
    height: 6px;
    border-radius: 3px;
    background: #e2e8f0;
    outline: none;
  }
  input[type="range"]::-webkit-slider-thumb {
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #3182ce;
    cursor: pointer;
  }
  button {
    background: #3182ce;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
  }
  button:hover {
    background: #2c5aa0;
  }
  .tooltip {
    position:absolute; pointer-events:none;
    background: rgba(0,0,0,0.9); 
    color:#fff; 
    padding: 8px 12px; 
    border-radius: 6px; 
    font-size: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    backdrop-filter: blur(4px);
  }
  #notice { 
    margin: 12px 0; 
    color: #d69e2e; 
    background: #fef5e7; 
    padding: 8px 12px; 
    border-radius: 6px; 
    border-left: 4px solid #f6ad55;
  }
  .legend {
    font-size: 13px; 
    color: #718096; 
    margin: 8px 0;
    padding: 8px 12px;
    background: #f7fafc;
    border-radius: 6px;
    border-left: 3px solid #3182ce;
  }
</style>
</head>
<body>
<div id="wrap">
      <div id="meta">
    <h2>MAPIT AI Co-participation Network Visualization</h2>
    <div><b>Query:</b> <code>__LUCENE__</code></div>
    <div id="stats"><b>Organizations:</b> __ORG_COUNT__ &nbsp; <b>Edges:</b> __EDGE_COUNT__</div>
    <div id="notice">__QUERY_NOTICE__</div>
  </div>

  <div id="controls">
    <label>min weight:
      <input id="wMin" type="range" min="1" max="10" step="1" value="3">
      <span id="wMinVal">3</span>
    </label>
    <label>min hybrid:
      <input id="hMin" type="range" min="0" max="5" step="0.05" value="2">
      <span id="hMinVal">2.00</span>
    </label>
    <label>max nodes:
      <input id="nMax" type="range" min="20" max="200" step="10" value="20">
      <span id="nMaxVal">100</span>
    </label>
    <label><input id="showIsolates" type="checkbox"> show isolates</label>
    <button id="applyBtn">Apply</button>
    <button id="fitBtn">Zoom to Fit</button>
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="font-size: 12px; color: #666;">Spacing:</span>
      <button id="spacingMinus" style="width: 30px; height: 30px; padding: 0; font-size: 16px; font-weight: bold;">−</button>
      <button id="spacingPlus" style="width: 30px; height: 30px; padding: 0; font-size: 16px; font-weight: bold;">+</button>
    </div>
  </div>

  <div id="graph"></div>
  <div id="zoomInfo" style="margin-top: 10px; font-size: 12px; color: #666;">Zoom: 1x | Pan: Drag empty space</div>
</div>
<script>
const ORIG_NODES = __NODES_JSON__;
const ORIG_EDGES = __EDGES_JSON__;

console.log("Loaded nodes/edges:", ORIG_NODES.length, ORIG_EDGES.length);
if (!Array.isArray(ORIG_EDGES)) { console.warn("ORIG_EDGES is not array", ORIG_EDGES); }
if (!Array.isArray(ORIG_NODES)) { console.warn("ORIG_NODES is not array", ORIG_NODES); }

let width = Math.max(960, window.innerWidth - 48);
let height = Math.max(600, window.innerHeight - 200);

const svg = d3.select("#graph").append("svg")
  .attr("width", width).attr("height", height)
  .style("background","#fff");
const g = svg.append("g");

// Add zoom functionality
const zoom = d3.zoom()
  .scaleExtent([0.1, 10]) // Min and max zoom scale
  .on("zoom", (event) => {
    g.attr("transform", event.transform);
    // Update zoom info
    const zoomInfo = document.getElementById("zoomInfo");
    if (zoomInfo) {
      zoomInfo.textContent = `Zoom: ${event.transform.k.toFixed(2)}x | Pan: Drag empty space`;
    }
  });

svg.call(zoom);

const color = d3.scaleOrdinal(d3.schemeCategory10);

let nodeSel = null, linkSel = null, labelSel = null, sim = null;
let currentLinkDistance = 120; // Default link distance
let currentChargeStrength = -300; // Default charge strength

function computeDegree(edges) {
  const deg = new Map();
  for (const e of edges) {
    const h = +e.hybrid || 0;
    deg.set(e.src_id, (deg.get(e.src_id)||0) + h);
    deg.set(e.dst_id, (deg.get(e.dst_id)||0) + h);
  }
  return deg;
}

/* Return all edges without filtering (for the initial render) */
function buildGraphNoFilter() {
  // Use all edges without filtering
  let E = ORIG_EDGES.map(e => ({
    src_id: String(e.src_id), dst_id: String(e.dst_id), // Ensure string IDs
    weight: +e.weight || 0, sim: +e.sim || 0, hybrid: +e.hybrid || 0,
    src_label: e.src_label || "", dst_label: e.dst_label || ""
  }));
  
  // Build the node set from all edges
  let ids = new Set();
  for (const e of E) { ids.add(e.src_id); ids.add(e.dst_id); }
  let N = ORIG_NODES.filter(n => ids.has(String(n.id))); // Ensure string comparison
  
  // Debug: log the counts
  console.log("buildGraphNoFilter: ORIG_EDGES=", ORIG_EDGES.length, "ORIG_NODES=", ORIG_NODES.length);
  console.log("buildGraphNoFilter: filtered N=", N.length, "E=", E.length);
  
  return { nodes: N, edges: E };
}

/* Filtered version used by the Apply action */
function buildFilteredGraph(wMin, hMin, nMax, showIsolates) {
  let E = ORIG_EDGES.filter(e => ((+e.weight||0) >= wMin) && ((+e.hybrid||0) >= hMin))
                    .map(e => ({
                      src_id: String(e.src_id), dst_id: String(e.dst_id), // Ensure string IDs
                      weight: +e.weight || 0, sim: +e.sim || 0, hybrid: +e.hybrid || 0,
                      src_label: e.src_label || "", dst_label: e.dst_label || ""
                    }));

  let ids = new Set();
  for (const e of E) { ids.add(e.src_id); ids.add(e.dst_id); }
  let N = ORIG_NODES.filter(n => ids.has(String(n.id))); // Ensure string comparison

  if (showIsolates) {
    const existing = new Set(N.map(n=>n.id));
    for (const n of ORIG_NODES) if (!existing.has(n.id)) N.push(n);
  }

  if (N.length > nMax) {
    const deg = computeDegree(E);
    N.sort((a,b) => (deg.get(b.id)||0) - (deg.get(a.id)||0));
    const keep = new Set(N.slice(0,nMax).map(n=>n.id));
    N = N.filter(n => keep.has(n.id));
    E = E.filter(e => keep.has(e.src_id) && keep.has(e.dst_id));
  }

  // Show a message if the filters removed everything
  if (E.length === 0 && ORIG_EDGES.length > 0) {
    document.getElementById("notice").textContent =
      "No edges after filters; relax thresholds (min weight/hybrid) to see connections.";
  } else {
    document.getElementById("notice").textContent = "";
  }

  return {nodes: N, edges: E};
}

function drawGraph(N, E) {
  // Store current zoom transform
  const currentTransform = d3.zoomTransform(svg.node());
  
  // Clear existing content
  g.selectAll("*").remove();
  
  // Reapply zoom to maintain zoom state
  svg.call(zoom.transform, currentTransform);
  
  // Debug: check if zoom is working
  console.log("Current zoom transform:", currentTransform);

  const links = E.map(e => ({
    source: String(e.src_id), target: String(e.dst_id), // Use string IDs, let D3 bind objects
    weight: e.weight, sim: e.sim, hybrid: e.hybrid,
    label: (e.src_label||e.src_id) + " ↔ " + (e.dst_label||e.dst_id)
  }));
  const nodes = N.map(n => ({
    id:n.id, label:n.acronym || n.name || n.id, community:+n.community,
    x: Math.random() * width, y: Math.random() * height  // Add initial positions
  }));

  // Debug: log the link creation
  console.log("drawGraph: N=", N.length, "E=", E.length, "links=", links.length);

  // If there are no links, show a notice and still render the nodes
  if (links.length === 0) {
    if (ORIG_EDGES.length > 0) {
      document.getElementById("notice").textContent =
        "Edges exist in dataset but none passed the filter; try lowering thresholds.";
    } else {
      document.getElementById("notice").textContent =
        "No edges available for this query from server.";
    }
  } else {
    document.getElementById("notice").textContent = "";
  }

  linkSel = g.append("g").selectAll("line").data(links).enter()
    .append("line").attr("class","link")
    .attr("stroke-width", d => {
      // Scale stroke width based on weight with scale factor for more apparent differences
      const weight = d.weight || 1;
      const scaleFactor = 0.5; // Multiply weight by this factor to make thickness more apparent
      const scaledWeight = weight * scaleFactor;
      const minWidth = 0.1;
      const maxWidth = 5;
      // Linear scaling with scale factor
      const scale = Math.min(scaledWeight / 5, 1); // Normalize to 0-1 based on max scaled weight of 15
      return minWidth + (maxWidth - minWidth) * scale;
    });
  
  nodeSel = g.append("g").selectAll("circle").data(nodes).enter()
    .append("circle").attr("class","node").attr("r",8)
    .attr("fill", d => color((d.community%10+10)%10))
    .attr("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.2))")
    .call(d3.drag()
      .on("start",function(event,d){ 
        if(!event.active) sim.alphaTarget(0.3).restart(); 
        d.fx=d.x; d.fy=d.y; 
      })
      .on("drag", function(event,d){ 
        d.fx=event.x; d.fy=event.y; 
      })
      .on("end",  function(event,d){ 
        if(!event.active) sim.alphaTarget(0); 
        d.fx=null; d.fy=null; 
      })
    );

  labelSel = g.append("g").selectAll("text").data(nodes).enter()
    .append("text").text(d => d.label)
    .attr("font-size", 12).attr("dx", 12).attr("dy", -10).attr("fill","#2d3748")
    .attr("font-weight", "500")
    .attr("text-shadow", "0 1px 2px rgba(255,255,255,0.8)");

  const tooltip = d3.select("body").append("div").attr("class","tooltip").style("opacity",0);
  nodeSel.on("mouseover",function(event,d){
    tooltip.style("opacity",1).html("🏢 <b>"+d.label+"</b><br/>👥 Community: "+d.community)
      .style("left",(event.pageX+8)+"px").style("top",(event.pageY-28)+"px");
  }).on("mouseout",function(){ tooltip.style("opacity",0); });
  linkSel.on("mouseover",function(event,d){
    const strokeWidth = d3.select(this).attr("stroke-width");
    const scaleFactor = 10;
    const scaledWeight = (d.weight || 1) * scaleFactor;
    tooltip.style("opacity",1)
      .html("<b>"+d.label+"</b><br/>🔗 <b>Weight:</b> "+d.weight+" (scaled: "+scaledWeight+")<br/>📏 Thickness: "+strokeWidth+"px<br/>📊 Similarity: "+d.sim.toFixed(3)+"<br/>⚡ Hybrid Score: "+d.hybrid.toFixed(3))
      .style("left",(event.pageX+8)+"px").style("top",(event.pageY-28)+"px");
  }).on("mouseout",function(){ tooltip.style("opacity",0); });

  sim = d3.forceSimulation(nodes).alphaDecay(0.08)
    .force("charge", d3.forceManyBody().strength(currentChargeStrength))
    .force("center", d3.forceCenter(width/2, height/2));

  if (links.length) {
    // Add an ID accessor for more stable matching across D3 versions
    // Configure the link force using node IDs
    sim.force("link", d3.forceLink(links).id(d => d.id).distance(currentLinkDistance).strength(0.1));
  }

  sim.on("tick", function() {
    if (linkSel && linkSel.size() > 0) {
      linkSel.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
             .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    }
    if (nodeSel && nodeSel.size() > 0) {
      nodeSel.attr("cx",d=>d.x).attr("cy",d=>d.y);
    }
    if (labelSel && labelSel.size() > 0) {
      labelSel.attr("x",d=>d.x).attr("y",d=>d.y);
    }
  });
  
  // Force the simulation to start
  sim.alpha(1).restart();

  var stats = document.getElementById("stats");
  if (stats) {
    stats.innerHTML = "<b>Organizations:</b> " + N.length + " &nbsp; <b>Edges:</b> " + E.length;
  }
}

function zoomToFit() {
  const bbox = g.node().getBBox();
  const margin = 20;
  const scale = Math.min(
    (width - margin) / (bbox.width || 1),
    (height - margin) / (bbox.height || 1)
  );
  const x = -bbox.x * scale + (width - bbox.width * scale) / 2;
  const y = -bbox.y * scale + (height - bbox.height * scale) / 2;
  svg.transition().duration(500).call(
    zoom.transform,
    d3.zoomIdentity.translate(x, y).scale(scale)
  );
}

function resetZoom() {
  svg.transition().duration(500).call(
    zoom.transform,
    d3.zoomIdentity
  );
}

function adjustSpacing(delta) {
  // Adjust link distance
  currentLinkDistance = Math.max(50, Math.min(300, currentLinkDistance + delta * 20));
  
  // Adjust charge strength (more negative = more repulsion)
  currentChargeStrength = Math.max(-600, Math.min(-100, currentChargeStrength + delta * 50));
  
  // Update the simulation if it exists
  if (sim) {
    sim.force("link").distance(currentLinkDistance);
    sim.force("charge").strength(currentChargeStrength);
    sim.alpha(0.3).restart(); // Restart with some energy
  }
  
  console.log(`Spacing adjusted: linkDistance=${currentLinkDistance}, chargeStrength=${currentChargeStrength}`);
}



function getControls() {
  const wMin = +document.getElementById("wMin").value;
  const hMin = +document.getElementById("hMin").value;
  const nMax = +document.getElementById("nMax").value;
  const showIsolates = document.getElementById("showIsolates").checked;
  return { wMin, hMin, nMax, showIsolates };
}

function updateLabels() {
  document.getElementById("wMinVal").textContent = document.getElementById("wMin").value;
  document.getElementById("hMinVal").textContent = (+document.getElementById("hMin").value).toFixed(2);
  document.getElementById("nMaxVal").textContent = document.getElementById("nMax").value;
}

document.getElementById("wMin").addEventListener("input", updateLabels);
document.getElementById("hMin").addEventListener("input", updateLabels);
document.getElementById("nMax").addEventListener("input", updateLabels);
updateLabels();

document.getElementById("applyBtn").addEventListener("click", function() {
  const c = getControls();
  const G = buildFilteredGraph(c.wMin, c.hMin, c.nMax, c.showIsolates);
  drawGraph(G.nodes, G.edges);
});

document.getElementById("fitBtn").addEventListener("click", zoomToFit);
document.getElementById("spacingMinus").addEventListener("click", () => adjustSpacing(-10));
document.getElementById("spacingPlus").addEventListener("click", () => adjustSpacing(10));

// *** Initial render: start with UNFILTERED data ***
const initial = buildGraphNoFilter();
drawGraph(initial.nodes, initial.edges);

// resize
window.addEventListener("resize", function() {
  width = Math.max(960, window.innerWidth - 48);
  height = Math.max(600, window.innerHeight - 200);
  svg.attr("width", width).attr("height", height);
});
</script>
</body>
</html>"""

    # Determine notice message
    if not query_matched and edges:
        notice = "Note: Showing edges from related queries (exact match not found)"
    else:
        notice = ""
    

    
    html = (template
            .replace("__LUCENE__", escape(lucene_query))
            .replace("__ORG_COUNT__", str(len(nodes)))
            .replace("__EDGE_COUNT__", str(len(edges)))
            .replace("__QUERY_NOTICE__", notice)
            .replace("__NODES_JSON__", json.dumps(nodes, ensure_ascii=False))
            .replace("__EDGES_JSON__", json.dumps(edges, ensure_ascii=False)))

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
        
@router.post("/visualize", response_model=VisualizeResponse)
async def visualize_co_participation(request: VisualizeRequest, user_id: str = Depends(get_current_user)):
    """
    Create a co-participation network visualization with optimized initial graph size.
    The graph is now limited to max_nodes (default 100) and max_edges (default 500) 
    during initial creation for faster processing.
    """
    try:
        lucene_query = sanitize_lucene_query(request.expanded_query_lucene)
        check_neo4j_connection()

        unique_graph = f"{request.graph_name}_{int(datetime.datetime.utcnow().timestamp())}"
        driver = make_neo4j_driver(require_password=True)
        try:
            # Create projection graph on the fly with initial size limits
            total_edges, pids, org_ids = create_hybrid_edges_on_projection(
                driver,
                lucene_query=lucene_query,
                min_fts_score=request.min_fts_score,
                min_weight=request.min_weight,
                sim_min=request.sim_min,
                epsilon=request.epsilon,
                limit=request.limit,
                graph_name=unique_graph,
                max_initial_edges=request.max_edges,  # Use the max_edges from request
                max_initial_nodes=request.max_nodes   # Use the max_nodes from request
            )
            
            if request.run_louvain and total_edges > 0:
                res = run_louvain_community_detection_on_projection(driver, unique_graph, request.write_prop)
                if res:
                    print(f"Louvain → communities={res.get('communityCount')} modularity={res.get('modularity')}")
            elif request.run_louvain:
                print("Skipping Louvain: no edges created for this query/thresholds.")

            graph = fetch_graph_from_projection(
                    driver,
                    unique_graph,
                    lucene_query,
                    request.write_prop,
                    pids,
                    min_weight_filter=request.min_weight_filter,
                    min_hybrid=request.min_hybrid,
                    max_edges=request.max_edges,
                    max_nodes=request.max_nodes,
                    show_isolates=request.show_isolates
                )
            
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_name = f"ai_org_org_hybrid_{ts}.html"
            out_path = os.path.join("static", "visuals", out_name)
            generate_html(out_path, lucene_query, graph, request.write_prop, graph.get("query_matched", True))
            return VisualizeResponse(ok=True, url=f"/visuals/{out_name}")
        finally:
            # Clean up: delete the projection graph
            try:
                with driver.session() as session:
                    session.run("CALL gds.graph.drop($name, false)", name=unique_graph)
                    print(f"Cleaned up projection graph: {unique_graph}")
            except Exception as e:
                print(f"Warning: Failed to clean up projection graph {unique_graph}: {e}")
            driver.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[visualize] error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create visualization: {str(e)}")

import os, json
from html import escape

def find_partners(driver, query: str) -> List[Dict[str, Any]]:
    """
    Find similar organizations using embedding similarity and fulltext search.
    Returns top 5 partners from each similarity search (SentenceTransformer, SemanticGNN, and Fulltext).
    """
    if not sentence_model:
        raise HTTPException(status_code=500, detail="Sentence transformer model not available")
    
    # Compute embedding for the query
    query_embedding = sentence_model.encode(query).tolist()
    
    with driver.session() as session:
        # Find organizations with similar SentenceTransformer embeddings
        sentence_partners = session.run(
            """
            MATCH (o:Organization)
            WHERE o.SentenceTransformerEmbedding IS NOT NULL
            WITH o, gds.similarity.cosine(o.SentenceTransformerEmbedding, $embedding) AS similarity
            WHERE similarity > 0.2
            RETURN o.id AS id,
                   o.name AS name,
                   o.shortName AS shortName,
                   o.country AS country,
                   o.type AS type,
                   similarity AS score,
                   'SentenceTransformer' AS method
            ORDER BY similarity DESC
            LIMIT 5
            """,
            embedding=query_embedding
        ).data()
        
        # Find organizations with similar SemanticGNN embeddings
        semantic_partners = session.run(
            """
            MATCH (o:Organization)
            WHERE o.SemanticGNNEmbedding IS NOT NULL
            WITH o, gds.similarity.cosine(o.SemanticGNNEmbedding, $embedding) AS similarity
            WHERE similarity > 0.2
            RETURN o.id AS id,
                   o.name AS name,
                   o.shortName AS shortName,
                   o.country AS country,
                   o.type AS type,
                   similarity AS score,
                   'SemanticGNN' AS method
            ORDER BY similarity DESC
            LIMIT 5
            """,
            embedding=query_embedding
        ).data()
        
        # Find organizations using Lucene fulltext search
        fulltext_partners = session.run(
            """
CALL {
  CALL db.index.fulltext.queryNodes('semanticNodeTextIndex', $lucene)
  YIELD node, score
  WHERE node:Project AND score >= 0.5
  RETURN node AS p, score
  ORDER BY score DESC
  LIMIT 200
}
WITH collect({p:p, s:score}) AS rows
WITH rows,
     reduce(m = 0.0, r IN rows | CASE WHEN r.s > m THEN r.s ELSE m END) AS maxScore
UNWIND rows AS r
WITH r.p AS p, r.s AS rawScore,
     (CASE WHEN maxScore = 0.0 THEN 0.0 ELSE r.s / maxScore END) AS pScoreNorm

MATCH (o:Organization)-[:PARTICIPATES_IN]->(p)
WITH o,
     collect(pScoreNorm) AS projectScores,
     count(DISTINCT p) AS matchedProjects
WITH o,
     apoc.coll.sum(projectScores) AS score_sum,       
     (CASE WHEN matchedProjects=0 THEN 0.0
           ELSE apoc.coll.sum(projectScores) / matchedProjects END) AS score_avg,
     matchedProjects
RETURN
  o.id        AS id,
  o.name      AS name,
  o.shortName AS shortName,
  o.country   AS country,
  o.type      AS type,
  score_sum   AS score_total,     
  score_avg/2   AS score,       
  matchedProjects,
  'ProjectFTS' AS method
ORDER BY score_total DESC
LIMIT 10;            """,
            lucene=query
        ).data()
        
        # Merge and deduplicate results
        all_partners = sentence_partners + semantic_partners + fulltext_partners
        
        # Remove duplicates based on organization ID, keeping the highest score
        partner_dict = {}
        for partner in all_partners:
            org_id = partner['id']
            if org_id not in partner_dict or partner['score'] > partner_dict[org_id]['score']:
                partner_dict[org_id] = partner
        
        # Convert back to list and sort by score
        unique_partners = list(partner_dict.values())
        unique_partners.sort(key=lambda x: x['score'], reverse=True)
        
        return unique_partners

@router.post("/find-partners", response_model=PartnerFinderResponse)
async def find_partners_endpoint(request: PartnerFinderRequest, user_id: str = Depends(get_current_user)):
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if len(request.query) > 500:
            raise HTTPException(status_code=400, detail="Query too long (max 500 characters)")
        
        check_neo4j_connection()
        
        # Step 1: Expand the query using the expand endpoint
        try:
            from .ai import expand_query, ExpandRequest
            expand_request = ExpandRequest(text=request.query.strip())
            expand_response = await expand_query(expand_request, user_id)
            expanded_query = expand_response.expanded_query
            print(f"Original query: '{request.query}' -> Expanded query: '{expanded_query}'")
        except Exception as e:
            print(f"Query expansion failed, using original query: {e}")
            expanded_query = request.query.strip()
        
        driver = make_neo4j_driver(require_password=True)
        try:
            partners = find_partners(driver, expanded_query)
            return PartnerFinderResponse(ok=True, partners=partners, original_query=request.query, expanded_query=expanded_query)
        finally:
            driver.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[find-partners] error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find partners: {str(e)}")

@router.post("/find-partners-with-lucene", response_model=PartnerFinderWithLuceneResponse)
async def find_partners_with_lucene_endpoint(request: PartnerFinderWithLuceneRequest, user_id: str = Depends(get_current_user)):
    """
    Find partners using a pre-generated lucene query.
    This endpoint skips the query expansion step and uses the provided lucene_query directly.
    """
    try:
        if not request.lucene_query.strip():
            raise HTTPException(status_code=400, detail="Lucene query cannot be empty")
        
        if len(request.lucene_query) > 1000:
            raise HTTPException(status_code=400, detail="Lucene query too long (max 1000 characters)")
        
        check_neo4j_connection()
        
        # Sanitize the lucene query
        sanitized_lucene_query = sanitize_lucene_query(request.lucene_query.strip())
        
        driver = make_neo4j_driver(require_password=True)
        try:
            # Use the existing find_partners function but pass the lucene query directly
            # We need to modify the approach since find_partners expects a text query for embedding
            # For this endpoint, we'll focus on the fulltext search part
            
            # Compute embedding for the lucene query (use it as text for embedding search)
            if not sentence_model:
                raise HTTPException(status_code=500, detail="Sentence transformer model not available")
            
            query_embedding = sentence_model.encode(sanitized_lucene_query).tolist()
            
            with driver.session() as session:
                # Find organizations with similar SentenceTransformer embeddings
                sentence_partners = session.run(
                    """
                    MATCH (o:Organization)
                    WHERE o.SentenceTransformerEmbedding IS NOT NULL
                    WITH o, gds.similarity.cosine(o.SentenceTransformerEmbedding, $embedding) AS similarity
                    WHERE similarity > 0.2
                    RETURN o.id AS id,
                           o.name AS name,
                           o.shortName AS shortName,
                           o.country AS country,
                           o.type AS type,
                           similarity AS score,
                           'SentenceTransformer' AS method
                    ORDER BY similarity DESC
                    LIMIT 5
                    """,
                    embedding=query_embedding
                ).data()
                
                # Find organizations with similar SemanticGNN embeddings
                semantic_partners = session.run(
                    """
                    MATCH (o:Organization)
                    WHERE o.SemanticGNNEmbedding IS NOT NULL
                    WITH o, gds.similarity.cosine(o.SemanticGNNEmbedding, $embedding) AS similarity
                    WHERE similarity > 0.2
                    RETURN o.id AS id,
                           o.name AS name,
                           o.shortName AS shortName,
                           o.country AS country,
                           o.type AS type,
                           similarity AS score,
                           'SemanticGNN' AS method
                    ORDER BY similarity DESC
                    LIMIT 5
                    """,
                    embedding=query_embedding
                ).data()
                
                # Find organizations using Lucene fulltext search with the provided lucene query
                fulltext_partners = session.run(
                    """
CALL {
  CALL db.index.fulltext.queryNodes('semanticNodeTextIndex', $lucene)
  YIELD node, score
  WHERE node:Project AND score >= 0.5
  RETURN node AS p, score
  ORDER BY score DESC
  LIMIT 200
}
WITH collect({p:p, s:score}) AS rows
WITH rows,
     reduce(m = 0.0, r IN rows | CASE WHEN r.s > m THEN r.s ELSE m END) AS maxScore
UNWIND rows AS r
WITH r.p AS p, r.s AS rawScore,
     (CASE WHEN maxScore = 0.0 THEN 0.0 ELSE r.s / maxScore END) AS pScoreNorm

MATCH (o:Organization)-[:PARTICIPATES_IN]->(p)
WITH o,
     collect(pScoreNorm) AS projectScores,
     count(DISTINCT p) AS matchedProjects
WITH o,
     apoc.coll.sum(projectScores) AS score_sum,       
     (CASE WHEN matchedProjects=0 THEN 0.0
           ELSE apoc.coll.sum(projectScores) / matchedProjects END) AS score_avg,
     matchedProjects
RETURN
  o.id        AS id,
  o.name      AS name,
  o.shortName AS shortName,
  o.country   AS country,
  o.type      AS type,
  score_sum   AS score_total,     
  score_avg/2   AS score,       
  matchedProjects,
  'ProjectFTS' AS method
ORDER BY score_total DESC
LIMIT 10;            """,
                    lucene=sanitized_lucene_query
                ).data()
                
                # Merge and deduplicate results
                all_partners = sentence_partners + semantic_partners + fulltext_partners
                
                # Remove duplicates based on organization ID, keeping the highest score
                partner_dict = {}
                for partner in all_partners:
                    org_id = partner['id']
                    if org_id not in partner_dict or partner['score'] > partner_dict[org_id]['score']:
                        partner_dict[org_id] = partner
                
                # Convert back to list and sort by score
                unique_partners = list(partner_dict.values())
                unique_partners.sort(key=lambda x: x['score'], reverse=True)
                
                return PartnerFinderWithLuceneResponse(
                    ok=True, 
                    partners=unique_partners, 
                    lucene_query=sanitized_lucene_query
                )
        finally:
            driver.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[find-partners-with-lucene] error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find partners: {str(e)}")

@router.post("/co-participation-with-lucene", response_model=CoParticipationWithLuceneResponse)
async def co_participation_with_lucene_endpoint(request: CoParticipationWithLuceneRequest, user_id: str = Depends(get_current_user)):
    """
    Create co-participation visualization using a direct lucene query (no expansion needed).
    This endpoint skips the query expansion step and uses the provided lucene_query directly.
    """
    try:
        if not request.lucene_query.strip():
            raise HTTPException(status_code=400, detail="Lucene query cannot be empty")
        
        if len(request.lucene_query) > 1000:
            raise HTTPException(status_code=400, detail="Lucene query too long (max 1000 characters)")
        
        check_neo4j_connection()
        
        # Sanitize the lucene query
        sanitized_lucene_query = sanitize_lucene_query(request.lucene_query.strip())
        
        driver = make_neo4j_driver(require_password=True)
        try:
            # Create projection graph on the fly with initial size limits
            unique_graph = f"orgOrg_hybrid_{int(datetime.datetime.utcnow().timestamp())}"
            
            total_edges, pids, org_ids = create_hybrid_edges_on_projection(
                driver,
                lucene_query=sanitized_lucene_query,
                min_fts_score=1.0,
                min_weight=2,
                sim_min=0.5,
                epsilon=0.1,
                limit=2000,
                graph_name=unique_graph,
                max_initial_edges=500,
                max_initial_nodes=100
            )
            
            # Run Louvain community detection
            if total_edges > 0:
                res = run_louvain_community_detection_on_projection(driver, unique_graph, "communityHybrid")
                if res:
                    print(f"Louvain → communities={res.get('communityCount')} modularity={res.get('modularity')}")
            else:
                print("Skipping Louvain: no edges created for this query/thresholds.")

            # Fetch the graph data
            graph = fetch_graph_from_projection(
                driver,
                unique_graph,
                sanitized_lucene_query,
                "communityHybrid",
                pids,
                min_weight_filter=2,
                min_hybrid=0,
                max_edges=500,
                max_nodes=100,
                show_isolates=False
            )
            
            # Generate HTML visualization
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_name = f"ai_org_org_hybrid_{ts}.html"
            out_path = os.path.join("static", "visuals", out_name)
            generate_html(out_path, sanitized_lucene_query, graph, "communityHybrid", graph.get("query_matched", True))
            
            return CoParticipationWithLuceneResponse(
                ok=True,
                url=f"/visuals/{out_name}",
                lucene_query=sanitized_lucene_query
            )
        finally:
            # Clean up: delete the projection graph
            try:
                with driver.session() as session:
                    session.run("CALL gds.graph.drop($name, false)", name=unique_graph)
                    print(f"Cleaned up projection graph: {unique_graph}")
            except Exception as e:
                print(f"Warning: Failed to clean up projection graph {unique_graph}: {e}")
            driver.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[co-participation-with-lucene] error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create co-participation visualization: {str(e)}")

@router.post("/heatmap", response_model=HeatmapResponse)
async def heatmap_endpoint(request: HeatmapRequest, user_id: str = Depends(get_current_user)):
    """
    Generate heatmap data for geographic visualization using a lucene query.
    Returns country-level aggregation data for projects and funding.
    """
    try:
        if not request.lucene_query.strip():
            raise HTTPException(status_code=400, detail="Lucene query cannot be empty")
        
        if len(request.lucene_query) > 1000:
            raise HTTPException(status_code=400, detail="Lucene query too long (max 1000 characters)")
        
        if request.metric not in ["projects", "ec_sum"]:
            raise HTTPException(status_code=400, detail="Metric must be 'projects' or 'ec_sum'")
        
        check_neo4j_connection()
        
        # Sanitize the lucene query
        sanitized_lucene_query = sanitize_lucene_query(request.lucene_query.strip())
        
        # Fetch heatmap data
        heatmap_data = fetch_heatmap_data(
            sanitized_lucene_query,
            request.min_score,
            request.limit_projects
        )
        
        return HeatmapResponse(
            ok=True,
            data=heatmap_data,
            lucene_query=sanitized_lucene_query,
            metric=request.metric
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[heatmap] error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate heatmap data: {str(e)}")


@router.get("/data-summary", response_model=DataSummaryResponse)
async def data_summary(user_id: str = Depends(get_current_user)):
    """
    Return key Neo4j node counts for UI tooltips/badges.
    """
    check_neo4j_connection()
    driver = make_neo4j_driver(require_password=True)
    try:
        with driver.session() as session:
            rec = session.run(
                """
                CALL {
                  MATCH (n:Project)
                  RETURN count(n) AS projects
                }
                CALL {
                  MATCH (n:Deliverable)
                  RETURN count(n) AS deliverables
                }
                CALL {
                  MATCH (n:Organization)
                  RETURN count(n) AS partners
                }
                CALL {
                  MATCH (n:Publication)
                  RETURN count(n) AS publications
                }
                CALL {
                  MATCH (n:PubAuthor)
                  RETURN count(n) AS authors
                }
                RETURN projects, deliverables, partners, publications, authors
                """
            ).single()

            counts = {
                "projects": int(rec["projects"] if rec and rec["projects"] is not None else 0),
                "deliverables": int(rec["deliverables"] if rec and rec["deliverables"] is not None else 0),
                "partners": int(rec["partners"] if rec and rec["partners"] is not None else 0),
                "publications": int(rec["publications"] if rec and rec["publications"] is not None else 0),
                "authors": int(rec["authors"] if rec and rec["authors"] is not None else 0),
            }
            return DataSummaryResponse(ok=True, counts=counts)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[data-summary] error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch data summary: {str(e)}")
    finally:
        driver.close()

def create_hybrid_edges_on_projection(driver, lucene_query: str, min_fts_score: float, min_weight: int,
                                     sim_min: float, epsilon: float, limit: int, graph_name: str,
                                     max_initial_edges: int = 500, max_initial_nodes: int = 100):
    """
    Create hybrid edges on a projection graph instead of the main database.
    This function creates a temporary projection, adds edges to it, and returns the results.
    Now with initial size limits to make the graph smaller and faster.
    """
    with driver.session() as session:
        # Get project IDs that match the query
        pids = fulltext_project_ids(session, lucene_query, min_fts_score, limit)
        if not pids:
            return 0, [], []
        
        # Create a projection graph with organizations and their relationships
        try:
            # Drop existing projection if it exists
            session.run("CALL gds.graph.drop($name, false)", name=graph_name)
        except Exception:
            pass
        
        # First, find the top organizations by participation count to limit initial nodes
        top_orgs = session.run(
            """
            MATCH (o:Organization)-[:PARTICIPATES_IN]->(p:Project)
            WHERE id(p) IN $pids
            WITH o, count(DISTINCT p) AS participation_count
            ORDER BY participation_count DESC
            LIMIT $maxNodes
            RETURN collect(id(o)) AS top_org_ids
            """,
            pids=pids,
            maxNodes=int(max_initial_nodes)
        ).single()
        
        top_org_ids = top_orgs["top_org_ids"] if top_orgs else []
        
        # Create projection with limited organizations and top edges
        session.run(
            """
            CALL gds.graph.project.cypher(
                $name,
                'MATCH (o:Organization) WHERE id(o) IN $topOrgIds RETURN id(o) AS id',
                'MATCH (o1:Organization)-[:PARTICIPATES_IN]->(p:Project)<-[:PARTICIPATES_IN]-(o2:Organization) 
                 WHERE id(p) IN $pids AND id(o1) < id(o2) 
                   AND id(o1) IN $topOrgIds AND id(o2) IN $topOrgIds
                 WITH o1, o2, count(DISTINCT p) AS weight
                 ORDER BY weight DESC
                 LIMIT $maxEdges
                 RETURN id(o1) AS source, id(o2) AS target, weight',
                {parameters: {pids: $pids, topOrgIds: $topOrgIds, maxEdges: $maxEdges}}
            )
            """,
            name=graph_name,
            pids=pids,
            topOrgIds=top_org_ids,
            maxEdges=int(max_initial_edges)
        )
        
        # Get the total number of edges in the projection (before hybrid filtering)
        total_edges_result = session.run(
            """
            CALL gds.graph.relationshipProperties.stream($name, ['weight'])
            YIELD sourceNodeId, targetNodeId, propertyValue
            RETURN count(*) AS total_edges
            """,
            name=graph_name
        ).single()
        
        total_edges = int(total_edges_result["total_edges"]) if total_edges_result else 0
        
        # Calculate hybrid weights and filter relationships (for reporting purposes)
        result = session.run(
            """
            MATCH (o1:Organization)-[:PARTICIPATES_IN]->(p:Project)<-[:PARTICIPATES_IN]-(o2:Organization)
            WHERE id(p) IN $pids AND id(o1) < id(o2)
            WITH o1, o2, count(DISTINCT p) AS weight
            WHERE weight >= $minWeight
            WITH o1, o2, weight, o1.SemanticGNNEmbedding AS v1, o2.SemanticGNNEmbedding AS v2
            WITH o1, o2, weight,
                 CASE WHEN v1 IS NULL OR v2 IS NULL THEN 0.0
                      ELSE gds.similarity.cosine(v1, v2) END AS sim
            WHERE sim >= $simMin
            WITH o1, o2, weight, sim,
                 (toFloat(weight) * (1 - $epsilon) + sim * $epsilon) AS hybrid
            RETURN count(*) AS edges_created,
                   collect(DISTINCT o1.id) + collect(DISTINCT o2.id) AS org_ids
            """,
            pids=pids,
            minWeight=int(min_weight),
            simMin=float(sim_min),
            epsilon=float(epsilon)
        ).single()
        
        edges_created = int(result["edges_created"]) if result and "edges_created" in result else 0
        org_ids = list(set(result["org_ids"])) if result and result["org_ids"] else []
        
        print(f"Created projection graph {graph_name} with {total_edges} total edges, {edges_created} edges pass hybrid filtering")
        print(f"Initial graph size limited to {len(top_org_ids)} nodes and {max_initial_edges} edges for faster processing")
        return total_edges, pids, org_ids

def run_louvain_community_detection_on_projection(driver, graph_name: str, write_prop: str):
    """
    Run Louvain community detection on a projection graph and store results in the projection.
    """
    with driver.session() as session:
        try:
            # Run Louvain on the projection graph
            res = session.run(
                """
                CALL gds.louvain.stream($name, {
                  relationshipWeightProperty: 'weight'
                }) YIELD nodeId, communityId
                RETURN count(nodeId) as nodes_processed
                """,
                name=graph_name
            ).data()
            
            # Get statistics
            stats = session.run(
                """
                CALL gds.louvain.stats($name, {
                  relationshipWeightProperty: 'weight'
                }) YIELD communityCount, modularity, ranLevels
                RETURN communityCount, modularity, ranLevels
                """,
                name=graph_name
            ).single()
            
            nodes_processed = res[0]['nodes_processed'] if res else 0
            print(f"Processed {nodes_processed} nodes with Louvain community detection")
            
            return stats
        except Exception as e:
            print(f"Error in Louvain community detection: {e}")
            return None

def fetch_graph_from_projection(driver, graph_name: str, lucene_query: str, write_prop: str, pids: list, *,
                               min_weight_filter: int, min_hybrid: float,
                               max_edges: int, max_nodes: int, show_isolates: bool) -> Dict[str, Any]:
    """
    Fetch graph data from a projection graph for visualization.
    """
    with driver.session() as session:
        try:
            # Get nodes that are part of the projection by checking which organizations participate in the matching projects
            nodes_result = session.run(
                """
                MATCH (o:Organization)-[:PARTICIPATES_IN]->(p:Project)
                WHERE id(p) IN $pids
                RETURN DISTINCT o.id AS org_id, o.name AS name
                """,
                pids=pids
            ).data()
            
            # Get relationships from projection with hybrid weight calculation
            edges_result = session.run(
                """
                CALL gds.graph.streamRelationshipProperties($name, ['weight'])
                YIELD sourceNodeId, targetNodeId, propertyValue
                WITH sourceNodeId, targetNodeId, propertyValue AS weight
                MATCH (o1:Organization) WHERE id(o1) = sourceNodeId
                MATCH (o2:Organization) WHERE id(o2) = targetNodeId
                WITH o1, o2, weight, o1.SemanticGNNEmbedding AS v1, o2.SemanticGNNEmbedding AS v2
                WITH o1, o2, weight,
                     CASE WHEN v1 IS NULL OR v2 IS NULL THEN 0.0
                          ELSE gds.similarity.cosine(v1, v2) END AS sim
                WHERE weight >= $minWeight
                WITH o1, o2, weight, sim,
                     (toFloat(weight) * 0.9 + sim * 0.1) AS hybrid
                WHERE hybrid >= $minHybrid
                RETURN o1.id AS src_id, o2.id AS dst_id, o1.name AS src_name, o2.name AS dst_name, weight AS weight, sim AS sim, hybrid AS hybrid
                ORDER BY hybrid DESC
                LIMIT $maxE
                """,
                name=graph_name,
                minWeight=int(min_weight_filter),
                minHybrid=float(min_hybrid),
                maxE=int(max_edges)
            ).data()
            
            # Get community information if available
            communities_result = session.run(
                """
                CALL gds.louvain.stream($name, {
                  relationshipWeightProperty: 'weight'
                }) YIELD nodeId, communityId
                MATCH (o:Organization) WHERE id(o) = nodeId
                RETURN o.id AS org_id, communityId
                """,
                name=graph_name
            ).data()
            
            # Create community mapping
            community_map = {item['org_id']: item['communityId'] for item in communities_result}
            
            # Build nodes list
            nodes = []
            for node in nodes_result:
                node_data_item = {
                    'id': node['org_id'],
                    'name': node['name'],
                    'community': community_map.get(node['org_id'], -1)
                }
                nodes.append(node_data_item)
            
            # Build edges list
            edges = []
            for edge in edges_result:
                edge_data = {
                    'src_id': edge['src_id'],
                    'dst_id': edge['dst_id'],
                    'src_label': edge['src_name'],
                    'dst_label': edge['dst_name'],
                    'weight': edge['weight'],
                    'sim': edge['sim'],
                    'hybrid': edge['hybrid']
                }
                edges.append(edge_data)
            
            return {
                'nodes': nodes,
                'edges': edges,
                'query_matched': True,
                'total_nodes': len(nodes),
                'total_edges': len(edges)
            }
            
        except Exception as e:
            print(f"Error fetching graph from projection: {e}")
            return {
                'nodes': [],
                'edges': [],
                'query_matched': False,
                'total_nodes': 0,
                'total_edges': 0
            }

def fetch_heatmap_data(lucene_query: str, min_score: float, limit_projects: int) -> List[Dict[str, Any]]:
    """
    Fetch geographic data for heatmap visualization.
    Returns data with country (ISO2), projects count, and ec_sum.
    """
    driver = make_neo4j_driver(require_password=True)
    try:
        with driver.session() as session:
            # First, get project IDs from fulltext search
            project_ids_result = session.run(
                """
                CALL db.index.fulltext.queryNodes('semanticNodeTextIndex', $lucene_query)
                YIELD node, score
                WHERE node:Project AND score >= $min_score
                RETURN id(node) as pid
                ORDER BY score DESC
                LIMIT $limit_projects
                """,
                lucene_query=lucene_query,
                min_score=min_score,
                limit_projects=limit_projects
            ).data()
            
            if not project_ids_result:
                return []
            
            pids = [row['pid'] for row in project_ids_result]
            
            # Then, get geographic aggregation
            geographic_data = session.run(
                """
                MATCH (o:Organization)-[r:PARTICIPATES_IN]->(p:Project)
                WHERE id(p) IN $pids AND coalesce(o.country, '') <> ''
                WITH o.country AS country,
                     count(DISTINCT p) AS projects,
                     sum(coalesce(r.totalCost, 0.0)) AS ec_sum
                RETURN country, projects, ec_sum
                ORDER BY projects DESC
                """,
                pids=pids
            ).data()
            
            return geographic_data
            
    except Exception as e:
        print(f"Error fetching heatmap data: {e}")
        return []
    finally:
        try:
            driver.close()
        except Exception:
            pass