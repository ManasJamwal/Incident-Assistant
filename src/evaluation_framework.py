"""
Evaluation Framework for Incident Search & Triage
Calculates Mean Reciprocal Rank (MRR), Hit Rate @ K, and Latency percentiles (p50, p90, p95, p99).
"""

import time
import numpy as np
from typing import List, Dict, Any, Optional
from .models import EvaluationBenchmarkResult
from .hybrid_retriever import HybridRetriever


# Comprehensive Ground-Truth Incident Benchmark Suite
BENCHMARK_CASES: List[Dict[str, Any]] = [
    # 1. Error Codes & Exceptions
    {
        "query": "HTTP 502 Bad Gateway: Upstream payment processor dropped connection",
        "expected_targets": ["runbook_502_bad_gateway", "INC-2024-042", "GatewayTimeoutError", "send_upstream_transaction"],
        "category": "error_code"
    },
    {
        "query": "PoolExhaustionError: Timeout waiting for connection from pool size 20",
        "expected_targets": ["runbook_db_connection_exhaustion", "INC-2024-001", "DatabaseConnectionPool", "acquire_db_connection"],
        "category": "error_code"
    },
    {
        "query": "MemoryThresholdExceeded: Pod status: OOMKilled (Exit Code 137)",
        "expected_targets": ["runbook_oom_killed_worker", "INC-2024-089", "WorkerConsumer", "consume_batch_messages"],
        "category": "error_code"
    },
    {
        "query": "TokenExpiredError: Token signature expired or NTP time skew exceeded threshold",
        "expected_targets": ["runbook_jwt_auth_failure", "INC-2025-012", "validate_jwt_token", "TokenExpiredError"],
        "category": "error_code"
    },
    {
        "query": "CircuitBreakerOpenException: Payment circuit breaker tripped",
        "expected_targets": ["runbook_circuit_breaker_recovery", "CircuitBreakerOpenException", "process_charge"],
        "category": "error_code"
    },

    # 2. Function Names & Code Symbols
    {
        "query": "validate_jwt_token",
        "expected_targets": ["validate_jwt_token", "token_validator.py", "runbook_jwt_auth_failure"],
        "category": "code_symbol"
    },
    {
        "query": "acquire_db_connection",
        "expected_targets": ["acquire_db_connection", "DatabaseConnectionPool", "db_pool.py"],
        "category": "code_symbol"
    },
    {
        "query": "consume_batch_messages",
        "expected_targets": ["consume_batch_messages", "WorkerConsumer", "queue_consumer.py"],
        "category": "code_symbol"
    },
    {
        "query": "process_charge",
        "expected_targets": ["process_charge", "PaymentProcessor", "processor.py"],
        "category": "code_symbol"
    },
    {
        "query": "refresh_session_cache",
        "expected_targets": ["refresh_session_cache", "RedisSessionManager", "INC-2025-033"],
        "category": "code_symbol"
    },

    # 3. Stack Traces
    {
        "query": 'File "checkout_flow.py", line 25, in execute_checkout_transaction',
        "expected_targets": ["execute_checkout_transaction", "checkout_flow.py", "CheckoutCoordinator"],
        "category": "stack_trace"
    },
    {
        "query": 'File "client.py", line 32, in send_upstream_transaction',
        "expected_targets": ["send_upstream_transaction", "client.py", "GatewayTimeoutError"],
        "category": "stack_trace"
    },
    {
        "query": 'File "token_validator.py", line 42, in validate_jwt_token',
        "expected_targets": ["validate_jwt_token", "token_validator.py", "TokenExpiredError"],
        "category": "stack_trace"
    },
    {
        "query": 'File "queue_consumer.py", line 36, in consume_batch_messages',
        "expected_targets": ["consume_batch_messages", "queue_consumer.py", "WorkerConsumer"],
        "category": "stack_trace"
    },

    # 4. Natural Language Symptom Descriptions
    {
        "query": "users experiencing checkout hangs and timeout errors during flash sale",
        "expected_targets": ["INC-2024-001", "runbook_db_connection_exhaustion", "checkout_service"],
        "category": "symptom_nl"
    },
    {
        "query": "upstream payment vendor timing out during credit card authorization",
        "expected_targets": ["INC-2024-042", "runbook_502_bad_gateway", "payment_service"],
        "category": "symptom_nl"
    },
    {
        "query": "background worker pods crashing repeatedly with memory limit exceeded",
        "expected_targets": ["INC-2024-089", "runbook_oom_killed_worker", "worker_service"],
        "category": "symptom_nl"
    },
    {
        "query": "active user sessions failing with 401 unauthorized due to clock drift across nodes",
        "expected_targets": ["INC-2025-012", "runbook_jwt_auth_failure", "auth_service"],
        "category": "symptom_nl"
    },
    {
        "query": "redis connections exhausted during mass email marketing campaign blast",
        "expected_targets": ["INC-2025-033", "redis_session.py", "RedisSessionManager"],
        "category": "symptom_nl"
    },
    {
        "query": "fast fail circuit breaker recovery procedures for third party gateway",
        "expected_targets": ["runbook_circuit_breaker_recovery", "payment_service", "CircuitBreakerOpenException"],
        "category": "symptom_nl"
    }
]


