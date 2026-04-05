"""
src/booking/pii_scrubber.py

Layer 2 PII scrubber — runs on STT output BEFORE it reaches the LLM.

TWO-PASS DETECTION STRATEGY
────────────────────────────
Pass 1 — Contextual detection (higher priority):
    Looks for intent phrases like "my phone number is", "my Aadhaar is",
    "my PAN is" followed by a value. When an intent phrase is present,
    the following value is redacted even if it doesn't strictly match
    the pattern regex (e.g. 8-digit partial number, lowercase PAN).
    This is the primary signal — a human explicitly labelling PII.

Pass 2 — Standalone pattern detection:
    Regex patterns for values that appear WITHOUT a preceding intent phrase.
    Catches numbers/emails shared without labelling them
    (e.g. someone reciting digits mid-sentence).

Both passes write to the same cleaned_text. Categories from both are merged.
The result also exposes which categories were caught contextually vs. by pattern.

Detects:
  - Indian mobile numbers (9–10 digit, +91/0 prefix variants)
  - Email addresses
  - PAN numbers (AAAAA0000A format)
  - Aadhaar numbers (12 digits, spaced/dashed variants)
  - 16-digit account / card numbers
"""

import re
from dataclasses import dataclass, field

_REDACT = "[REDACTED]"

# ─── Pass 1: Contextual patterns ──────────────────────────────────────────────
#
# Each entry: (category, pattern)
# pattern must have exactly ONE capturing group — group(1) is the PII value.
# The label ("my phone number is") is kept; only the value is redacted.
#
# Intent phrase vocab covers common STT variants:
#   "my phone is", "my number is", "my mobile number is",
#   "call me on", "reach me at", "whatsapp me on", etc.

_CONTEXTUAL_PATTERNS: list[tuple[str, re.Pattern]] = [
    # ── Phone ──
    ("phone", re.compile(
        r"(?:"
        r"my\s+(?:phone|mobile|cell|contact|whatsapp)(?:\s+(?:number|no\.?))?"
        r"|(?:call|reach|contact|ping|whatsapp)\s+(?:me\s+)?(?:on|at|via)?"
        r"|my\s+number"
        r")"
        r"\s*(?:is|:|-|=)?\s*"
        r"([+\d][\d\s\-]{4,14})",          # value: digit sequence 5–15 chars
        re.IGNORECASE,
    )),

    # ── Aadhaar ──
    ("aadhaar", re.compile(
        r"(?:"
        r"my\s+(?:aadhaar|aadhar|adhaar|uid)(?:\s+(?:number|no\.?|card))?"
        r"|(?:aadhaar|aadhar|adhaar)\s+(?:number\s+)?(?:is|:)?"
        r")"
        r"\s*(?:is|:|-|=)?\s*"
        r"([\d][\d\s\-]{2,17})",           # value: 3+ chars — catch partials too
        re.IGNORECASE,
    )),

    # ── PAN ──
    ("pan", re.compile(
        r"(?:"
        r"my\s+pan(?:\s+(?:number|no\.?|card))?"
        r"|pan\s+(?:number\s+)?(?:is|:)?"
        r")"
        r"\s*(?:is|:|-|=)?\s*"
        r"([A-Z0-9]{5,12})",               # value: loose alphanumeric
        re.IGNORECASE,
    )),

    # ── Email ──
    ("email", re.compile(
        r"(?:"
        r"my\s+(?:email|e-mail|mail|gmail|yahoo)(?:\s+(?:id|address|is))?"
        r"|(?:email|mail|send)\s+(?:me\s+)?(?:at|to)?"
        r"|(?:reach|contact)\s+me\s+(?:at|via|on)\s+(?:email)?"
        r")"
        r"\s*(?:is|:|-|=)?\s*"
        r"(\S+@\S+)",                       # value: anything with @
        re.IGNORECASE,
    )),

    # ── Account / card number ──
    ("account_number", re.compile(
        r"(?:"
        r"my\s+(?:account|card|debit|credit|bank)(?:\s+(?:number|no\.?))?"
        r"|(?:account|card)\s+(?:number\s+)?(?:is|:)?"
        r")"
        r"\s*(?:is|:|-|=)?\s*"
        r"([\d][\d\s\-]{3,22})",           # value: 4+ chars — catch partials too
        re.IGNORECASE,
    )),
]

