"""
src/booking/booking_code_generator.py

Generates unique booking codes in NL-XXXX format (4 uppercase alphanumeric chars)
and waitlist codes in NL-WXXX format (W prefix + 3 chars).

Format rationale:
  - "NL" prefix is constant (brand identifier)
  - 4-char suffix: uppercase letters + digits (excludes 0/O and 1/I to avoid confusion)
  - Waitlist codes: NL-W + 3 chars to visually distinguish from booking codes

No external dependencies — stdlib only.
"""

import random
import string

# Excludes visually ambiguous chars: 0, O, 1, I
_SAFE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_booking_code(existing_codes: set[str] | None = None) -> str:
    """
    Generate a unique booking code in NL-XXXX format.

    Args:
        existing_codes: Set of already-used codes to avoid collision.

    Returns:
        A string like "NL-A742".
    """
    if existing_codes is None:
        existing_codes = set()

    max_attempts = 1000
    for _ in range(max_attempts):
        suffix = "".join(random.choices(_SAFE_CHARS, k=4))
        code = f"NL-{suffix}"
        if code not in existing_codes:
            return code

    raise RuntimeError("Could not generate a unique booking code after 1000 attempts.")


def generate_waitlist_code(existing_codes: set[str] | None = None) -> str:
    """
    Generate a unique waitlist code in NL-WXXX format.

    Args:
        existing_codes: Set of already-used codes to avoid collision.

    Returns:
        A string like "NL-W391".
    """
    if existing_codes is None:
        existing_codes = set()

    max_attempts = 1000
    for _ in range(max_attempts):
        suffix = "".join(random.choices(_SAFE_CHARS, k=3))
        code = f"NL-W{suffix}"
        if code not in existing_codes:
            return code

    raise RuntimeError("Could not generate a unique waitlist code after 1000 attempts.")


def is_valid_booking_code(code: str) -> bool:
    """Return True if code matches NL-XXXX format (not a waitlist code)."""
    if not isinstance(code, str):
        return False
    if not code.startswith("NL-"):
        return False
    suffix = code[3:]
    if len(suffix) != 4:
        return False
    if suffix.startswith("W"):
        return False  # That's a waitlist code
    return all(c in _SAFE_CHARS for c in suffix)


def is_valid_waitlist_code(code: str) -> bool:
    """Return True if code matches NL-WXXX format."""
    if not isinstance(code, str):
        return False
    if not code.startswith("NL-W"):
        return False
    suffix = code[4:]
    if len(suffix) != 3:
        return False
    return all(c in _SAFE_CHARS for c in suffix)
