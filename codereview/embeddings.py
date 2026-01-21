import hashlib
import math
import re
from typing import List

from openai import OpenAI

from .config import EMBEDDING_MODE, OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, OPENROUTER_TIMEOUT


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


class OpenAIEmbeddingFunction:
    def __init__(self, model: str = OPENAI_EMBEDDING_MODEL):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings.")
        self.client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENROUTER_TIMEOUT, max_retries=2)
        self.model = model

    def __call__(self, input: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(model=self.model, input=input)
        return [item.embedding for item in response.data]

    def name(self) -> str:
        return "openai"


def get_embedding_function():
    if EMBEDDING_MODE == "local":
        return LocalHashEmbeddingFunction()
    if EMBEDDING_MODE == "openai":
        return OpenAIEmbeddingFunction()
    raise ValueError(f"Unsupported EMBEDDING_MODE: {EMBEDDING_MODE}")


def collection_name(base: str) -> str:
    if EMBEDDING_MODE == "local":
        return f"{base}_local"
    if EMBEDDING_MODE == "openai":
        return f"{base}_openai"
    return base


def bm25_path(base_path: str) -> str:
    if EMBEDDING_MODE == "local":
        if base_path.endswith(".pkl"):
            return base_path.replace(".pkl", "_local.pkl")
        return f"{base_path}_local"
    if EMBEDDING_MODE == "openai":
        if base_path.endswith(".pkl"):
            return base_path.replace(".pkl", "_openai.pkl")
        return f"{base_path}_openai"
    return base_path
