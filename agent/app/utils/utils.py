import hashlib
from typing import Any
import json


def hash_text(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def truncate_text(text: str, max_length: int = 1000) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)
    except Exception:
        return str(obj)
