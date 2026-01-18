import hashlib
import math
import re
from typing import List

from chromadb.utils import embedding_functions

from .config import EMBEDDING_MODE


class LocalHashEmbeddingFunction:
    def __init__(self, dim: int = 256):
        self.dim = dim

    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        for text in input:
            vec = [0.0] * self.dim
            tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+", text)
            for tok in tokens:
                h = hashlib.sha256(tok.encode("utf-8")).hexdigest()
                idx = int(h[:8], 16) % self.dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vec = [v / norm for v in vec]
            embeddings.append(vec)
        return embeddings

    def name(self) -> str:
        return "local_hash"


def get_embedding_function():
    if EMBEDDING_MODE == "local":
        return LocalHashEmbeddingFunction()
    return embedding_functions.DefaultEmbeddingFunction()


def collection_name(base: str) -> str:
    if EMBEDDING_MODE == "local":
        return f"{base}_local"
    return base


def bm25_path(base_path: str) -> str:
    if EMBEDDING_MODE == "local":
        if base_path.endswith(".pkl"):
            return base_path.replace(".pkl", "_local.pkl")
        return f"{base_path}_local"
    return base_path
