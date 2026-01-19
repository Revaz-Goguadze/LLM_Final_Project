from typing import List, Optional


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    if not text or max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def split_words(text: str) -> List[str]:
    if not text:
        return []
    return [word.strip() for word in text.split() if word.strip()]


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split())
