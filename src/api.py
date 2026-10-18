"""
FastAPI REST API Service for Incident Assistant
Provides endpoints for hybrid search, live outage triage, benchmark evaluation, and corpus inspection.
"""

import os
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .ast_code_indexer import ASTCodeIndexer
from .dense_doc_indexer import DenseDocIndexer
from .hybrid_retriever import HybridRetriever
from .incident_assistant import IncidentAssistant
from .evaluation_framework import EvaluationFramework
from .models import QueryResponse, IncidentTriageReport

# Initialize paths relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEBASE_DIR = os.path.join(BASE_DIR, "data", "codebases")
RUNBOOKS_DIR = os.path.join(BASE_DIR, "data", "runbooks")
POST_MORTEMS_DIR = os.path.join(BASE_DIR, "data", "post_mortems")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="Codebase & IT Infrastructure Incident Assistant",
    description="High-velocity hybrid retrieval and outage triage engine (AST + BM25 + Dense Vectors)",
    version="1.0.0"
)

# Global engines
retriever = HybridRetriever()
assistant = IncidentAssistant(retriever)
evaluator = EvaluationFramework(retriever)

# Initialize corpus indices immediately
retriever.initialize_from_data(
    codebase_dir=CODEBASE_DIR,
    runbooks_dir=RUNBOOKS_DIR,
    post_mortems_dir=POST_MORTEMS_DIR
)


class SearchRequest(BaseModel):
    query: str
    strategy: Optional[str] = "hybrid"
    top_k: Optional[int] = 5


class TriageRequest(BaseModel):
    query: str
    strategy: Optional[str] = "hybrid"


@app.get("/api/health")
def health_check():
    """Returns engine health and index statistics."""
    return {
        "status": "healthy",
        "ast_symbols_indexed": len(retriever.ast_indexer.symbols),
        "documents_indexed": len(retriever.doc_indexer.documents),
        "bm25_items_indexed": len(retriever.corpus_items),
        "vector_dimensions": retriever.doc_indexer.vector_dim
    }


@app.post("/api/search", response_model=QueryResponse)
def execute_search(req: SearchRequest):
    """Executes hybrid retrieval across code and documentation."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty")
    return retriever.search(query=req.query, strategy=req.strategy or "hybrid", top_k=req.top_k or 5)


@app.post("/api/triage", response_model=IncidentTriageReport)
def execute_triage(req: TriageRequest):
    """Synthesizes live incident diagnosis, root cause hypothesis, and runbook mitigation."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Incident query string cannot be empty")
    return assistant.diagnose_incident(query=req.query, strategy=req.strategy or "hybrid")


@app.get("/api/benchmark")
def run_evaluation(strategy: Optional[str] = None):
    """
    Evaluates Mean Reciprocal Rank (MRR) and Latency percentiles (p50, p90, p95, p99).
    If strategy is provided, runs single benchmark; otherwise runs comparative ablation.
    """
    if strategy:
        result = evaluator.run_benchmark(strategy=strategy)
        return {"benchmark": result}
    else:
        results = evaluator.run_all_ablations()
        return {"ablations": results}


@app.get("/api/corpus")
def get_corpus():
    """Lists indexed code repositories, runbooks, and post-mortems."""
    symbols = [
        {
            "name": s.symbol_name,
            "type": s.symbol_type,
            "service": s.service,
            "file": os.path.basename(s.file_path),
            "lines": f"{s.line_start}-{s.line_end}",
            "exceptions": s.raised_exceptions
        }
        for s in retriever.ast_indexer.symbols
    ]
    docs = [
        {
            "id": d.doc_id,
            "title": d.title,
            "type": d.doc_type,
            "severity": d.severity,
            "remediation_count": len(d.remediation_steps)
        }
        for d in retriever.doc_indexer.documents
    ]
    return {
        "symbols": symbols,
        "documents": docs
    }


# Mount static web UI files
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def serve_ui():
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Incident Assistant API is running. UI not found."}
