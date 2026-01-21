from .config import VECTOR_STORE_PATH
from .vector_store import SimpleVectorClient

_CLIENT = None


def get_chroma_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = SimpleVectorClient(VECTOR_STORE_PATH)
    return _CLIENT
