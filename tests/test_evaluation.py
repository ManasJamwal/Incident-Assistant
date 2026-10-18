"""
Tests for Evaluation Framework metrics: MRR, Hit Rate, and Latency percentiles.
"""

import os
import pytest
from src.hybrid_retriever import HybridRetriever
from src.evaluation_framework import EvaluationFramework


@pytest.fixture
def framework():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    codebase_dir = os.path.join(base_dir, "data", "codebases")
    runbooks_dir = os.path.join(base_dir, "data", "runbooks")
    post_mortems_dir = os.path.join(base_dir, "data", "post_mortems")

    retriever = HybridRetriever()
    retriever.initialize_from_data(codebase_dir, runbooks_dir, post_mortems_dir)
    return EvaluationFramework(retriever)


def test_benchmark_metrics_structure(framework):
    res = framework.run_benchmark(strategy="hybrid")
    
    assert res.total_queries > 0
    assert 0.0 <= res.mrr <= 1.0
    assert 0.0 <= res.hit_rate_at_1 <= 1.0
    assert 0.0 <= res.hit_rate_at_5 <= 1.0
    assert res.hit_rate_at_1 <= res.hit_rate_at_5
    
    # Latency percentiles ordering
    assert res.latency_p50_ms <= res.latency_p95_ms
    assert res.latency_p95_ms <= res.latency_p99_ms
    # Emergency response latency requirement: p95 under 100ms
    assert res.latency_p95_ms < 100.0


def test_comparative_ablations(framework):
    ablations = framework.run_all_ablations()
    assert "hybrid" in ablations
    assert "bm25_only" in ablations
    assert "dense_only" in ablations
    assert "ast_only" in ablations
    
    # Hybrid search should achieve highest overall MRR
    hybrid_mrr = ablations["hybrid"].mrr
    assert hybrid_mrr >= ablations["ast_only"].mrr
    assert hybrid_mrr >= ablations["dense_only"].mrr
