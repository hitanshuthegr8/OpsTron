"""
Security and cost-control helpers for inbound logs.
"""

import hashlib
import re
from typing import Iterable


SECRET_PATTERNS = (
    (re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*([^\s,'\"]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|client[_-]?secret)\s*[:=]\s*([^\s,'\"]+)"), r"\1=[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)\b(Basic|Bearer)\s+[A-Za-z0-9._~+/=-]{16,}\b"), r"\1 [REDACTED]"),
    (re.compile(r"(?i)(postgres|postgresql|mysql|mongodb|redis)://[^\s]+"), r"\1://[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
)


def redact_text(text: str) -> str:
    redacted = text or ""
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text

    head_size = max_chars // 2
    tail_size = max_chars - head_size
    omitted = len(text) - max_chars
    return (
        text[:head_size]
        + f"\n...[truncated {omitted} characters for safety and cost control]...\n"
        + text[-tail_size:]
    )


def normalize_for_fingerprint(parts: Iterable[str]) -> str:
    text = "\n".join(part for part in parts if part).lower()
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "<sha>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "<uuid>", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}[t\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?z?\b", "<timestamp>", text)
    text = re.sub(r"\b\d+\b", "<num>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:4000]


def incident_fingerprint(*parts: str) -> str:
    normalized = normalize_for_fingerprint(parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
