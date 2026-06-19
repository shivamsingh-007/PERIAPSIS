from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.graphify.client import graphify_client
from packages.graphify.knowledge_graph import knowledge_graph
from packages.graphify.context_assembler import context_assembler
from packages.graphify.impact_tracer import impact_tracer
from packages.graphify.graph_router import graph_router

router = APIRouter(prefix="/graph", tags=["graph"])


class BuildRequest(BaseModel):
    target_dir: str = "."
    force: bool = False
    mode: str = "default"


class QueryRequest(BaseModel):
    question: str
    budget: int | None = None


class PathRequest(BaseModel):
    source: str
    target: str


class ExplainRequest(BaseModel):
    concept: str


class ContextRequest(BaseModel):
    goal: str
    mode: str = "planning"


class ImpactRequest(BaseModel):
    node_id: str
    depth: int = 2


class RouteRequest(BaseModel):
    task: str


@router.post("/build")
async def build_graph(req: BuildRequest) -> dict:
    try:
        result = await knowledge_graph.build(
            target_dir=req.target_dir,
            force=req.force,
        )
        return {"status": "ok", "snapshot": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def update_graph(req: BuildRequest) -> dict:
    try:
        result = await knowledge_graph.update(target_dir=req.target_dir)
        return {"status": "ok", "snapshot": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_graph(req: QueryRequest) -> dict:
    result = await knowledge_graph.query(req.question, budget=req.budget)
    return {
        "status": "ok",
        "nodes": [n.model_dump() for n in result.nodes],
        "node_count": result.node_count,
    }


@router.post("/path")
async def find_path(req: PathRequest) -> dict:
    result = await knowledge_graph.find_path(req.source, req.target)
    return {
        "status": "ok",
        "path": result.path,
        "found": result.found,
    }


@router.post("/explain")
async def explain_concept(req: ExplainRequest) -> dict:
    result = await knowledge_graph.explain(req.concept)
    return {"status": "ok", **result}


@router.get("/node/{node_id}")
async def get_node(node_id: str) -> dict:
    node = knowledge_graph.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "ok", "node": node.model_dump()}


@router.get("/neighbors/{node_id}")
async def get_neighbors(node_id: str, depth: int = 1) -> dict:
    neighbors = knowledge_graph.get_neighbors(node_id, depth=depth)
    return {
        "status": "ok",
        "neighbors": [n.model_dump() for n in neighbors],
        "count": len(neighbors),
    }


@router.get("/search")
async def search_concepts(q: str, limit: int = 10) -> dict:
    results = knowledge_graph.search_concepts(q, limit=limit)
    return {
        "status": "ok",
        "results": [n.model_dump() for n in results],
        "count": len(results),
    }


@router.post("/context")
async def assemble_context(req: ContextRequest) -> dict:
    if req.mode == "planning":
        ctx = await context_assembler.assemble_for_planning(req.goal)
    elif req.mode == "editing":
        ctx = await context_assembler.assemble_for_editing(req.goal)
    elif req.mode == "reflection":
        ctx = await context_assembler.assemble_for_reflection(req.goal)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {req.mode}")

    return {
        "status": "ok",
        "goal": ctx.goal,
        "chunks": [c.model_dump() for c in ctx.chunks],
        "total_tokens_estimate": ctx.total_tokens_estimate,
        "sources_consulted": ctx.sources_consulted,
        "graph_queries": ctx.graph_queries,
    }


@router.post("/impact")
async def trace_impact(req: ImpactRequest) -> dict:
    result = impact_tracer.trace_change_impact(req.node_id, depth=req.depth)
    return {
        "status": "ok",
        "impact": result.model_dump(),
    }


@router.get("/critique/{node_id}")
async def architectural_critique(node_id: str) -> dict:
    result = impact_tracer.get_architectural_critique(node_id)
    return {"status": "ok", **result}


@router.post("/route")
async def route_task(req: RouteRequest) -> dict:
    decision = graph_router.route_task(req.task)
    return {"status": "ok", "decision": decision.model_dump()}


@router.get("/route/files/{file_path:path}")
async def route_file(file_path: str) -> dict:
    decision = graph_router.route_file_edit(file_path)
    return {"status": "ok", "decision": decision.model_dump()}


@router.get("/stats")
async def graph_stats() -> dict:
    return {
        "status": "ok",
        "knowledge_graph": knowledge_graph.get_stats(),
        "context_assembler": context_assembler.get_stats(),
        "graph_router": graph_router.get_stats(),
    }


@router.get("/architecture")
async def architecture_overview() -> dict:
    overview = knowledge_graph.get_architecture_overview()
    return {"status": "ok", **overview}
