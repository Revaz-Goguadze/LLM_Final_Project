from openai import OpenAI
from .bm25_index import BM25Index
from .config import (
    VECTOR_DB_COLLECTION,
    SEMANTIC_TOP_K,
    BM25_TOP_K,
    HYBRID_ALPHA,
    BM25_INDEX_PATH,
    OPENROUTER_API_KEY,
)
from .embeddings import get_embedding_function, collection_name, bm25_path
from .chroma_client import get_chroma_client


class HyDEGenerator:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        self.model = "mistralai/devstral-2512:free"

    def generate_hypothetical_doc(self, query: str) -> str:
        prompt = f"""Given this code review query, generate a hypothetical code snippet that would be relevant.
Query: {query}

Generate a short Python code example (10-20 lines) that would answer this query.
Only output the code, no explanations."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or query
            return query
        except Exception:
            return query


class HybridRetriever:
    def __init__(
        self,
        collection: str = VECTOR_DB_COLLECTION,
        bm25_index_path: str = BM25_INDEX_PATH,
    ):
        self.client = get_chroma_client()
        self.emb_fn = get_embedding_function()
        self.collection = self.client.get_collection(
            name=collection_name(collection),
            embedding_function=self.emb_fn,
        )
        self.bm25 = BM25Index(path=bm25_path(bm25_index_path))
        self.bm25.load_or_build(self.collection)
        self.hyde = HyDEGenerator() if OPENROUTER_API_KEY else None

    def _semantic_search(self, query: str, n_results: int):
        try:
            results = self.collection.query(query_texts=[query], n_results=n_results)
        except Exception:
            return []

        if not results.get("ids") or not results["ids"] or not results["ids"][0]:
            return []

        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append(
                {
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                }
            )
        return formatted

    @staticmethod
    def _normalize(scores):
        if not scores:
            return {}
        vals = list(scores.values())
        vmin = min(vals)
        vmax = max(vals)
        if vmax == vmin:
            return {k: 1.0 for k in scores}
        return {k: (v - vmin) / (vmax - vmin) for k, v in scores.items()}

    def search(self, query: str, n_results: int = 5):
        semantic = self._semantic_search(query, SEMANTIC_TOP_K)
        bm25 = self.bm25.search(query, BM25_TOP_K)

        hyde_semantic = []
        if self.hyde:
            hyde_doc = self.hyde.generate_hypothetical_doc(query)
            hyde_semantic = self._semantic_search(hyde_doc, SEMANTIC_TOP_K)

        semantic_scores = {}
        for item in semantic + hyde_semantic:
            distance = item.get("distance", 0.0)
            sim = 1.0 / (1.0 + float(distance))
            semantic_scores[item["id"]] = max(sim, semantic_scores.get(item["id"], 0.0))

        bm25_scores = {item["id"]: float(item["score"]) for item in bm25}

        semantic_norm = self._normalize(semantic_scores)
        bm25_norm = self._normalize(bm25_scores)

        merged = {}
        for item in semantic + hyde_semantic:
            merged[item["id"]] = {
                "id": item["id"],
                "content": item["content"],
                "metadata": item["metadata"],
                "distance": item.get("distance"),
            }
        for item in bm25:
            if item["id"] not in merged:
                merged[item["id"]] = {
                    "id": item["id"],
                    "content": item["content"],
                    "metadata": item["metadata"],
                    "distance": None,
                }

        combined = []
        for doc_id, payload in merged.items():
            score = (HYBRID_ALPHA * semantic_norm.get(doc_id, 0.0)) + (
                (1.0 - HYBRID_ALPHA) * bm25_norm.get(doc_id, 0.0)
            )
            payload["score"] = score
            combined.append(payload)

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:n_results]


if __name__ == "__main__":
    retriever = HybridRetriever()
    res = retriever.search("How is the git analyzer implemented?")
    for r in res:
        print(f"Found in {r['metadata']['file_path']} ({r['metadata']['name']}):")
        print(f"Content: {r['content'][:100]}...")
