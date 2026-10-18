"""
Abstract Syntax Tree (AST) Code Indexer
Parses Python repositories into structured syntax units with exact lexical matching.
"""

import ast
import os
import glob
from typing import List, Dict, Optional, Set
from .models import ASTSymbol
from .tokenizer import tokenize_code, split_identifier


class ASTVisitor(ast.NodeVisitor):
    """Walks the AST tree to extract functions, classes, and exceptions."""

    def __init__(self, file_path: str, source_lines: List[str], service_name: str):
        self.file_path = file_path
        self.source_lines = source_lines
        self.service_name = service_name
        self.symbols: List[ASTSymbol] = []
        self._current_class: Optional[str] = None

    def _extract_snippet(self, start_line: int, end_line: int) -> str:
        # 1-indexed to 0-indexed slicing
        start_idx = max(0, start_line - 1)
        end_idx = min(len(self.source_lines), end_line)
        return "".join(self.source_lines[start_idx:end_idx])

    def _extract_docstring(self, node: ast.AST) -> Optional[str]:
        return ast.get_docstring(node)

    def _extract_raises(self, node: ast.AST) -> List[str]:
        raised = []
        for child in ast.walk(node):
            if isinstance(child, ast.Raise):
                if child.exc is None:
                    continue
                if isinstance(child.exc, ast.Name):
                    raised.append(child.exc.id)
                elif isinstance(child.exc, ast.Call):
                    if isinstance(child.exc.func, ast.Name):
                        raised.append(child.exc.func.id)
                    elif isinstance(child.exc.func, ast.Attribute):
                        raised.append(child.exc.func.attr)
        return list(set(raised))

    def _extract_calls(self, node: ast.AST) -> List[str]:
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return list(set(calls))

    def visit_ClassDef(self, node: ast.ClassDef):
        prev_class = self._current_class
        self._current_class = node.name
        
        snippet = self._extract_snippet(node.lineno, getattr(node, "end_lineno", node.lineno + 20))
        docstring = self._extract_docstring(node)
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        
        self.symbols.append(
            ASTSymbol(
                symbol_name=node.name,
                symbol_type="class",
                service=self.service_name,
                file_path=self.file_path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                docstring=docstring,
                raised_exceptions=[],
                calls=bases,
                signature=f"class {node.name}({', '.join(bases)})",
                code_snippet=snippet
            )
        )
        self.generic_visit(node)
        self._current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_function(node, is_async=True)

    def _record_function(self, node, is_async: bool):
        full_name = f"{self._current_class}.{node.name}" if self._current_class else node.name
        snippet = self._extract_snippet(node.lineno, getattr(node, "end_lineno", node.lineno + 15))
        docstring = self._extract_docstring(node)
        raised = self._extract_raises(node)
        calls = self._extract_calls(node)
        
        prefix = "async def " if is_async else "def "
        args_list = [arg.arg for arg in node.args.args]
        sig = f"{prefix}{node.name}({', '.join(args_list)})"

        self.symbols.append(
            ASTSymbol(
                symbol_name=full_name,
                symbol_type="method" if self._current_class else "function",
                service=self.service_name,
                file_path=self.file_path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                docstring=docstring,
                raised_exceptions=raised,
                calls=calls,
                signature=sig,
                code_snippet=snippet
            )
        )
        self.generic_visit(node)


class ASTCodeIndexer:
    """
    Parses repositories into AST units and maintains exact lexical lookup tables.
    """

    def __init__(self):
        self.symbols: List[ASTSymbol] = []
        # Exact symbol map: symbol_name.lower() -> List[ASTSymbol]
        self.symbol_map: Dict[str, List[ASTSymbol]] = {}
        # Exception / error code map: exc_name.lower() -> List[ASTSymbol]
        self.exception_map: Dict[str, List[ASTSymbol]] = {}
        # File path map
        self.file_map: Dict[str, List[ASTSymbol]] = {}

    def index_directory(self, base_dir: str) -> int:
        """Walks directory, parses all .py files, and populates index."""
        indexed_count = 0
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_service = os.path.basename(os.path.dirname(full_path))
                    symbols = self.parse_file(full_path, service_name=rel_service)
                    self.add_symbols(symbols)
                    indexed_count += len(symbols)
        return indexed_count

    def parse_file(self, file_path: str, service_name: str = "unknown") -> List[ASTSymbol]:
        """Parses a single file using Python AST."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines(keepends=True)

            tree = ast.parse(content, filename=file_path)
            visitor = ASTVisitor(file_path=file_path, source_lines=lines, service_name=service_name)
            visitor.visit(tree)
            return visitor.symbols
        except Exception as e:
            # Fallback for syntax variations
            return []

    def add_symbols(self, symbols: List[ASTSymbol]):
        """Adds symbols to the internal registry and inverted index."""
        for sym in symbols:
            self.symbols.append(sym)
            
            # Map exact name and normalized sub-tokens
            name_lower = sym.symbol_name.lower()
            if name_lower not in self.symbol_map:
                self.symbol_map[name_lower] = []
            self.symbol_map[name_lower].append(sym)
            
            # If Class.method, also map raw method
            if "." in name_lower:
                short_name = name_lower.split(".")[-1]
                if short_name not in self.symbol_map:
                    self.symbol_map[short_name] = []
                self.symbol_map[short_name].append(sym)

            # Map exceptions
            for exc in sym.raised_exceptions:
                exc_lower = exc.lower()
                if exc_lower not in self.exception_map:
                    self.exception_map[exc_lower] = []
                self.exception_map[exc_lower].append(sym)

            # Map file basename
            base_file = os.path.basename(sym.file_path).lower()
            if base_file not in self.file_map:
                self.file_map[base_file] = []
            self.file_map[base_file].append(sym)

    def exact_match(self, query: str) -> List[ASTSymbol]:
        """
        Sub-millisecond exact lexical matching on symbol names, raised exceptions, or file refs.
        """
        q = query.strip().lower()
        results: List[ASTSymbol] = []
        seen = set()

        # 1. Direct symbol match
        if q in self.symbol_map:
            for s in self.symbol_map[q]:
                key = (s.file_path, s.line_start)
                if key not in seen:
                    results.append(s)
                    seen.add(key)

        # 2. Direct exception match
        if q in self.exception_map:
            for s in self.exception_map[q]:
                key = (s.file_path, s.line_start)
                if key not in seen:
                    results.append(s)
                    seen.add(key)

        # 3. Stack trace extraction
        # Check if query references filename and function
        for sym in self.symbols:
            key = (sym.file_path, sym.line_start)
            if key in seen:
                continue
            base = os.path.basename(sym.file_path).lower()
            if base in q and (sym.symbol_name.lower() in q or (sym.signature and sym.signature.lower() in q)):
                results.append(sym)
                seen.add(key)

        return results

    def get_all_symbols(self) -> List[ASTSymbol]:
        return self.symbols
