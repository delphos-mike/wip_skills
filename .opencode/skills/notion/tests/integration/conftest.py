"""Integration test fixtures.

All integration tests run against a real Notion page:
  "Notion Skill - Testing Ground"
  https://www.notion.so/Notion-Skill-Testing-Ground-32242374e1fe80508849c6301f59179c

The page lives in database 13e42374-e1fe-810b-888e-f967fd209a0b and has
properties: Name, Summary, Type, Decision, Approved By, etc.
"""

import pytest
from helpers import clear_page
from notion_utils import load_api_key

# ── Constants ────────────────────────────────────────────────────────

TEST_PAGE_ID = "32242374-e1fe-8050-8849-c6301f59179c"
TEST_DATABASE_ID = "13e42374-e1fe-810b-888e-f967fd209a0b"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def api_key():
    """Load Notion API key (env var -> cached file -> 1Password)."""
    return load_api_key()


@pytest.fixture(scope="session")
def page_id():
    """The test page ID."""
    return TEST_PAGE_ID


@pytest.fixture(scope="session")
def database_id():
    """The parent database ID."""
    return TEST_DATABASE_ID


@pytest.fixture(autouse=True)
def clear_test_page(api_key, page_id):
    """Clear the test page before each test."""
    clear_page(api_key, page_id)
    yield
