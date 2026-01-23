import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# Models - LLMs
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_LLM_MODEL = GEMINI_MODEL if LLM_PROVIDER == "gemini" else "gpt-4o-mini"
MODEL_GRADER_SECURITY = os.getenv("MODEL_GRADER_SECURITY", DEFAULT_LLM_MODEL)
MODEL_GRADER_LOGIC = os.getenv("MODEL_GRADER_LOGIC", DEFAULT_LLM_MODEL)
MODEL_GRADER_PERF = os.getenv("MODEL_GRADER_PERF", DEFAULT_LLM_MODEL)
MODEL_JUDGE = os.getenv("MODEL_JUDGE", DEFAULT_LLM_MODEL)
MODEL_HYDE = os.getenv("MODEL_HYDE", DEFAULT_LLM_MODEL)

# Model diversity options (fallback lists for each role)
MODEL_GRADER_SECURITY_OPTIONS = [
    MODEL_GRADER_SECURITY,
    MODEL_GRADER_SECURITY,
    MODEL_GRADER_SECURITY,
]

MODEL_GRADER_LOGIC_OPTIONS = [
    MODEL_GRADER_LOGIC,
    MODEL_GRADER_LOGIC,
    MODEL_GRADER_LOGIC,
]

MODEL_GRADER_PERF_OPTIONS = [
    MODEL_GRADER_PERF,
    MODEL_GRADER_PERF,
    MODEL_GRADER_PERF,
]

MODEL_JUDGE_OPTIONS = [
    MODEL_JUDGE,
    MODEL_JUDGE,
]

# Deduplication settings
ENABLE_DEDUPLICATION = os.getenv("ENABLE_DEDUPLICATION", "true").lower() in ("1", "true", "yes")
DEDUPLICATION_LINE_THRESHOLD = int(os.getenv("DEDUPLICATION_LINE_THRESHOLD", "3"))

# Storage
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", os.path.join(os.getcwd(), ".vector_store"))
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
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "openai")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))
LLM_MIN_DELAY = float(os.getenv("LLM_MIN_DELAY", "1.2"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
ALLOW_FIX_PATCH = os.getenv("ALLOW_FIX_PATCH", "false").lower() in ("1", "true", "yes")
DEMO_EXCLUDE_PREFIXES = [
    prefix.strip()
    for prefix in os.getenv("DEMO_EXCLUDE_PREFIXES", "").split(",")
    if prefix.strip()
]


def missing_api_keys() -> list[str]:
    missing = []
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
    else:
        if not OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
    return missing


def require_llm_key() -> None:
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required for Gemini requests.")
    else:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI requests.")
