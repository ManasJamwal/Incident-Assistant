"""
Unit tests for AST Code Indexer and lexical symbol extraction.
"""

import os
import pytest
from src.ast_code_indexer import ASTCodeIndexer


@pytest.fixture
def indexer():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    codebase_dir = os.path.join(base_dir, "data", "codebases")
    idx = ASTCodeIndexer()
    idx.index_directory(codebase_dir)
    return idx


def test_ast_symbol_extraction(indexer):
    symbols = indexer.get_all_symbols()
    assert len(symbols) > 0

    names = [s.symbol_name for s in symbols]
    assert "DatabaseConnectionPool" in names
    assert "process_charge" in names or "PaymentProcessor.process_charge" in names
    assert "validate_jwt_token" in names
    assert "WorkerConsumer.consume_batch_messages" in names


def test_exception_extraction(indexer):
    symbols = indexer.get_all_symbols()
    raised_all = [exc for s in symbols for exc in s.raised_exceptions]
    assert "GatewayTimeoutError" in raised_all
    assert "PoolExhaustionError" in raised_all
    assert "TokenExpiredError" in raised_all
    assert "MemoryThresholdExceeded" in raised_all


def test_exact_lexical_lookup(indexer):
    matches = indexer.exact_match("validate_jwt_token")
    assert len(matches) > 0
    assert any("validate_jwt_token" in m.symbol_name for m in matches)

    exc_matches = indexer.exact_match("GatewayTimeoutError")
    assert len(exc_matches) > 0
