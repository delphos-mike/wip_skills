"""Root conftest — adds scripts/ and tests/integration/ to sys.path."""

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
INTEGRATION_DIR = Path(__file__).parent / "integration"

# Make `from notion_utils import ...` work in tests
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Make `from helpers import ...` work in integration tests
if str(INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_DIR))
