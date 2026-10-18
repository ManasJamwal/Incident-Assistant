"""
Domain data models for Incident Assistant, Hybrid Search, and Evaluation.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ASTSymbol(BaseModel):
    """Extracted code symbol via Abstract Syntax Tree."""
    symbol_name: str
    symbol_type: str  # 'function', 'class', 'method', 'variable'
    service: str
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    raised_exceptions: List[str] = Field(default_factory=list)
    calls: List[str] = Field(default_factory=list)
    signature: Optional[str] = None
    code_snippet: str


class TextDocument(BaseModel):
    """Architectural documentation, runbook, or incident post-mortem."""
    doc_id: str
    title: str
    doc_type: str  # 'runbook', 'post_mortem', 'architecture'
    file_path: str
    severity: Optional[str] = "P1"
    content: str
    summary: Optional[str] = None
    remediation_steps: List[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Ranked item returned from hybrid retrieval."""
    item_id: str
    item_type: str  # 'code_ast', 'runbook', 'post_mortem'
    title: str
    source_path: str
    score: float
    rank: int
    bm25_score: Optional[float] = 0.0
    dense_score: Optional[float] = 0.0
    ast_exact_match: bool = False
    preview: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LatencyBreakdown(BaseModel):
    """Sub-millisecond profiling for search execution."""
    lexical_ms: float
    dense_ms: float
    fusion_ms: float
    total_ms: float


class QueryResponse(BaseModel):
    """Hybrid search response payload."""
    query: str
    detected_intent: str
    retrieval_strategy: str
    results: List[SearchResult]
    latency: LatencyBreakdown
    total_matches: int


class IncidentTriageReport(BaseModel):
    """Emergency incident diagnosis and response recommendation."""
    query: str
    detected_severity: str  # P0, P1, P2
    probable_root_cause: str
    confidence_score: float
    identified_service: str
    relevant_code_symbols: List[Dict[str, Any]]
    matched_post_mortems: List[Dict[str, Any]]
    recommended_runbooks: List[Dict[str, Any]]
    immediate_actions: List[str]
    diagnostic_commands: List[str]
    retrieval_latency_ms: float


class EvaluationBenchmarkResult(BaseModel):
    """Benchmark performance metrics for a retrieval strategy."""
    strategy_name: str
    total_queries: int
    mrr: float
    hit_rate_at_1: float
    hit_rate_at_3: float
    hit_rate_at_5: float
    latency_mean_ms: float
    latency_p50_ms: float
    latency_p90_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
