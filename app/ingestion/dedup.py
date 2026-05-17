"""Normalized raw hashing for duplicate detection.

The digest is derived from normalized text only (case and whitespace folding). Application
dedup keys rows by ``(source, normalized_raw_hash)`` so the same text under different sources
is kept distinct.
"""

import hashlib
import re

_WS_RE = re.compile(r"\s+")


def normalize_raw_for_dedup(raw_stripped: str) -> str:
    """Trim (caller strips outer raw), lowercase, collapse internal whitespace."""
    lowered = raw_stripped.lower()
    collapsed = _WS_RE.sub(" ", lowered).strip()
    return collapsed


def normalized_raw_sha256_hex(raw_stripped: str) -> str:
    normalized = normalize_raw_for_dedup(raw_stripped)
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return digest.hex()
