import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Models
if OPENROUTER_API_KEY:
    DEFAULT_MODEL_GRADER_SECURITY = "google/gemini-2.0-flash-exp:free"
    DEFAULT_MODEL_GRADER_LOGIC = "meta-llama/llama-3.1-8b-instruct:free"
    DEFAULT_MODEL_GRADER_PERF = "mistralai/mistral-7b-instruct:free"
    DEFAULT_MODEL_JUDGE = "google/gemini-2.0-flash-exp:free"
else:
    DEFAULT_MODEL_GRADER_SECURITY = "gpt-4o-mini"
    DEFAULT_MODEL_GRADER_LOGIC = "gpt-4o-mini"
    DEFAULT_MODEL_GRADER_PERF = "gpt-4o-mini"
    DEFAULT_MODEL_JUDGE = "gpt-4o-mini"

MODEL_GRADER_SECURITY = os.getenv("MODEL_GRADER_SECURITY", DEFAULT_MODEL_GRADER_SECURITY)
MODEL_GRADER_LOGIC = os.getenv("MODEL_GRADER_LOGIC", DEFAULT_MODEL_GRADER_LOGIC)
MODEL_GRADER_PERF = os.getenv("MODEL_GRADER_PERF", DEFAULT_MODEL_GRADER_PERF)
MODEL_JUDGE = os.getenv("MODEL_JUDGE", DEFAULT_MODEL_JUDGE)

# Storage
CHROMA_DB_PATH = os.path.join(os.getcwd(), ".chroma")
VECTOR_DB_COLLECTION = "codebase"
BM25_INDEX_PATH = os.path.join(os.getcwd(), ".bm25", "index.pkl")
DOCS_DB_COLLECTION = "docs"
DOCS_BM25_INDEX_PATH = os.path.join(os.getcwd(), ".bm25", "docs_index.pkl")

# Settings
MAX_FIX_RETRIES = 3
CONTEXT_WINDOW_REDUCTION_SUMMARY = True
VERIFY_COMMAND = os.getenv("VERIFY_COMMAND", "pytest")

# Retrieval
SEMANTIC_TOP_K = 8
BM25_TOP_K = 8
HYBRID_ALPHA = 0.6
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "default")
