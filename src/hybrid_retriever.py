"""
Hybrid Retrieval Engine
Combines AST exact lexical matching, BM25 keyword retrieval, and dense semantic embeddings.
"""

import time
import os
import math
from typing import List, Dict, Any, Optional, Tuple
from rank_bm25 import BM25Okapi

from .models import ASTSymbol, TextDocument, SearchResult, LatencyBreakdown, QueryResponse
from .ast_code_indexer import ASTCodeIndexer
from .dense_doc_indexer import DenseDocIndexer
from .tokenizer import tokenize_incident_query, tokenize_code, tokenize_doc_text, ERROR_CODE_REGEX, STACKTRACE_LINE_REGEX


class HybridRetriever:
    """
    Coordinates multi-modal indexing and hybrid retrieval across codebase ASTs and incident docs.
    """

    def __init__(self, ast_indexer: Optional[ASTCodeIndexer] = None, doc_indexer: Optional[DenseDocIndexer] = None):
        self.ast_indexer = ast_indexer or ASTCodeIndexer()
        self.doc_indexer = doc_indexer or DenseDocIndexer()
        
        # Unified BM25 Corpus
        self.corpus_items: List[Dict[str, Any]] = []  # List of dicts representing code or docs
        self.bm25_corpus_tokens: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

    def initialize_from_data(self, codebase_dir: str, runbooks_dir: str, post_mortems_dir: str):
        """Indexes all repositories, runbooks, and post-mortems."""
        # 1. Index AST code
        self.ast_indexer.index_directory(codebase_dir)

        # 2. Index Dense docs
        self.doc_indexer.index_directory(runbooks_dir, post_mortems_dir)

        # 3. Build unified BM25 index
        self._build_bm25_index()

    def _build_bm25_index(self):
        """Builds tokenized corpus for BM25 retrieval."""
        self.corpus_items = []
        self.bm25_corpus_tokens = []

        # Add AST symbols to BM25
        for sym in self.ast_indexer.get_all_symbols():
            item_id = f"ast::{sym.service}::{sym.symbol_name}::{sym.line_start}"
            text_repr = (
                f"{sym.symbol_name} {sym.signature or ''} "
                f"{' '.join(sym.raised_exceptions)} {' '.join(sym.calls)} "
                f"{sym.docstring or ''} {sym.code_snippet}"
            )
            tokens = tokenize_code(text_repr)
            self.corpus_items.append({
                "item_id": item_id,
                "type": "code_ast",
                "obj": sym,
                "title": f"{sym.symbol_name} ({sym.service})",
                "source": sym.file_path,
                "snippet": sym.code_snippet[:300] + ("..." if len(sym.code_snippet) > 300 else "")
            })
            self.bm25_corpus_tokens.append(tokens)

        # Add Documentation (runbooks and post-mortems) to BM25
        for doc in self.doc_indexer.documents:
            item_id = f"doc::{doc.doc_type}::{doc.doc_id}"
            tokens = tokenize_doc_text(f"{doc.title} {doc.doc_id} {doc.content}")
            self.corpus_items.append({
                "item_id": item_id,
                "type": doc.doc_type,
                "obj": doc,
                "title": doc.title,
                "source": doc.file_path,
                "snippet": doc.content[:300] + ("..." if len(doc.content) > 300 else "")
            })
            self.bm25_corpus_tokens.append(tokens)

        if self.bm25_corpus_tokens:
            self.bm25 = BM25Okapi(self.bm25_corpus_tokens, k1=1.5, b=0.75)

    def detect_query_intent(self, query: str) -> str:
        """
        Classifies incoming outage query into:
        - CODE_EXACT: contains stack traces, error codes (502, 137), or function signatures
        - SYMPTOM_NL: natural language descriptions of outage symptoms
        - HYBRID_INCIDENT: combination of technical names and symptom keywords
        """
        has_error_code = bool(ERROR_CODE_REGEX.search(query))
        has_stack_trace = bool(STACKTRACE_LINE_REGEX.search(query)) or "traceback" in query.lower() or 'line ' in query.lower()
        has_code_syntax = any(char in query for char in ["()", "->", "::", ".", "_"])

        if has_stack_trace or (has_error_code and has_code_syntax):
            return "CODE_EXACT"
        elif has_error_code or has_code_syntax:
            return "HYBRID_INCIDENT"
        else:
            return "SYMPTOM_NL"

    def search(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5
    ) -> QueryResponse:
        """
        Performs hybrid retrieval with latency profiling.
        Strategies: 'hybrid', 'bm25_only', 'dense_only', 'ast_only'
        """
        t0 = time.perf_counter()
        intent = self.detect_query_intent(query)
        q_tokens = tokenize_incident_query(query)

        lexical_time = 0.0
        dense_time = 0.0
        fusion_time = 0.0

        bm25_scores: Dict[str, float] = {}
        dense_scores: Dict[str, float] = {}
        ast_matches: List[ASTSymbol] = []

        # 1. AST Exact Match
        t_ast_start = time.perf_counter()
        if strategy in ("hybrid", "ast_only"):
            ast_matches = self.ast_indexer.exact_match(query)
        t_ast_end = time.perf_counter()

        # 2. BM25 Retrieval
        t_bm25_start = time.perf_counter()
        if strategy in ("hybrid", "bm25_only") and self.bm25 is not None and q_tokens:
            scores = self.bm25.get_scores(q_tokens)
            for idx, score in enumerate(scores):
                if score > 0.1:
                    bm25_scores[self.corpus_items[idx]["item_id"]] = float(score)
        t_bm25_end = time.perf_counter()
        lexical_time = (t_ast_end - t_ast_start) + (t_bm25_end - t_bm25_start)

        # 3. Dense Vector Retrieval
        t_dense_start = time.perf_counter()
        if strategy in ("hybrid", "dense_only"):
            dense_docs = self.doc_indexer.query_dense(query, top_k=top_k * 2)
            for doc, score in dense_docs:
                item_id = f"doc::{doc.doc_type}::{doc.doc_id}"
                dense_scores[item_id] = float(score)
        t_dense_end = time.perf_counter()
        dense_time = t_dense_end - t_dense_start

        # 4. Fusion
        t_fusion_start = time.perf_counter()
        ranked_results: List[SearchResult] = []

        if strategy == "ast_only":
            ranked_results = self._rank_ast_only(ast_matches, top_k)
        elif strategy == "bm25_only":
            ranked_results = self._rank_bm25_only(bm25_scores, top_k)
        elif strategy == "dense_only":
            ranked_results = self._rank_dense_only(dense_scores, top_k)
        else:
            # Hybrid Fusion (RRF + Intent Weighting)
            ranked_results = self._rank_hybrid_rrf(
                query=query,
                intent=intent,
                ast_matches=ast_matches,
                bm25_scores=bm25_scores,
                dense_scores=dense_scores,
                top_k=top_k
            )
        t_fusion_end = time.perf_counter()
        fusion_time = t_fusion_end - t_fusion_start

        total_time = time.perf_counter() - t0

        latency = LatencyBreakdown(
            lexical_ms=round(lexical_time * 1000, 3),
            dense_ms=round(dense_time * 1000, 3),
            fusion_ms=round(fusion_time * 1000, 3),
            total_ms=round(total_time * 1000, 3)
        )

        return QueryResponse(
            query=query,
            detected_intent=intent,
            retrieval_strategy=strategy,
            results=ranked_results,
            latency=latency,
            total_matches=len(ranked_results)
        )

    def _rank_ast_only(self, ast_matches: List[ASTSymbol], top_k: int) -> List[SearchResult]:
        results = []
        for rank, sym in enumerate(ast_matches[:top_k], start=1):
            item_id = f"ast::{sym.service}::{sym.symbol_name}::{sym.line_start}"
            results.append(SearchResult(
                item_id=item_id,
                item_type="code_ast",
                title=f"{sym.symbol_name} ({sym.service})",
                source_path=sym.file_path,
                score=1.0,
                rank=rank,
                ast_exact_match=True,
                preview=sym.code_snippet,
                metadata={
                    "service": sym.service,
                    "line_start": sym.line_start,
                    "line_end": sym.line_end,
                    "exceptions": sym.raised_exceptions,
                    "signature": sym.signature
                }
            ))
        return results

    def _rank_bm25_only(self, bm25_scores: Dict[str, float], top_k: int) -> List[SearchResult]:
        sorted_items = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        item_lookup = {item["item_id"]: item for item in self.corpus_items}
        for rank, (item_id, score) in enumerate(sorted_items, start=1):
            meta = item_lookup.get(item_id)
            if not meta:
                continue
            results.append(SearchResult(
                item_id=item_id,
                item_type=meta["type"],
                title=meta["title"],
                source_path=meta["source"],
                score=round(score, 4),
                rank=rank,
                bm25_score=round(score, 4),
                preview=meta["snippet"],
                metadata={}
            ))
        return results

    def _rank_dense_only(self, dense_scores: Dict[str, float], top_k: int) -> List[SearchResult]:
        sorted_items = sorted(dense_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for rank, (item_id, score) in enumerate(sorted_items, start=1):
            doc_id = item_id.split("::")[-1]
            doc = self.doc_indexer.doc_map.get(doc_id)
            if not doc:
                continue
            results.append(SearchResult(
                item_id=item_id,
                item_type=doc.doc_type,
                title=doc.title,
                source_path=doc.file_path,
                score=round(score, 4),
                rank=rank,
                dense_score=round(score, 4),
                preview=doc.content[:300] + "...",
                metadata={"severity": doc.severity, "doc_id": doc.doc_id}
            ))
        return results

    def _rank_hybrid_rrf(
        self,
        query: str,
        intent: str,
        ast_matches: List[ASTSymbol],
        bm25_scores: Dict[str, float],
        dense_scores: Dict[str, float],
        top_k: int,
        k: int = 60
    ) -> List[SearchResult]:
        """
        Reciprocal Rank Fusion with adaptive intent-based weights.
        """
        # Dynamic Intent-based Weight Tuning
        if intent == "CODE_EXACT":
            w_ast = 2.5
            w_bm25 = 1.8
            w_dense = 0.6
        elif intent == "SYMPTOM_NL":
            w_ast = 0.5
            w_bm25 = 1.0
            w_dense = 2.2
        else:  # HYBRID_INCIDENT
            w_ast = 1.5
            w_bm25 = 1.5
            w_dense = 1.5

        rrf_scores: Dict[str, float] = {}

        # 1. AST Direct Matches
        ast_item_ids = set()
        for rank, sym in enumerate(ast_matches, start=1):
            item_id = f"ast::{sym.service}::{sym.symbol_name}::{sym.line_start}"
            ast_item_ids.add(item_id)
            rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (w_ast / (k + rank))

        # 2. BM25 Rankings
        sorted_bm25 = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (item_id, _) in enumerate(sorted_bm25, start=1):
            rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (w_bm25 / (k + rank))

        # 3. Dense Rankings
        sorted_dense = sorted(dense_scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (item_id, _) in enumerate(sorted_dense, start=1):
            rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (w_dense / (k + rank))

        # Sort combined results
        ranked_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        item_lookup = {item["item_id"]: item for item in self.corpus_items}
        final_results: List[SearchResult] = []

        for rank, (item_id, rrf_score) in enumerate(ranked_items, start=1):
            lookup_meta = item_lookup.get(item_id)
            if not lookup_meta:
                continue

            obj = lookup_meta["obj"]
            is_ast = item_id in ast_item_ids

            if isinstance(obj, ASTSymbol):
                res = SearchResult(
                    item_id=item_id,
                    item_type="code_ast",
                    title=f"{obj.symbol_name} ({obj.service})",
                    source_path=obj.file_path,
                    score=round(rrf_score, 5),
                    rank=rank,
                    bm25_score=round(bm25_scores.get(item_id, 0.0), 3),
                    dense_score=0.0,
                    ast_exact_match=is_ast,
                    preview=obj.code_snippet[:350],
                    metadata={
                        "service": obj.service,
                        "line_start": obj.line_start,
                        "line_end": obj.line_end,
                        "signature": obj.signature,
                        "exceptions": obj.raised_exceptions,
                        "docstring": obj.docstring
                    }
                )
            else:  # TextDocument
                res = SearchResult(
                    item_id=item_id,
                    item_type=obj.doc_type,
                    title=obj.title,
                    source_path=obj.file_path,
                    score=round(rrf_score, 5),
                    rank=rank,
                    bm25_score=round(bm25_scores.get(item_id, 0.0), 3),
                    dense_score=round(dense_scores.get(item_id, 0.0), 3),
                    ast_exact_match=False,
                    preview=obj.content[:350] + "...",
                    metadata={
                        "severity": obj.severity,
                        "doc_id": obj.doc_id,
                        "remediation_steps": obj.remediation_steps
                    }
                )
            final_results.append(res)

        return final_results
