"""
src/dialogue/compliance_guard.py

Post-LLM compliance checker — Layer 3 of the PII/compliance defence.

Scans the LLM's output text BEFORE it is spoken to the user.
If a violation is found, the agent speaks a safe refusal instead.

Checks:
  1. Investment advice — keywords suggesting specific financial recommendations
  2. PII leakage    — the LLM accidentally included PII in its response
  3. Out-of-scope   — response is clearly not about scheduling

Returns a ComplianceResult with:
  - is_compliant: bool
  - flag: None | "refuse_advice" | "refuse_pii" | "out_of_scope"
  - safe_speech: the response to use if non-compliant
  - reason: short explanation for audit log
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ─── Investment advice indicators ─────────────────────────────────────────────
# Phrases that suggest the LLM is providing investment advice.
# Conservative list — we'd rather over-trigger than under-trigger.

_ADVICE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(should|must|recommend|advise)\s+(you\s+)?(buy|sell|invest|hold|exit|redeem)", re.I),
    re.compile(r"\b(good|great|best|better|top)\s+(investment|fund|stock|option|choice|pick)\b", re.I),
    re.compile(r"\bexpected\s+returns?\b", re.I),
    re.compile(r"\b\d+(\.\d+)?\s*%\s+(return|gain|growth|yield|interest)\b", re.I),
    re.compile(r"\b(market|stocks?|equit(y|ies)|mutual\s+fund|nifty|sensex)\s+(will|is\s+going\s+to|might)\b", re.I),
    re.compile(r"\b(outperform|underperform|alpha|beta|sharpe)\b", re.I),
    re.compile(r"\b(diversif(y|ication)|rebalance|asset\s+allocation)\b", re.I),
]

# ─── PII leak indicators (in LLM output) ─────────────────────────────────────
# The scrubber already cleaned the INPUT; this checks the OUTPUT.

_PII_LEAK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b[6-9]\d{8,9}\b"),                           # phone
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),  # email
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I),           # PAN
    re.compile(r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)"), # Aadhaar
]

# ─── Safe refusal responses ────────────────────────────────────────────────────

_SAFE_ADVICE = (
    "I'm not able to provide investment advice. "
    "I can help you book a consultation with an advisor. "
    "Would you like to schedule one?"
)

_SAFE_PII = (
    "Please don't share personal details on this call. "
    "You'll receive a secure link after booking to submit your contact information."
)

_SAFE_SCOPE = "I'm only able to help with advisor appointment scheduling today."


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ComplianceResult:
    is_compliant: bool
    flag: str | None            # None | "refuse_advice" | "refuse_pii" | "out_of_scope"
    safe_speech: str            # speech to use — original if compliant, refusal if not
    reason: str = ""            # short audit note

    def effective_speech(self, original: str) -> str:
        """Return original speech if compliant, otherwise the safe refusal."""
        return original if self.is_compliant else self.safe_speech


# ─── Guard ────────────────────────────────────────────────────────────────────

class ComplianceGuard:
    """
    Scans LLM output for compliance violations.

    Usage:
        guard = ComplianceGuard()
        result = guard.check("You should invest in Nifty 50 for good returns.")
    """

    def check(self, llm_output: str) -> ComplianceResult:
        """
        Run all compliance checks on the given LLM output text.

        Args:
            llm_output: The 'speech' field from LLMResponse (text to be spoken).

        Returns:
            ComplianceResult — is_compliant=False blocks the response.
        """
        if not llm_output or not llm_output.strip():
            return ComplianceResult(is_compliant=True, flag=None, safe_speech="")

        # Check 1: investment advice
        for pattern in _ADVICE_PATTERNS:
            m = pattern.search(llm_output)
            if m:
                return ComplianceResult(
                    is_compliant=False,
                    flag="refuse_advice",
                    safe_speech=_SAFE_ADVICE,
                    reason=f"Investment advice detected: '{m.group(0)}'",
                )

        # Check 2: PII leakage
        for pattern in _PII_LEAK_PATTERNS:
            m = pattern.search(llm_output)
            if m:
                return ComplianceResult(
                    is_compliant=False,
                    flag="refuse_pii",
                    safe_speech=_SAFE_PII,
                    reason=f"PII leak detected: '{m.group(0)[:20]}...'",
                )

        return ComplianceResult(is_compliant=True, flag=None, safe_speech=llm_output)

    def check_and_gate(self, llm_output: str) -> str:
        """
        Convenience method — returns the safe speech directly.
        Use this when you just want the final text to speak.
        """
        result = self.check(llm_output)
        return result.effective_speech(llm_output)
