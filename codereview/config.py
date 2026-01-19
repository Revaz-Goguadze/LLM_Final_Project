import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Models - Gemini via OpenRouter (free tier)
MODEL_GRADER_SECURITY = "mistralai/devstral-2512:free"
MODEL_GRADER_LOGIC = "mistralai/devstral-2512:free"
MODEL_GRADER_PERF = "mistralai/devstral-2512:free"
MODEL_JUDGE = "mistralai/devstral-2512:free"

# Storage
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", os.path.join(os.getcwd(), ".chroma"))
VECTOR_DB_COLLECTION = "codebase"
DOCS_DB_COLLECTION = "docs"
BM25_INDEX_PATH = os.path.join(os.getcwd(), ".bm25", "index.pkl")
DOCS_BM25_INDEX_PATH = os.path.join(os.getcwd(), ".bm25", "docs_index.pkl")

# Retrieval settings
SEMANTIC_TOP_K = 8
BM25_TOP_K = 8
HYBRID_ALPHA = 0.6

# Settings
MAX_FIX_RETRIES = 3
CONTEXT_WINDOW_REDUCTION_SUMMARY = True
VERIFY_COMMAND = os.getenv("VERIFY_COMMAND", "pytest")
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "default")


def missing_api_keys() -> list[str]:
    missing = []
    if not OPENROUTER_API_KEY:
        missing.append("OPENROUTER_API_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    return missing


def require_openrouter_key() -> None:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter requests.")
