"""
tests/conftest.py  (Phase 2)

Adds phase0, phase1, and phase2/src to sys.path so all test modules
can import `src.dialogue.*` and `src.booking.*` without installing packages.
Also sets MOCK_CALENDAR_PATH so calendar lookups resolve correctly.
"""

import os
import sys

# voice-agents/ root
_tests_dir   = os.path.dirname(os.path.abspath(__file__))          # phase2/tests/
_phase2_dir  = os.path.dirname(_tests_dir)                          # phase2/
_root_dir    = os.path.dirname(_phase2_dir)                         # voice-agents/

for _entry in [
    os.path.join(_root_dir, "phase0"),
    os.path.join(_root_dir, "phase1"),
    _phase2_dir,                                                     # phase2/ — so "src.dialogue" resolves
]:
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

# Calendar data used by slot_resolver during tests
os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    os.path.join(_root_dir, "phase1", "data", "mock_calendar.json"),
)
