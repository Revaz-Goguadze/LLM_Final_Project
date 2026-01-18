import os
import pickle
import re
from typing import Dict, List, Any, Tuple

from rank_bm25 import BM25Okapi

from .config import BM25_INDEX_PATH


def _split_camel(token: str) -> List[str]:
    parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", token).split()
    return parts if parts else [token]


def _tokenize(text: str) -> List[str]:
    raw = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+", text)
    tokens: List[str] = []
    for tok in raw:
        for part in _split_camel(tok):
            tokens.append(part.lower())
    return tokens


class BM25Index:
    def __init__(self, path: str = BM25_INDEX_PATH):
        self.path = path
        self.bm25: BM25Okapi | None = None
        self.ids: List[str] = []
        self.documents: List[str] = []
        self.metadatas: List[Dict[str, Any]] = []

    def build_from_collection(self, collection) -> None:
        data = collection.get(include=["documents", "metadatas"])
        self.ids = data["ids"]
        self.documents = data["documents"]
        self.metadatas = data["metadatas"]

        tokenized = [_tokenize(doc) for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "ids": self.ids,
            "documents": self.documents,
            "metadatas": self.metadatas,
        }
        with open(self.path, "wb") as f:
            pickle.dump(payload, f)

    def load(self) -> bool:
        if not os.path.exists(self.path):
            return False
        with open(self.path, "rb") as f:
            payload = pickle.load(f)
        self.ids = payload.get("ids", [])
        self.documents = payload.get("documents", [])
        self.metadatas = payload.get("metadatas", [])
        tokenized = [_tokenize(doc) for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized)
        return True

    def load_or_build(self, collection) -> None:
        if not self.load():
            self.build_from_collection(collection)
            self.save()

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.bm25:
            return []
        query_tokens = _tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for idx, score in ranked:
            results.append(
                {
                    "id": self.ids[idx],
                    "content": self.documents[idx],
                    "metadata": self.metadatas[idx],
                    "score": float(score),
                }
            )
        return results
