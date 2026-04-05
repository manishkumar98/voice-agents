"""
tests/conftest.py  (Phase 4)

Adds phase0/phase1/phase2/phase4 to sys.path and loads .env so all
MCP tools can import correctly and read credentials.
"""
import os
import sys
from pathlib import Path

_tests_dir  = Path(__file__).resolve().parent       # phase4/tests/
_phase4_dir = _tests_dir.parent                     # phase4/
_root_dir   = _phase4_dir.parent                    # voice-agents/

for _entry in [
    str(_root_dir / "phase0"),
    str(_root_dir / "phase1"),
    str(_root_dir / "phase2"),
    str(_phase4_dir),
]:
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

# Load .env from voice-agents/
from dotenv import load_dotenv
load_dotenv(str(_root_dir / ".env"))

# Override calendar path for tests
os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    str(_root_dir / "phase1" / "data" / "mock_calendar.json"),
)
