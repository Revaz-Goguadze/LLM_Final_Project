from openai import OpenAI
from .bm25_index import BM25Index
from .config import (
    VECTOR_DB_COLLECTION,
    SEMANTIC_TOP_K,
    BM25_TOP_K,
    HYBRID_ALPHA,
    BM25_INDEX_PATH,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    LLM_PROVIDER,
    GEMINI_MODEL,
    OPENAI_TIMEOUT,
    MODEL_HYDE,
    LLM_MIN_DELAY,
)
from .llm_utils import RateLimiter, backoff_sleep
from .gemini_client import GeminiClient
from .embeddings import get_embedding_function, collection_name, bm25_path
from .chroma_client import get_chroma_client


class HyDEGenerator:
    def __init__(self):
        self.provider = LLM_PROVIDER
        self.rate_limiter = RateLimiter(LLM_MIN_DELAY)
        if self.provider == "gemini":
            if not GEMINI_API_KEY:
                self.client = None
                self.model = None
            else:
                self.client = GeminiClient(
                    api_key=GEMINI_API_KEY,
                    model=GEMINI_MODEL,
                    min_delay=LLM_MIN_DELAY,
                    max_retries=3,
                )
                self.model = GEMINI_MODEL
        else:
            if not OPENAI_API_KEY:
                self.client = None
                self.model = None
            else:
                self.client = OpenAI(
                    api_key=OPENAI_API_KEY,
                    timeout=OPENAI_TIMEOUT,
                )
                self.model = MODEL_HYDE

    def generate_hypothetical_doc(self, query: str) -> str:
        prompt = f"""Given this code review query, generate a hypothetical code snippet that would be relevant.
Query: {query}

Generate a short Python code example (10-20 lines) that would answer this query.
Only output the code, no explanations."""

        if not self.client or not self.model:
            return query

        for attempt in range(3):
            try:
                self.rate_limiter.wait()
                if self.provider == "gemini":
                    return self.client.generate(prompt) or query
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    timeout=OPENAI_TIMEOUT,
                )
                if response.choices and response.choices[0].message:
                    return response.choices[0].message.content or query
                return query
            except Exception:
                backoff_sleep(attempt)
                continue
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
        self.hyde = HyDEGenerator()

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

    @staticmethod
    def _rrf(ranked_lists, k: int = 60):
        """Reciprocal Rank Fusion: combine multiple ranked lists.

        Args:
            ranked_lists: List of lists, where each inner list contains (doc_id, rank) tuples
            k: Constant to prevent high ranks from dominating (default 60)

        Returns:
            Dict mapping doc_id to RRF score
        """
        scores = {}
        for ranked_list in ranked_lists:
            for rank, (doc_id, _) in enumerate(ranked_list, start=1):
                if doc_id not in scores:
                    scores[doc_id] = 0.0
                scores[doc_id] += 1.0 / (k + rank)
        return scores

    def search(self, query: str, n_results: int = 5):
        # Get ranked results from BM25 and semantic search
        semantic = self._semantic_search(query, SEMANTIC_TOP_K)
        bm25 = self.bm25.search(query, BM25_TOP_K)

        hyde_semantic = []
        if self.hyde:
            hyde_doc = self.hyde.generate_hypothetical_doc(query)
            hyde_semantic = self._semantic_search(hyde_doc, SEMANTIC_TOP_K)

        # Combine semantic + HyDE (keep best score for each doc)
        semantic_scores = {}
        for item in semantic + hyde_semantic:
            distance = item.get("distance", 0.0)
            sim = 1.0 / (1.0 + float(distance))
            doc_id = item["id"]
            semantic_scores[doc_id] = max(sim, semantic_scores.get(doc_id, 0.0))

        # Build ranked lists for RRF
        # Format: [(doc_id, score), ...] sorted by score descending
        semantic_ranked = sorted(
            semantic_scores.items(), key=lambda x: x[1], reverse=True
        )
        bm25_ranked = sorted(
            [(item["id"], float(item["score"])) for item in bm25],
            key=lambda x: x[1], reverse=True
        )

        # Apply RRF fusion
        rrf_scores = self._rrf([semantic_ranked, bm25_ranked])

        # Build merged payload with RRF scores
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

        # Apply RRF scores and sort
        combined = []
        for doc_id, payload in merged.items():
            payload["score"] = rrf_scores.get(doc_id, 0.0)
            combined.append(payload)

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:n_results]


if __name__ == "__main__":
    retriever = HybridRetriever()
    res = retriever.search("How is the git analyzer implemented?")
    for r in res:
        print(f"Found in {r['metadata']['file_path']} ({r['metadata']['name']}):")
        print(f"Content: {r['content'][:100]}...")
