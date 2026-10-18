#!/usr/bin/env python3
"""
CLI Evaluation Runner for Codebase & IT Infrastructure Incident Assistant
Evaluates Mean Reciprocal Rank (MRR) and Latency (p95) across retrieval strategies.
"""

import os
import sys
import json
from src.ast_code_indexer import ASTCodeIndexer
from src.dense_doc_indexer import DenseDocIndexer
from src.hybrid_retriever import HybridRetriever
from src.evaluation_framework import EvaluationFramework

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    codebase_dir = os.path.join(base_dir, "data", "codebases")
    runbooks_dir = os.path.join(base_dir, "data", "runbooks")
    post_mortems_dir = os.path.join(base_dir, "data", "post_mortems")

    print("=" * 80)
    print("CODEBASE & IT INFRASTRUCTURE INCIDENT ASSISTANT - IR EVALUATION FRAMEWORK")
    print("=" * 80)
    print(f"[*] Indexing codebases: {codebase_dir}")
    print(f"[*] Indexing runbooks: {runbooks_dir}")
    print(f"[*] Indexing post-mortems: {post_mortems_dir}")

    retriever = HybridRetriever()
    retriever.initialize_from_data(codebase_dir, runbooks_dir, post_mortems_dir)

    print(f"[+] Indexed {len(retriever.ast_indexer.symbols)} AST code symbols.")
    print(f"[+] Indexed {len(retriever.doc_indexer.documents)} markdown documentation files.")
    print(f"[+] Initialized BM25 index with {len(retriever.corpus_items)} total entries.")
    print("-" * 80)

    evaluator = EvaluationFramework(retriever)
    print(f"[*] Executing benchmark suite over {len(evaluator.cases)} real-world outage test queries...")
    print("-" * 80)

    results = evaluator.run_all_ablations()

    # Formatted Table Output
    header = f"{'Strategy':<18} | {'MRR':<8} | {'Hit@1':<8} | {'Hit@3':<8} | {'Hit@5':<8} | {'Mean(ms)':<10} | {'p50(ms)':<9} | {'p95(ms)':<9} | {'p99(ms)':<9}"
    print(header)
    print("-" * len(header))

    for strat_name, r in results.items():
        prefix = "> " if strat_name == "hybrid" else "  "
        print(
            f"{prefix + strat_name:<18} | "
            f"{r.mrr:<8.4f} | "
            f"{r.hit_rate_at_1 * 100:<7.1f}% | "
            f"{r.hit_rate_at_3 * 100:<7.1f}% | "
            f"{r.hit_rate_at_5 * 100:<7.1f}% | "
            f"{r.latency_mean_ms:<10.2f} | "
            f"{r.latency_p50_ms:<9.2f} | "
            f"{r.latency_p95_ms:<9.2f} | "
            f"{r.latency_p99_ms:<9.2f}"
        )

    print("=" * 80)
    hybrid_res = results.get("hybrid")
    if hybrid_res:
        print(f"[SUMMARY] Hybrid Search achieves MRR = {hybrid_res.mrr:.4f} with p95 Latency = {hybrid_res.latency_p95_ms:.2f} ms.")
        if hybrid_res.latency_p95_ms < 50.0:
            print("[PASS] Incident response latency requirement met: critical answers surfaced in milliseconds.")
    print("=" * 80)

if __name__ == "__main__":
    main()
