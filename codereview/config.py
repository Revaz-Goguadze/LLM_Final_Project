import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Models
MODEL_GRADER_SECURITY = "google/gemini-2.0-flash-exp:free"
MODEL_GRADER_LOGIC = "meta-llama/llama-3.1-8b-instruct:free"
MODEL_GRADER_PERF = "mistralai/mistral-7b-instruct:free"
MODEL_JUDGE = "google/gemini-2.0-flash-exp:free"

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
