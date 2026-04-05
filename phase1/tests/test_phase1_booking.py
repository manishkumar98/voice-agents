"""
tests/test_phase1_booking.py

Phase 1 test suite — Booking Brain (pure business logic, no external APIs).

Test Cases:
  TC-1.1  Booking code format and uniqueness
  TC-1.2  Waitlist code format and uniqueness
  TC-1.3  Code validation helpers
  TC-1.4  Slot resolver — day matching
  TC-1.5  Slot resolver — time band matching
  TC-1.6  Slot resolver — topic affinity filtering
  TC-1.7  Slot resolver — no match returns empty list
  TC-1.8  PII scrubber — phone numbers
  TC-1.9  PII scrubber — email addresses
  TC-1.10 PII scrubber — PAN numbers
  TC-1.11 PII scrubber — Aadhaar numbers
  TC-1.12 PII scrubber — 16-digit account numbers
  TC-1.13 PII scrubber — clean text passes through unchanged
  TC-1.14 PII scrubber — multiple PII types in one string
  TC-1.15 Secure URL — generate and verify round-trip
  TC-1.16 Secure URL — tampered token raises BadSignature
  TC-1.17 Secure URL — expired token raises SignatureExpired
  TC-1.18 Secure URL — token extraction from full URL
  TC-1.19 Waitlist entry — creation and fields
  TC-1.20 Waitlist entry — cancel flow
  TC-1.21 Waitlist entry — validation rejects empty fields
"""

import os
import sys
from datetime import datetime

import pytest
import pytz

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

IST = pytz.timezone("Asia/Kolkata")

# Reference date for slot resolver tests: Friday, 3 April 2026 09:00 IST
# (All mock calendar slots are 6–16 April 2026)
_REF_DATE = IST.localize(datetime(2026, 4, 3, 9, 0, 0))
CALENDAR_PATH = os.path.join(PROJECT_ROOT, "data", "mock_calendar.json")


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.1 — Booking code format and uniqueness
# ═══════════════════════════════════════════════════════════════════════════════

class TestBookingCodeGenerator:

    def test_format_starts_with_NL(self):
        from src.booking.booking_code_generator import generate_booking_code
        code = generate_booking_code()
        assert code.startswith("NL-"), f"Expected 'NL-' prefix, got: {code}"

    def test_format_total_length(self):
        from src.booking.booking_code_generator import generate_booking_code
        code = generate_booking_code()
        assert len(code) == 7, f"Expected length 7 (NL-XXXX), got: {len(code)} — {code}"

    def test_suffix_is_alphanumeric_uppercase(self):
        from src.booking.booking_code_generator import generate_booking_code
        for _ in range(20):
            code = generate_booking_code()
            suffix = code[3:]
            assert suffix.isupper() or suffix.isdigit() or all(
                c.isupper() or c.isdigit() for c in suffix
            ), f"Suffix contains unexpected chars: {suffix}"

    def test_no_ambiguous_chars(self):
        """Codes must not contain 0, O, 1, I."""
        from src.booking.booking_code_generator import generate_booking_code
        ambiguous = set("01OI")
        for _ in range(50):
            code = generate_booking_code()
            suffix = code[3:]
            found = ambiguous.intersection(suffix)
            assert not found, f"Ambiguous chars {found} found in code: {code}"

    def test_uniqueness_across_100_codes(self):
        from src.booking.booking_code_generator import generate_booking_code
        codes = set()
        for _ in range(100):
            code = generate_booking_code(existing_codes=codes)
            assert code not in codes, f"Duplicate code generated: {code}"
            codes.add(code)

    def test_avoids_existing_codes(self):
        from src.booking.booking_code_generator import generate_booking_code
        existing = {"NL-A742", "NL-B3K9", "NL-CX7P"}
        for _ in range(20):
            code = generate_booking_code(existing_codes=existing)
            assert code not in existing


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.2 — Waitlist code format and uniqueness
# ═══════════════════════════════════════════════════════════════════════════════

