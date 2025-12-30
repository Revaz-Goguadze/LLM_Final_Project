import chromadb
from .config import CHROMA_DB_PATH, VECTOR_DB_COLLECTION
from chromadb.utils import embedding_functions

class HybridRetriever:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.emb_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_collection(
            name=VECTOR_DB_COLLECTION,
            embedding_function=self.emb_fn
        )

    def search(self, query: str, n_results: int = 5):
        """Basic semantic search. TODO: Add BM25 hybrid ranking."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Format results
        formatted = []
        for i in range(len(results['ids'][0])):
            formatted.append({
                "id": results['ids'][0][i],
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i]
            })
        return formatted

if __name__ == "__main__":
    retriever = HybridRetriever()
    res = retriever.search("How is the git analyzer implemented?")
    for r in res:
        print(f"Found in {r['metadata']['file_path']} ({r['metadata']['name']}):")
        print(f"Content: {r['content'][:100]}...")
