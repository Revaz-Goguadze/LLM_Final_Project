import os
import chromadb
from .chunker import ASTChunker
from .config import CHROMA_DB_PATH, VECTOR_DB_COLLECTION, BM25_INDEX_PATH
from .bm25_index import BM25Index
from .embeddings import get_embedding_function, collection_name, bm25_path
from typing import List

class CodebaseIndexer:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        
        self.emb_fn = get_embedding_function()
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name(VECTOR_DB_COLLECTION),
            embedding_function=self.emb_fn
        )
        self.chunker = ASTChunker()

    def index_directory(self, directory: str, build_bm25: bool = True):
        """Indexes all supported files in a directory."""
        for root, dirs, files in os.walk(directory):
            # Skip hidden dirs and common exclusions
            if any(part.startswith('.') for part in root.split(os.sep)):
                continue
            if 'venv' in root or '__pycache__' in root or 'node_modules' in root:
                continue
                
            for file in files:
                if file.endswith((".py", ".js", ".jsx", ".ts", ".tsx")):
                    file_path = os.path.join(root, file)
                    self.index_file(file_path)
        if build_bm25:
            bm25 = BM25Index(path=bm25_path(BM25_INDEX_PATH))
            bm25.build_from_collection(self.collection)
            bm25.save()

    def index_file(self, file_path: str):
        """Chunks and indexes a single file."""
        chunks = self.chunker.chunk_file(file_path)
        if not chunks:
            return

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{chunk.file_path}:{chunk.name}:{i}"
            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append({
                "file_path": chunk.file_path,
                "name": chunk.name,
                "type": chunk.type,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line
            })

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        print(f"Indexed {len(chunks)} chunks from {file_path}")

if __name__ == "__main__":
    indexer = CodebaseIndexer()
    # Index the codereview package itself as a test
    indexer.index_directory("codereview")
