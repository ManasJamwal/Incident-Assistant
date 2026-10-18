"""
Dense Vector Documentation Indexer
Indexes architectural docs, runbooks, and post-mortems using dense semantic vector representations.
"""

import os
import re
from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from .models import TextDocument, ASTSymbol


class DenseDocIndexer:
    """
    Manages vectorization and similarity search over architectural documentation,
    runbooks, and past incident post-mortems.
    """

    def __init__(self, vector_dim: int = 48):
        self.vector_dim = vector_dim
        self.documents: List[TextDocument] = []
        self.doc_map: Dict[str, TextDocument] = {}
        
        # Vector models
        self.tfidf = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            sublinear_tf=True
        )
        self.svd: Optional[TruncatedSVD] = None
        self.doc_vectors: Optional[np.ndarray] = None
        self.is_fitted = False

    def index_directory(self, runbooks_dir: str, post_mortems_dir: str) -> int:
        """Loads and indexes runbooks and post-mortems."""
        count = 0
        
        # Load Runbooks
        if os.path.exists(runbooks_dir):
            for file in os.listdir(runbooks_dir):
                if file.endswith(".md"):
                    path = os.path.join(runbooks_dir, file)
                    doc = self._parse_markdown_file(path, doc_type="runbook")
                    if doc:
                        self.documents.append(doc)
                        self.doc_map[doc.doc_id] = doc
                        count += 1

        # Load Post-Mortems
        if os.path.exists(post_mortems_dir):
            for file in os.listdir(post_mortems_dir):
                if file.endswith(".md"):
                    path = os.path.join(post_mortems_dir, file)
                    doc = self._parse_markdown_file(path, doc_type="post_mortem")
                    if doc:
                        self.documents.append(doc)
                        self.doc_map[doc.doc_id] = doc
                        count += 1

        self.fit_vectors()
        return count

    def _parse_markdown_file(self, file_path: str, doc_type: str) -> Optional[TextDocument]:
        """Parses markdown front-matter, title, severity, and remediation."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            filename = os.path.basename(file_path)
            doc_id = filename.replace(".md", "")
            
            # Extract title
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else doc_id

            # Extract severity
            sev_match = re.search(r"\*\*Severity\*\*:\s*([A-Za-z0-9\s/]+)", content)
            severity = sev_match.group(1).strip() if sev_match else "P1"

            # Extract remediation steps (e.g. bash commands or bullet lists)
            remediation = []
            code_blocks = re.findall(r"```(?:bash|sh|sql)?\n(.*?)```", content, re.DOTALL)
            for block in code_blocks:
                cmds = [line.strip() for line in block.splitlines() if line.strip() and not line.startswith("#")]
                remediation.extend(cmds)

            return TextDocument(
                doc_id=doc_id,
                title=title,
                doc_type=doc_type,
                file_path=file_path,
                severity=severity,
                content=content,
                remediation_steps=remediation
            )
        except Exception:
            return None

    def fit_vectors(self):
        """Builds dense semantic projection matrix."""
        if not self.documents:
            return

        corpus = [f"{d.title} {d.content}" for d in self.documents]
        tfidf_mat = self.tfidf.fit_transform(corpus)
        
        n_components = min(self.vector_dim, max(2, tfidf_mat.shape[0] - 1), tfidf_mat.shape[1] - 1)
        if n_components > 1:
            self.svd = TruncatedSVD(n_components=n_components, random_state=42)
            dense_mat = self.svd.fit_transform(tfidf_mat)
        else:
            dense_mat = tfidf_mat.toarray()

        # Normalize vectors for cosine similarity
        norms = np.linalg.norm(dense_mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.doc_vectors = dense_mat / norms
        self.is_fitted = True

    def query_dense(self, query: str, top_k: int = 5) -> List[Tuple[TextDocument, float]]:
        """Computes cosine similarity of dense query vector against documents."""
        if not self.is_fitted or self.doc_vectors is None or len(self.documents) == 0:
            return []

        try:
            q_tfidf = self.tfidf.transform([query])
            if self.svd is not None:
                q_dense = self.svd.transform(q_tfidf)
            else:
                q_dense = q_tfidf.toarray()

            q_norm = np.linalg.norm(q_dense)
            if q_norm > 0:
                q_dense = q_dense / q_norm

            sims = np.dot(self.doc_vectors, q_dense.T).flatten()
            ranked_indices = np.argsort(sims)[::-1][:top_k]

            results = []
            for idx in ranked_indices:
                score = float(sims[idx])
                if score > 0.01:
                    results.append((self.documents[idx], score))
            return results
        except Exception:
            return []
