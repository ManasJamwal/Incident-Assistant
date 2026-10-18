"""
Tests for Hybrid Retrieval (BM25, Dense Vectors, RRF) and Incident Assistant.
"""

import os
import pytest
from src.hybrid_retriever import HybridRetriever
from src.incident_assistant import IncidentAssistant


@pytest.fixture
def initialized_retriever():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    codebase_dir = os.path.join(base_dir, "data", "codebases")
    runbooks_dir = os.path.join(base_dir, "data", "runbooks")
    post_mortems_dir = os.path.join(base_dir, "data", "post_mortems")

    retriever = HybridRetriever()
    retriever.initialize_from_data(codebase_dir, runbooks_dir, post_mortems_dir)
    return retriever


def test_bm25_error_code_retrieval(initialized_retriever):
    res = initialized_retriever.search("HTTP 502 Bad Gateway", strategy="bm25_only")
    assert len(res.results) > 0
    top_result = res.results[0]
    assert "502" in top_result.title or "502" in top_result.source_path or "GatewayTimeout" in top_result.preview


def test_dense_symptom_retrieval(initialized_retriever):
    res = initialized_retriever.search("slow checkout query holding connections open", strategy="dense_only")
    assert len(res.results) > 0
    matched_ids = [r.title.lower() for r in res.results]
    assert any("connection" in t or "checkout" in t for t in matched_ids)


def test_hybrid_rrf_search(initialized_retriever):
    res = initialized_retriever.search("PoolExhaustionError: Timeout waiting for connection from pool size 20", strategy="hybrid")
    assert len(res.results) > 0
    assert res.latency.total_ms > 0
    # Top result should hit checkout service or pool exhaustion runbook/post-mortem
    top_matches = [r.title for r in res.results[:3]]
    assert any("Pool" in m or "checkout" in m.lower() for m in top_matches)


def test_incident_assistant_triage(initialized_retriever):
    assistant = IncidentAssistant(initialized_retriever)
    report = assistant.diagnose_incident("HTTP 502 Bad Gateway: Upstream payment processor dropped connection")
    
    assert report.detected_severity in ("P0", "P1")
    assert "payment" in report.identified_service.lower() or "upstream" in report.probable_root_cause.lower()
    assert len(report.immediate_actions) > 0
    assert len(report.diagnostic_commands) > 0
