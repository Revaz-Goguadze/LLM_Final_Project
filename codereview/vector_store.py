import os
import pickle
from typing import Any, Dict, List

import numpy as np


class SimpleCollection:
    def __init__(self, name: str, path: str, embedding_function):
        self.name = name
        self.path = path
        self.embedding_function = embedding_function
        self.ids: List[str] = []
        self.documents: List[str] = []
        self.metadatas: List[Dict[str, Any]] = []
        self._embeddings: np.ndarray | None = None
        self._load()

    def _data_path(self) -> str:
        return os.path.join(self.path, f"{self.name}.pkl")

    def _load(self) -> None:
        os.makedirs(self.path, exist_ok=True)
        data_path = self._data_path()
        if not os.path.exists(data_path):
            return
        with open(data_path, "rb") as f:
            payload = pickle.load(f)
        self.ids = payload.get("ids", [])
        self.documents = payload.get("documents", [])
        self.metadatas = payload.get("metadatas", [])
        embeddings = payload.get("embeddings", [])
        if embeddings:
            self._embeddings = np.array(embeddings, dtype=np.float32)

    def _save(self) -> None:
        data_path = self._data_path()
        payload = {
            "ids": self.ids,
            "documents": self.documents,
            "metadatas": self.metadatas,
            "embeddings": self._embeddings.tolist() if self._embeddings is not None else [],
        }
        with open(data_path, "wb") as f:
            pickle.dump(payload, f)

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]]):
        if not ids:
            return
        filtered = [
            (doc_id, doc, meta)
            for doc_id, doc, meta in zip(ids, documents, metadatas)
            if doc and doc.strip()
        ]
        if not filtered:
            return
        ids, documents, metadatas = map(list, zip(*filtered))
        embeddings = self.embedding_function(documents)
        embeddings_arr = np.array(embeddings, dtype=np.float32)
        for idx, doc_id in enumerate(ids):
            if doc_id in self.ids:
                pos = self.ids.index(doc_id)
                self.documents[pos] = documents[idx]
                self.metadatas[pos] = metadatas[idx]
                if self._embeddings is not None:
                    self._embeddings[pos] = embeddings_arr[idx]
            else:
                self.ids.append(doc_id)
                self.documents.append(documents[idx])
                self.metadatas.append(metadatas[idx])
                if self._embeddings is None:
                    self._embeddings = embeddings_arr
                else:
                    self._embeddings = np.vstack([self._embeddings, embeddings_arr[idx]])
        self._save()

    def get(self, include: List[str] | None = None) -> Dict[str, Any]:
        return {
            "ids": self.ids,
            "documents": self.documents,
            "metadatas": self.metadatas,
        }

    def query(self, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        if not self.ids or self._embeddings is None:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        query_embeddings = np.array(self.embedding_function(query_texts), dtype=np.float32)
        # cosine similarity
        doc_norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
        query_norms = np.linalg.norm(query_embeddings, axis=1, keepdims=True)
        doc_normed = self._embeddings / (doc_norms + 1e-12)
        query_normed = query_embeddings / (query_norms + 1e-12)
        scores = query_normed @ doc_normed.T
        results_ids = []
        results_docs = []
        results_metas = []
        results_dists = []
        for row in scores:
            ranked = np.argsort(-row)[:n_results]
            results_ids.append([self.ids[i] for i in ranked])
            results_docs.append([self.documents[i] for i in ranked])
            results_metas.append([self.metadatas[i] for i in ranked])
            results_dists.append([float(1.0 - row[i]) for i in ranked])
        return {
            "ids": results_ids,
            "documents": results_docs,
            "metadatas": results_metas,
            "distances": results_dists,
        }


class SimpleVectorClient:
    def __init__(self, path: str):
        self.path = path
        self._collections: Dict[str, SimpleCollection] = {}

    def get_or_create_collection(self, name: str, embedding_function):
        if name not in self._collections:
            self._collections[name] = SimpleCollection(name, self.path, embedding_function)
        return self._collections[name]

    def get_collection(self, name: str, embedding_function):
        data_path = os.path.join(self.path, f"{name}.pkl")
        if not os.path.exists(data_path):
            raise ValueError(f"Collection {name} does not exist")
        if name not in self._collections:
            self._collections[name] = SimpleCollection(name, self.path, embedding_function)
        return self._collections[name]