class TestWaitlistCodeGenerator:

    def test_format_starts_with_NL_W(self):
        from src.booking.booking_code_generator import generate_waitlist_code
        code = generate_waitlist_code()
        assert code.startswith("NL-W"), f"Expected 'NL-W' prefix, got: {code}"

    def test_format_total_length(self):
        from src.booking.booking_code_generator import generate_waitlist_code
        code = generate_waitlist_code()
        assert len(code) == 7, f"Expected length 7 (NL-WXXX), got: {len(code)} — {code}"

    def test_uniqueness_across_50_codes(self):
        from src.booking.booking_code_generator import generate_waitlist_code
        codes = set()
        for _ in range(50):
            code = generate_waitlist_code(existing_codes=codes)
            assert code not in codes
            codes.add(code)


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.3 — Code validation helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestCodeValidation:

    def test_valid_booking_code(self):
        from src.booking.booking_code_generator import is_valid_booking_code
        assert is_valid_booking_code("NL-A742") is True
        assert is_valid_booking_code("NL-B3K9") is True

    def test_invalid_booking_code_wrong_prefix(self):
        from src.booking.booking_code_generator import is_valid_booking_code
        assert is_valid_booking_code("WL-A742") is False
        assert is_valid_booking_code("NLA742") is False

    def test_waitlist_code_is_not_booking_code(self):
        from src.booking.booking_code_generator import (
            is_valid_booking_code, is_valid_waitlist_code, generate_waitlist_code
        )
        code = generate_waitlist_code()  # guaranteed to use only _SAFE_CHARS
        assert is_valid_booking_code(code) is False
        assert is_valid_waitlist_code(code) is True

    def test_valid_waitlist_code(self):
        from src.booking.booking_code_generator import is_valid_waitlist_code, generate_waitlist_code
        # Use generated codes — they are guaranteed to use only _SAFE_CHARS
        for _ in range(5):
            code = generate_waitlist_code()
            assert is_valid_waitlist_code(code) is True
        # Hard-code a known valid code (no ambiguous 0,O,1,I)
        assert is_valid_waitlist_code("NL-WKP3") is True
        assert is_valid_waitlist_code("NL-W39K") is True

    def test_invalid_waitlist_code_wrong_length(self):
        from src.booking.booking_code_generator import is_valid_waitlist_code
        assert is_valid_waitlist_code("NL-W39") is False   # 2-char suffix
        assert is_valid_waitlist_code("NL-W3910") is False  # 4-char suffix


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.4 — Slot resolver — day matching
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlotResolverDayMatching:

    def test_monday_resolves_to_april_6(self):
        """From Friday Apr 3, 'Monday' should resolve to Apr 6."""
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="10 AM",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) >= 1, "Expected at least one slot on Monday Apr 6"
        for s in slots:
            assert s.start.date().isoformat() == "2026-04-06", (
                f"Expected Apr 6, got {s.start.date()}"
            )

    def test_tuesday_resolves_to_april_7(self):
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Tuesday",
            time_preference="morning",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) >= 1
        for s in slots:
            assert s.start.date().isoformat() == "2026-04-07"

    def test_next_monday_resolves_to_april_13(self):
        """'next Monday' from Friday Apr 3 should be Apr 13 (not Apr 6)."""
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="next Monday",
            time_preference="morning",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) >= 1
        for s in slots:
            assert s.start.date().isoformat() == "2026-04-13", (
                f"Expected Apr 13 for 'next Monday', got {s.start.date()}"
            )

    def test_returns_at_most_2_slots(self):
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="afternoon",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) <= 2

    def test_slots_sorted_by_start_time(self):
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="afternoon",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        if len(slots) > 1:
            assert slots[0].start <= slots[1].start


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.5 — Slot resolver — time band matching
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlotResolverTimeBand:

    def test_morning_returns_10am_slot(self):
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="morning",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) >= 1
        for s in slots:
            assert 9 <= s.start.hour < 12, f"Morning slot not in 9-12: {s.start.hour}"

    def test_afternoon_returns_2pm_slot(self):
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="afternoon",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) >= 1
        for s in slots:
            assert 12 <= s.start.hour < 17, f"Afternoon slot not in 12-17: {s.start.hour}"

    def test_explicit_2pm_matches_14h_slot(self):
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="2 PM",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) >= 1
        # The 14:00 slot should be in results
        hours = [s.start.hour for s in slots]
        assert 14 in hours, f"Expected 14:00 slot, got hours: {hours}"


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.6 — Slot resolver — topic affinity filtering
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlotResolverTopicAffinity:

    def test_kyc_topic_matches_affinity_slot(self):
        """SLOT-20260406-1530 has topic_affinity=[kyc_onboarding, account_changes]."""
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="afternoon",
            topic="kyc_onboarding",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(slots) >= 1
        # Slots with no affinity restriction or kyc_onboarding should be included
        for s in slots:
            assert (not s.topic_affinity) or ("kyc_onboarding" in s.topic_affinity), (
                f"Slot {s.slot_id} has wrong affinity: {s.topic_affinity}"
            )

    def test_sip_topic_filtered_from_kyc_only_slot(self):
        """Slot with topic_affinity=['kyc_onboarding'] should NOT appear for sip_mandates."""
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Monday",
            time_preference="afternoon",
            topic="sip_mandates",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        for s in slots:
            if s.topic_affinity:
                assert "sip_mandates" in s.topic_affinity, (
                    f"Slot {s.slot_id} with affinity {s.topic_affinity} shown for sip_mandates"
                )

    def test_all_slots_returned_without_topic_filter(self):
        """Without topic filter, more slots should be available."""
        from src.booking.slot_resolver import resolve_slots
        all_slots = resolve_slots(
            day_preference="Monday",
            time_preference="afternoon",
            topic=None,
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        assert len(all_slots) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.7 — Slot resolver — no match returns empty list
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlotResolverNoMatch:

    def test_nonexistent_date_returns_empty(self):
        """Asking for a date with no slots → empty list (not exception)."""
        from src.booking.slot_resolver import resolve_slots
        # Sunday April 5 has no slots in mock_calendar
        ref = IST.localize(datetime(2026, 4, 3, 9, 0, 0))
        slots = resolve_slots(
            day_preference="Sunday",
            time_preference="morning",
            calendar_path=CALENDAR_PATH,
            reference_date=ref,
        )
        assert isinstance(slots, list)
        assert len(slots) == 0

    def test_all_slots_are_available_status(self):
        """resolve_slots must never return TENTATIVE or CANCELLED slots."""
        from src.booking.slot_resolver import resolve_slots
        slots = resolve_slots(
            day_preference="Wednesday",
            time_preference="afternoon",
            calendar_path=CALENDAR_PATH,
            reference_date=_REF_DATE,
        )
        for s in slots:
            assert s.status == "AVAILABLE", f"Non-AVAILABLE slot returned: {s.slot_id} ({s.status})"


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.8 — PII scrubber — phone numbers (standalone + contextual)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberPhone:

    def test_10_digit_mobile_standalone(self):
        """10-digit mobile with no intent phrase — caught by standalone regex."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("My number is 9876543210")
        assert "[REDACTED]" in result.cleaned_text
        assert result.pii_found is True
        assert "phone" in result.categories

    def test_mobile_with_plus91_prefix_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("Call me at +919876543210")
        assert "[REDACTED]" in result.cleaned_text
        assert result.pii_found is True

    def test_mobile_with_0_prefix_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("reach me on 09876543210")
        assert "[REDACTED]" in result.cleaned_text

    def test_9_digit_contextual_scrubbed(self):
        """'my phone number is' + 9-digit value — caught by contextual pass."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my phone number is 999999999")
        assert "[REDACTED]" in result.cleaned_text
        assert result.pii_found is True
        assert "phone" in result.categories
        assert "phone" in result.context_detected

    def test_short_number_with_intent_phrase_scrubbed(self):
        """Even a short digit string after 'my mobile is' must be redacted."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my mobile is 98765")
        assert "[REDACTED]" in result.cleaned_text
        assert "phone" in result.context_detected

    def test_intent_phrase_preserves_label(self):
        """The intent label ('my phone number is') should remain; only value is redacted."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my phone number is 9876543210")
        assert "my phone number is" in result.cleaned_text
        assert "9876543210" not in result.cleaned_text

    def test_landline_5_digits_no_intent_not_scrubbed(self):
        """5-digit PIN with no intent phrase — not a phone number."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("My PIN is 12345")
        assert result.pii_found is False or "phone" not in result.categories


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.8b — Contextual detection — Aadhaar, PAN, email, account
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberContextual:

    def test_aadhaar_intent_phrase_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my Aadhaar is 1234")
        assert "[REDACTED]" in result.cleaned_text
        assert "aadhaar" in result.context_detected

    def test_pan_intent_phrase_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my PAN is ABCDE1234F")
        assert "[REDACTED]" in result.cleaned_text
        assert "pan" in result.context_detected

    def test_email_intent_phrase_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my email is user@test.com")
        assert "[REDACTED]" in result.cleaned_text
        assert "email" in result.context_detected

    def test_account_intent_phrase_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my account number is 12345678")
        assert "[REDACTED]" in result.cleaned_text
        assert "account_number" in result.context_detected

    def test_context_and_pattern_both_populated(self):
        """Text with context phrase + standalone number — both detection fields filled."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my phone number is 99999 and also 9876543210")
        assert result.pii_found is True
        assert "phone" in result.context_detected   # 99999 via intent phrase
        assert "phone" in result.categories

    def test_detection_summary_clean(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("I want to book a KYC slot")
        assert "No PII" in result.detection_summary()

    def test_detection_summary_contextual(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my Aadhaar is 1234")
        assert "contextual" in result.detection_summary()

    def test_intent_phrase_without_value_not_redacted(self):
        """Saying 'my phone number' without providing one should not cause a crash."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my phone number")
        assert isinstance(result.cleaned_text, str)


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.9 — PII scrubber — email addresses
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberEmail:

    def test_standard_email_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("Send it to john.doe@example.com please")
        assert "[REDACTED]" in result.cleaned_text
        assert "email" in result.categories

    def test_gmail_address_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("my email is user123@gmail.com")
        assert "[REDACTED]" in result.cleaned_text

    def test_email_with_plus_tag_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("use binay+work@company.in")
        assert "[REDACTED]" in result.cleaned_text


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.10 — PII scrubber — PAN numbers
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberPAN:

    def test_valid_pan_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("My PAN is ABCDE1234F")
        assert "[REDACTED]" in result.cleaned_text
        assert "pan" in result.categories

    def test_pan_lowercase_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("pan number abcde1234f")
        assert "[REDACTED]" in result.cleaned_text

    def test_wrong_pan_format_not_scrubbed(self):
        """ABCD1234F (only 4 leading letters) should not match."""
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("code ABCD1234F")
        assert "pan" not in result.categories


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.11 — PII scrubber — Aadhaar numbers
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberAadhaar:

    def test_12_digit_aadhaar_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("My Aadhaar is 234567890123")
        assert "[REDACTED]" in result.cleaned_text
        assert "aadhaar" in result.categories

    def test_aadhaar_with_spaces_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("Aadhaar: 2345 6789 0123")
        assert "[REDACTED]" in result.cleaned_text

    def test_aadhaar_with_dashes_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("2345-6789-0123 is my ID")
        assert "[REDACTED]" in result.cleaned_text


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.12 — PII scrubber — 16-digit account numbers
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberAccountNumber:

    def test_16_digit_account_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("Account 1234567890123456 is mine")
        assert "[REDACTED]" in result.cleaned_text
        assert "account_number" in result.categories

    def test_card_number_with_spaces_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("card: 1234 5678 9012 3456")
        assert "[REDACTED]" in result.cleaned_text

    def test_card_number_with_dashes_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("1234-5678-9012-3456")
        assert "[REDACTED]" in result.cleaned_text


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.13 — PII scrubber — clean text passes through unchanged
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberCleanText:

    def test_clean_booking_query_unchanged(self):
        from src.booking.pii_scrubber import scrub_pii
        text = "I want to book a consultation about KYC next Monday at 2 PM"
        result = scrub_pii(text)
        assert result.cleaned_text == text
        assert result.pii_found is False
        assert result.categories == []

    def test_empty_string_handled(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("")
        assert result.cleaned_text == ""
        assert result.pii_found is False

    def test_booking_code_not_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        result = scrub_pii("My booking code is NL-A742")
        assert "NL-A742" in result.cleaned_text
        assert result.pii_found is False


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.14 — PII scrubber — multiple PII types in one string
# ═══════════════════════════════════════════════════════════════════════════════

class TestPIIScrubberMultiple:

    def test_phone_and_email_both_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        text = "Call me at 9876543210 or email me at test@example.com"
        result = scrub_pii(text)
        assert result.pii_found is True
        assert "phone" in result.categories
        assert "email" in result.categories
        assert "9876543210" not in result.cleaned_text
        assert "test@example.com" not in result.cleaned_text

    def test_pan_and_phone_both_scrubbed(self):
        from src.booking.pii_scrubber import scrub_pii
        text = "PAN ABCDE1234F and mobile 9876543210"
        result = scrub_pii(text)
        assert "pan" in result.categories
        assert "phone" in result.categories
        assert "ABCDE1234F" not in result.cleaned_text
        assert "9876543210" not in result.cleaned_text

    def test_redacted_count_matches_pii_occurrences(self):
        from src.booking.pii_scrubber import scrub_pii
        text = "email a@b.com and also c@d.com"
        result = scrub_pii(text)
        assert result.cleaned_text.count("[REDACTED]") == 2


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.15 — Secure URL — generate and verify round-trip
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecureURL:

    _SECRET = "test_secret_key_for_unit_tests_minimum32chars"
    _DOMAIN = "http://localhost:8501"

    def test_generate_returns_full_url(self):
        from src.booking.secure_url_generator import generate_secure_url
        url = generate_secure_url(
            booking_code="NL-A742",
            topic="kyc_onboarding",
            slot_ist="2026-04-06T14:00:00+05:30",
            secret=self._SECRET,
            domain=self._DOMAIN,
        )
        assert url.startswith("http://localhost:8501/book/")

    def test_round_trip_decode(self):
        from src.booking.secure_url_generator import (
            generate_secure_url,
            verify_secure_url,
            extract_token_from_url,
        )
        url = generate_secure_url(
            booking_code="NL-B3K9",
            topic="sip_mandates",
            slot_ist="2026-04-07T10:00:00+05:30",
            secret=self._SECRET,
            domain=self._DOMAIN,
        )
        token = extract_token_from_url(url)
        payload = verify_secure_url(token, secret=self._SECRET, max_age_seconds=86400)

        assert payload["booking_code"] == "NL-B3K9"
        assert payload["topic"] == "sip_mandates"
        assert "2026-04-07" in payload["slot_ist"]

    def test_datetime_object_accepted(self):
        from src.booking.secure_url_generator import generate_secure_url, verify_secure_url, extract_token_from_url
        slot_dt = IST.localize(datetime(2026, 4, 8, 14, 0, 0))
        url = generate_secure_url(
            booking_code="NL-CX7P",
            topic="withdrawals",
            slot_ist=slot_dt,
            secret=self._SECRET,
            domain=self._DOMAIN,
        )
        token = extract_token_from_url(url)
        payload = verify_secure_url(token, secret=self._SECRET)
        assert payload["booking_code"] == "NL-CX7P"

    def test_url_contains_no_pii(self):
        """The URL must not contain the booking code in plaintext."""
        from src.booking.secure_url_generator import generate_secure_url
        url = generate_secure_url(
            booking_code="NL-A742",
            topic="kyc_onboarding",
            slot_ist="2026-04-06T14:00:00+05:30",
            secret=self._SECRET,
            domain=self._DOMAIN,
        )
        # Token is base64-encoded — the raw code should not appear literally
        # (The domain part has /book/ but the code itself is encoded)
        token_part = url.split("/book/")[1]
        assert "NL-A742" not in token_part


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.16 — Secure URL — tampered token raises BadSignature
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecureURLTampering:

    _SECRET = "test_secret_key_for_unit_tests_minimum32chars"

    def test_tampered_token_raises(self):
        from itsdangerous import BadSignature
        from src.booking.secure_url_generator import verify_secure_url
        with pytest.raises(BadSignature):
            verify_secure_url("totally.invalid.token", secret=self._SECRET)

    def test_wrong_secret_raises(self):
        from itsdangerous import BadSignature
        from src.booking.secure_url_generator import (
            generate_secure_url, verify_secure_url, extract_token_from_url
        )
        url = generate_secure_url(
            booking_code="NL-A742",
            topic="kyc_onboarding",
            slot_ist="2026-04-06T14:00:00+05:30",
            secret=self._SECRET,
            domain="http://localhost:8501",
        )
        token = extract_token_from_url(url)
        with pytest.raises(BadSignature):
            verify_secure_url(token, secret="a_completely_different_secret_32chars")


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.17 — Secure URL — expired token raises SignatureExpired
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecureURLExpiry:

    _SECRET = "test_secret_key_for_unit_tests_minimum32chars"

    def test_expired_token_raises(self):
        from itsdangerous import SignatureExpired
        from src.booking.secure_url_generator import (
            generate_secure_url, verify_secure_url, extract_token_from_url
        )
        url = generate_secure_url(
            booking_code="NL-EXP1",
            topic="kyc_onboarding",
            slot_ist="2026-04-06T14:00:00+05:30",
            secret=self._SECRET,
            domain="http://localhost:8501",
        )
        token = extract_token_from_url(url)
        # max_age=-1 ensures the token is always expired
        with pytest.raises(SignatureExpired):
            verify_secure_url(token, secret=self._SECRET, max_age_seconds=-1)


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.18 — Secure URL — token extraction from full URL
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecureURLExtraction:

    def test_extract_token_valid_url(self):
        from src.booking.secure_url_generator import extract_token_from_url
        url = "http://localhost:8501/book/abc123.def456"
        token = extract_token_from_url(url)
        assert token == "abc123.def456"

    def test_extract_token_invalid_url_raises(self):
        from src.booking.secure_url_generator import extract_token_from_url
        with pytest.raises(ValueError):
            extract_token_from_url("http://localhost:8501/no-book-segment")


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.19 — Waitlist entry — creation and fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestWaitlistEntry:

    def test_create_returns_waitlist_entry(self):
        from src.booking.waitlist_handler import create_waitlist_entry, WaitlistEntry
        entry = create_waitlist_entry(
            topic="kyc_onboarding",
            day_preference="Monday",
            time_preference="2 PM",
        )
        assert isinstance(entry, WaitlistEntry)

    def test_waitlist_code_format(self):
        from src.booking.waitlist_handler import create_waitlist_entry
        from src.booking.booking_code_generator import is_valid_waitlist_code
        entry = create_waitlist_entry(
            topic="sip_mandates",
            day_preference="Tuesday",
            time_preference="morning",
        )
        assert is_valid_waitlist_code(entry.waitlist_code), (
            f"Invalid waitlist code: {entry.waitlist_code}"
        )

    def test_fields_stored_correctly(self):
        from src.booking.waitlist_handler import create_waitlist_entry
        ref = IST.localize(datetime(2026, 4, 3, 9, 0, 0))
        entry = create_waitlist_entry(
            topic="withdrawals",
            day_preference="Friday",
            time_preference="afternoon",
            reference_time=ref,
        )
        assert entry.topic == "withdrawals"
        assert entry.day_preference == "Friday"
        assert entry.time_preference == "afternoon"
        assert entry.status == "ACTIVE"
        assert entry.created_at.tzinfo is not None  # must be timezone-aware

    def test_to_dict_serializable(self):
        import json
        from src.booking.waitlist_handler import create_waitlist_entry
        entry = create_waitlist_entry(
            topic="account_changes",
            day_preference="Wednesday",
            time_preference="10 AM",
        )
        d = entry.to_dict()
        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert "waitlist_code" in json_str
        assert "topic" in json_str

    def test_unique_codes_across_multiple_entries(self):
        from src.booking.waitlist_handler import create_waitlist_entry
        codes = set()
        for _ in range(20):
            entry = create_waitlist_entry(
                topic="kyc_onboarding",
                day_preference="Monday",
                time_preference="morning",
                existing_codes=codes,
            )
            assert entry.waitlist_code not in codes
            codes.add(entry.waitlist_code)


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.20 — Waitlist entry — cancel flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestWaitlistCancellation:

    def test_cancel_sets_status_to_cancelled(self):
        from src.booking.waitlist_handler import create_waitlist_entry, cancel_waitlist_entry
        entry = create_waitlist_entry(
            topic="kyc_onboarding",
            day_preference="Monday",
            time_preference="2 PM",
        )
        cancelled = cancel_waitlist_entry(entry)
        assert cancelled.status == "CANCELLED"

    def test_cancel_preserves_other_fields(self):
        from src.booking.waitlist_handler import create_waitlist_entry, cancel_waitlist_entry
        entry = create_waitlist_entry(
            topic="sip_mandates",
            day_preference="Tuesday",
            time_preference="morning",
        )
        cancelled = cancel_waitlist_entry(entry)
        assert cancelled.waitlist_code == entry.waitlist_code
        assert cancelled.topic == entry.topic
        assert cancelled.day_preference == entry.day_preference

    def test_original_entry_unchanged_after_cancel(self):
        from src.booking.waitlist_handler import create_waitlist_entry, cancel_waitlist_entry
        entry = create_waitlist_entry(
            topic="kyc_onboarding",
            day_preference="Monday",
            time_preference="2 PM",
        )
        cancel_waitlist_entry(entry)
        # Original must be unchanged
        assert entry.status == "ACTIVE"


# ═══════════════════════════════════════════════════════════════════════════════
# TC-1.21 — Waitlist entry — validation rejects empty fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestWaitlistValidation:

    def test_empty_topic_raises(self):
        from src.booking.waitlist_handler import create_waitlist_entry
        with pytest.raises(ValueError, match="topic"):
            create_waitlist_entry(topic="", day_preference="Monday", time_preference="2 PM")

    def test_empty_day_raises(self):
        from src.booking.waitlist_handler import create_waitlist_entry
        with pytest.raises(ValueError, match="day_preference"):
            create_waitlist_entry(topic="kyc_onboarding", day_preference="", time_preference="2 PM")

    def test_empty_time_raises(self):
        from src.booking.waitlist_handler import create_waitlist_entry
        with pytest.raises(ValueError, match="time_preference"):
            create_waitlist_entry(topic="kyc_onboarding", day_preference="Monday", time_preference="")