# ─── Pass 2: Standalone patterns ──────────────────────────────────────────────
#
# These match PII values that appear WITHOUT a preceding intent phrase.
# Ordered: 16-digit check before 12-digit Aadhaar to avoid partial overlap.

_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+91[\s\-]?|91[\s\-]?|0)?"
    r"[6-9]\d{8,9}"
    r"(?!\d)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
_PAN_RE = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    re.IGNORECASE,
)
_AADHAAR_RE = re.compile(
    r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)",
)
_ACCOUNT_16_RE = re.compile(
    r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)",
)

_STANDALONE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("account_number", _ACCOUNT_16_RE),
    ("aadhaar",        _AADHAAR_RE),
    ("pan",            _PAN_RE),
    ("phone",          _PHONE_RE),
    ("email",          _EMAIL_RE),
]


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class PIIScrubResult:
    cleaned_text: str
    pii_found: bool
    categories: list[str] = field(default_factory=list)
    context_detected: list[str] = field(default_factory=list)   # caught by intent phrase
    pattern_detected: list[str] = field(default_factory=list)   # caught by standalone regex

    def detection_summary(self) -> str:
        """Human-readable summary for UI / audit logs."""
        if not self.pii_found:
            return "No PII detected — text is clean."
        parts = []
        if self.context_detected:
            parts.append(f"contextual ({', '.join(self.context_detected)})")
        if self.pattern_detected:
            parts.append(f"pattern ({', '.join(self.pattern_detected)})")
        return "PII detected via: " + " + ".join(parts)


# ─── Core scrubber ────────────────────────────────────────────────────────────

def scrub_pii(text: str) -> PIIScrubResult:
    """
    Two-pass PII scrubber.

    Pass 1 — contextual: redacts values that follow explicit intent phrases.
    Pass 2 — standalone: redacts values that appear without intent phrases.

    Args:
        text: Raw STT transcript (or any user-submitted text).

    Returns:
        PIIScrubResult with cleaned_text, pii_found, categories,
        context_detected, and pattern_detected.
    """
    if not text:
        return PIIScrubResult(cleaned_text=text, pii_found=False)

    cleaned = text
    context_cats: list[str] = []
    pattern_cats: list[str] = []

    # ── Pass 1: contextual ────────────────────────────────────────────────────
    for category, pattern in _CONTEXTUAL_PATTERNS:
        def _redact_value(m: re.Match, _cat: str = category) -> str:
            """Replace only the captured value group, keep the intent label."""
            full_match = m.group(0)
            return full_match[: m.start(1) - m.start()] + _REDACT

        new_text, count = pattern.subn(_redact_value, cleaned)
        if count > 0:
            cleaned = new_text
            if category not in context_cats:
                context_cats.append(category)

    # ── Pass 2: standalone ────────────────────────────────────────────────────
    for category, pattern in _STANDALONE_PATTERNS:
        new_text, count = pattern.subn(_REDACT, cleaned)
        if count > 0:
            cleaned = new_text
            if category not in pattern_cats:
                pattern_cats.append(category)

    all_cats = list(dict.fromkeys(context_cats + pattern_cats))  # deduplicated, ordered

    return PIIScrubResult(
        cleaned_text=cleaned,
        pii_found=len(all_cats) > 0,
        categories=all_cats,
        context_detected=context_cats,
        pattern_detected=pattern_cats,
    )


def contains_pii(text: str) -> bool:
    """Quick check — returns True if any PII is detected."""
    return scrub_pii(text).pii_found
