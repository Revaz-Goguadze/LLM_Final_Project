import os
from typing import List, Dict, Any

import chromadb

from .config import CHROMA_DB_PATH, DOCS_DB_COLLECTION, DOCS_BM25_INDEX_PATH
from .bm25_index import BM25Index
from .embeddings import get_embedding_function, collection_name, bm25_path


def _split_by_heading(text: str) -> List[str]:
    lines = text.splitlines()
    chunks: List[str] = []
    current: List[str] = []
    for line in lines:
        if line.startswith("#") and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    return [c for c in chunks if c]


class DocsIndexer:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.emb_fn = get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=collection_name(DOCS_DB_COLLECTION),
            embedding_function=self.emb_fn
        )

    def index_directory(self, directory: str, build_bm25: bool = True) -> None:
        for root, dirs, files in os.walk(directory):
            if any(part.startswith(".") for part in root.split(os.sep)):
                continue
            for file in files:
                if file.endswith(".md") or file.endswith(".txt"):
                    self.index_file(os.path.join(root, file))
        if build_bm25:
            bm25 = BM25Index(path=bm25_path(DOCS_BM25_INDEX_PATH))
            bm25.build_from_collection(self.collection)
            bm25.save()

    def index_file(self, file_path: str) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        chunks = _split_by_heading(content)
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{file_path}:section:{idx}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    "file_path": file_path,
                    "name": f"section_{idx}",
                    "type": "doc",
                    "start_line": None,
                    "end_line": None,
                }
            )

        if ids:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
