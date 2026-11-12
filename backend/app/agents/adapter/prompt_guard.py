"""Prompt injection defence and untrusted passage isolation."""

import re
from typing import Tuple

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+override\s*:", re.IGNORECASE),
    re.compile(r"mark\s+(?:every|all)\s+claims?\s+as\s+['\"]?verified['\"]?", re.IGNORECASE),
    re.compile(r"invent\s+source\s*id", re.IGNORECASE),
    re.compile(r"include\s+all\s+restricted", re.IGNORECASE),
]


def sanitize_untrusted_passage(text: str) -> Tuple[str, bool]:
    """Strip adversarial prompt-injection directives from retrieved source text while preserving genuine technical content."""
    sanitized = text
    injection_detected = False

    for pat in INJECTION_PATTERNS:
        if pat.search(sanitized):
            injection_detected = True

    if injection_detected:
        # Remove sentences containing adversarial override instructions while keeping benign technical sentences
        sentences = re.split(r"(?<=[.!?])\s+", sanitized)
        clean_sentences = []
        for s in sentences:
            if any(pat.search(s) for pat in INJECTION_PATTERNS):
                clean_sentences.append("[ADVERSARIAL_INSTRUCTION_ISOLATED]")
            else:
                clean_sentences.append(s)
        sanitized = " ".join(clean_sentences)

    return sanitized, injection_detected
