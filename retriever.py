"""
Pure standard-library TF-IDF retriever over the chunk corpus — no
scikit-learn, no embedding API calls, no vector DB, no pip installs at all.

Chosen for this prototype because the corpus is tiny (~40 chunks): plain
TF-IDF needs no model download and no network call, so the whole project
runs with zero external dependencies. See README "Trade-offs" for when this
would need to change (a larger/growing corpus, or queries that are
paraphrases with little keyword overlap with the source text).
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "to", "of",
    "and", "or", "in", "on", "for", "with", "this", "that", "it", "as",
    "at", "by", "from", "your", "you", "i", "my", "can", "will", "if",
    "do", "does", "not", "but", "so", "how", "what", "when",
}


def tokenize(text: str):
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class Retriever:
    def __init__(self, chunks_path: Path = DATA_DIR / "chunks.json"):
        self.chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        self.doc_tokens = [tokenize(f"{c['title']} {c['text']}") for c in self.chunks]

        doc_freq = Counter()
        for tokens in self.doc_tokens:
            for term in set(tokens):
                doc_freq[term] += 1

        n_docs = len(self.doc_tokens)
        self.idf = {term: math.log(n_docs / (1 + df)) + 1.0 for term, df in doc_freq.items()}

        self.doc_vectors = [self._vectorize(tokens) for tokens in self.doc_tokens]
        self.doc_norms = [self._norm(v) for v in self.doc_vectors]

    def _vectorize(self, tokens):
        counts = Counter(tokens)
        total = len(tokens) or 1
        return {term: (count / total) * self.idf.get(term, 0.0) for term, count in counts.items()}

    @staticmethod
    def _norm(vector):
        return math.sqrt(sum(w * w for w in vector.values())) or 1e-9

    @staticmethod
    def _cosine(query_vec, query_norm, doc_vec, doc_norm):
        shared = set(query_vec) & set(doc_vec)
        dot = sum(query_vec[t] * doc_vec[t] for t in shared)
        return dot / (query_norm * doc_norm)

    def search(self, query: str, top_k: int = 3):
        query_vec = self._vectorize(tokenize(query))
        query_norm = self._norm(query_vec)

        scored = []
        for i, (doc_vec, doc_norm) in enumerate(zip(self.doc_vectors, self.doc_norms)):
            score = self._cosine(query_vec, query_norm, doc_vec, doc_norm)
            scored.append((score, i))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        return [{"chunk": self.chunks[i], "score": float(score)} for score, i in scored[:top_k]]
