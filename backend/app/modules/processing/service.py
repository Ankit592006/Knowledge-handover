"""Secret Scanning, Prompt-Injection Sanitization, Document Parsing, Chunking & Embeddings (Modules 4, 5, 6)."""

import hashlib
import math
import re
from typing import Any, Dict, List, Tuple

from app.core.config import get_settings

settings = get_settings()

# High-confidence regex patterns for credential / secret scanning and redaction
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("STRIPE_OR_API_KEY", re.compile(r"\b(?:sk_live|sk_test|pk_live|rk_live|api_key|apikey)[_a-zA-Z0-9-]{8,}\b", re.IGNORECASE)),
    ("GITHUB_PAT", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{16,}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("BEARER_OR_JWT", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("GENERIC_PASSWORD_ASSIGNMENT", re.compile(r"(?:password|passwd|secret|client_secret|webhook_secret)\s*[:=]\s*['\"]?([A-Za-z0-9!@#$%^&*_-]{8,})['\"]?", re.IGNORECASE)),
]


def scan_and_redact_secrets(raw_text: str) -> Tuple[str, int]:
    """Scan document content for credentials/secrets and replace them with [REDACTED_SECRET] before storage or LLM exposure."""
    redacted_text = raw_text
    total_redactions = 0

    for label, pattern in SECRET_PATTERNS:
        if label == "GENERIC_PASSWORD_ASSIGNMENT":
            def _replace_kv(match: re.Match) -> str:
                nonlocal total_redactions
                total_redactions += 1
                full = match.group(0)
                secret_val = match.group(1)
                return full.replace(secret_val, "[REDACTED_SECRET]")

            redacted_text = pattern.sub(_replace_kv, redacted_text)
        else:
            matches = list(pattern.finditer(redacted_text))
            if matches:
                total_redactions += len(matches)
                redacted_text = pattern.sub("[REDACTED_SECRET]", redacted_text)

    return redacted_text, total_redactions


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def split_document_into_chunks(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> List[Dict[str, Any]]:
    """Split text into bounded passages while preserving exact character offsets and estimated page numbers."""
    cleaned = text.replace("\r\n", "\n")
    length = len(cleaned)
    if length == 0:
        return []

    chunks: List[Dict[str, Any]] = []
    start = 0
    chunk_index = 0
    chars_per_page = 2400

    while start < length:
        end = min(start + chunk_size, length)
        # Prefer breaking on a newline or sentence boundary if not at the end of document
        if end < length:
            newline_pos = cleaned.rfind("\n", start + int(chunk_size * 0.5), end)
            if newline_pos != -1:
                end = newline_pos + 1
            else:
                space_pos = cleaned.rfind(" ", start + int(chunk_size * 0.6), end)
                if space_pos != -1:
                    end = space_pos + 1

        passage = cleaned[start:end].strip()
        if passage:
            page_num = (start // chars_per_page) + 1
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "content": passage,
                    "char_start": start,
                    "char_end": end,
                    "page_number": page_num,
                    "location_label": f"body#chars:{start}-{end}",
                }
            )
            chunk_index += 1

        if end >= length:
            break
        start = max(start + 1, end - chunk_overlap)

    return chunks


def generate_embedding_vector(text: str, dimension: int = 384) -> List[float]:
    """Generate a normalized 384-dim lexical MD5 feature-hash vector (Weinberger et al., non-semantic token projection)."""
    vec = [0.0] * dimension
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    if not tokens:
        vec[0] = 1.0
        return vec

    # Unigrams and bigrams hashed into signed random projections (feature hashing / Weinberger et al.)
    features = list(tokens) + [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
    for token in features:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dimension
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        weight = 1.5 if "_" in token else 1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 6) for v in vec]
    else:
        vec[0] = 1.0
    return vec


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