class EvaluationFramework:
    """
    Evaluates IR metrics and latency profiling for emergency response retrieval.
    """

    def __init__(self, retriever: HybridRetriever, benchmark_cases: Optional[List[Dict[str, Any]]] = None):
        self.retriever = retriever
        self.cases = benchmark_cases or BENCHMARK_CASES

    def run_benchmark(self, strategy: str = "hybrid", top_k: int = 5) -> EvaluationBenchmarkResult:
        """
        Executes all test queries against the specified strategy, measuring MRR and latency.
        """
        reciprocal_ranks: List[float] = []
        hits_at_1: List[int] = []
        hits_at_3: List[int] = []
        hits_at_5: List[int] = []
        latencies_ms: List[float] = []

        for case in self.cases:
            query = case["query"]
            targets = [t.lower() for t in case["expected_targets"]]

            # Timed query execution
            t_start = time.perf_counter()
            response = self.retriever.search(query, strategy=strategy, top_k=top_k)
            t_elapsed_ms = (time.perf_counter() - t_start) * 1000
            latencies_ms.append(t_elapsed_ms)

            # Check ranking of relevant documents
            first_match_rank: Optional[int] = None
            for item in response.results:
                # Check if item matches any expected targets
                item_identifiers = [
                    item.title.lower(),
                    item.source_path.lower(),
                    item.item_id.lower()
                ]
                if "signature" in item.metadata and item.metadata["signature"]:
                    item_identifiers.append(item.metadata["signature"].lower())
                if "exceptions" in item.metadata:
                    for exc in item.metadata["exceptions"]:
                        item_identifiers.append(exc.lower())

                # Target match condition
                is_hit = any(
                    any(target in ident for ident in item_identifiers)
                    for target in targets
                )
                if is_hit:
                    first_match_rank = item.rank
                    break

            if first_match_rank is not None:
                reciprocal_ranks.append(1.0 / first_match_rank)
                hits_at_1.append(1 if first_match_rank <= 1 else 0)
                hits_at_3.append(1 if first_match_rank <= 3 else 0)
                hits_at_5.append(1 if first_match_rank <= 5 else 0)
            else:
                reciprocal_ranks.append(0.0)
                hits_at_1.append(0)
                hits_at_3.append(0)
                hits_at_5.append(0)

        total_queries = len(self.cases)
        mrr = float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0
        h1 = float(np.mean(hits_at_1)) if hits_at_1 else 0.0
        h3 = float(np.mean(hits_at_3)) if hits_at_3 else 0.0
        h5 = float(np.mean(hits_at_5)) if hits_at_5 else 0.0

        latency_arr = np.array(latencies_ms)
        p50 = float(np.percentile(latency_arr, 50))
        p90 = float(np.percentile(latency_arr, 90))
        p95 = float(np.percentile(latency_arr, 95))
        p99 = float(np.percentile(latency_arr, 99))
        mean_lat = float(np.mean(latency_arr))

        return EvaluationBenchmarkResult(
            strategy_name=strategy,
            total_queries=total_queries,
            mrr=round(mrr, 4),
            hit_rate_at_1=round(h1, 4),
            hit_rate_at_3=round(h3, 4),
            hit_rate_at_5=round(h5, 4),
            latency_mean_ms=round(mean_lat, 2),
            latency_p50_ms=round(p50, 2),
            latency_p90_ms=round(p90, 2),
            latency_p95_ms=round(p95, 2),
            latency_p99_ms=round(p99, 2)
        )

    def run_all_ablations(self) -> Dict[str, EvaluationBenchmarkResult]:
        """Runs benchmarks across all strategies for comparative evaluation."""
        strategies = ["hybrid", "bm25_only", "dense_only", "ast_only"]
        results = {}
        for strat in strategies:
            results[strat] = self.run_benchmark(strategy=strat)
        return results
