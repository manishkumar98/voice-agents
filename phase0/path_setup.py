"""
path_setup.py

Adds every completed phase's root directory to sys.path so that
cross-phase imports work from any entry point (app.py, console.py,
internal_dashboard.py, training_set.py, tests, etc.).

Import this as the FIRST thing in any entry point:

    import path_setup  # must be before any from src.xxx import

After this runs:
    from src.agent.rag_injector import ...    # phase0
    from src.booking.slot_resolver import ... # phase1
    from src.dialogue.fsm import ...          # phase2
    from config.settings import settings      # phase0/config
are all valid.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))   # .../voice-agents/phase0/
_ROOT = os.path.dirname(_HERE)                         # .../voice-agents/

_PHASES = ["phase0", "phase1", "phase2"]

for _phase in _PHASES:
    _path = os.path.join(_ROOT, _phase)
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

# Default MOCK_CALENDAR_PATH so slot_resolver finds mock data
os.environ.setdefault(
    "MOCK_CALENDAR_PATH",
    os.path.join(_ROOT, "phase1", "data", "mock_calendar.json"),
)
