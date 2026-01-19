from typing import Optional
import re

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_PATTERN.match(email.strip()))


def validate_age(age: Optional[int]) -> bool:
    if age is None or not isinstance(age, int):
        return False
    return 0 <= age <= 150
