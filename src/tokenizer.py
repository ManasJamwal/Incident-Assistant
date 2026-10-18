"""
Code and Infrastructure-Aware Tokenizer
Specialized in handling stack traces, camelCase/snake_case symbols, error codes, and symptoms.
"""

import re
from typing import List, Set

# Common English and Python stopwords to filter for dense/lexical text
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with",
    "by", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "can", "could", "should", "would",
    "this", "that", "these", "those", "i", "we", "you", "they", "it"
}

# Regex patterns for error codes, stack traces, and identifiers
ERROR_CODE_REGEX = re.compile(r"\b(?:HTTP[_\s]?)?([1-5]\d{2})\b|\b(?:137|OOMKilled|SIGSEGV|SIGKILL|ECONNREFUSED|ETIMEDOUT)\b", re.IGNORECASE)
STACKTRACE_LINE_REGEX = re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+([a-zA-Z0-9_]+)', re.IGNORECASE)
CAMEL_CASE_REGEX = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def split_identifier(identifier: str) -> List[str]:
    """
    Splits programming identifiers written in camelCase or snake_case.
    e.g., 'acquire_db_connection' -> ['acquire', 'db', 'connection', 'acquire_db_connection']
    e.g., 'GatewayTimeoutError' -> ['gateway', 'timeout', 'error', 'gatewaytimeouterror']
    """
    parts = []
    # Replace snake_case underscores
    sub_parts = identifier.replace("-", "_").split("_")
    for sp in sub_parts:
        if not sp:
            continue
        # Split camelCase
        camel_tokens = CAMEL_CASE_REGEX.split(sp)
        for ct in camel_tokens:
            if ct:
                parts.append(ct.lower())
    
    # Also add the normalized unified form
    normalized = re.sub(r"[_\W]+", "", identifier.lower())
    if normalized and normalized not in parts:
        parts.append(normalized)
    
    return parts


def tokenize_code(code_text: str) -> List[str]:
    """
    Tokenizes raw code or code signatures into lexical tokens.
    Preserves symbol names, raises, and identifiers.
    """
    raw_tokens = re.findall(r"[A-Za-z0-9_]+", code_text)
    tokens: List[str] = []
    
    for token in raw_tokens:
        sub_tokens = split_identifier(token)
        tokens.extend(sub_tokens)
        
    return tokens


def tokenize_incident_query(query: str) -> List[str]:
    """
    Tokenizes an incident triage query or search phrase.
    Extracts explicit error codes, stack trace lines, and semantic symptom words.
    """
    tokens: List[str] = []
    
    # 1. Extract error codes (e.g. 502, 137, OOMKilled)
    error_matches = ERROR_CODE_REGEX.findall(query)
    for em in error_matches:
        if isinstance(em, tuple):
            for item in em:
                if item:
                    tokens.append(item.lower())
        elif em:
            tokens.append(em.lower())

    # 2. Extract stack trace frames
    st_matches = STACKTRACE_LINE_REGEX.findall(query)
    for file_match, line_match, func_match in st_matches:
        tokens.append(file_match.lower())
        tokens.append(f"line_{line_match}")
        tokens.extend(split_identifier(func_match))

    # 3. General word and symbol extraction
    words = re.findall(r"[A-Za-z0-9_\-\.]+", query)
    for word in words:
        clean = word.lower()
        if clean in STOPWORDS:
            continue
        tokens.extend(split_identifier(clean))

    return tokens


def tokenize_doc_text(text: str) -> List[str]:
    """
    General document tokenizer for markdown runbooks and post-mortems.
    """
    words = re.findall(r"[A-Za-z0-9_]+", text)
    tokens = []
    for w in words:
        lw = w.lower()
        if lw not in STOPWORDS and len(lw) > 1:
            tokens.append(lw)
            sub = split_identifier(w)
            for s in sub:
                if s not in tokens and s not in STOPWORDS:
                    tokens.append(s)
    return tokens
