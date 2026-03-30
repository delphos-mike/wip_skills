"""Integration tests: database queries and property updates.

The test page (32242374...) lives in database 13e42374... which has properties:
  Name (title), Summary (rich_text), Type (multi_select), Decision (rich_text),
  Approved By (rich_text), Predecessor (rich_text), Author (people),
  Created time, Last edited time, Created By.
"""

from notion_utils import api_call
from query_database import extract_property_value, query_database
from update_page_property import build_property_update, get_page_property_schema

# ── Helpers ──────────────────────────────────────────────────────────


def _get_page_property(api_key: str, page_id: str, prop_name: str) -> dict:
    """Fetch a single property from a page."""
    page = api_call(f"pages/{page_id}", api_key)
    return page["properties"].get(prop_name, {})


def _update_properties(api_key: str, page_id: str, props: dict) -> dict:
    """Update page properties via the API."""
    return api_call(
        f"pages/{page_id}",
        api_key,
        method="PATCH",
        data={"properties": props},
    )


# ── Database Query Tests ─────────────────────────────────────────────


class TestDatabaseQuery:
    def test_query_returns_results(self, api_key, database_id):
        results = query_database(database_id, api_key)
        assert len(results) > 0

    def test_query_results_have_properties(self, api_key, database_id):
        results = query_database(database_id, api_key)
        page = results[0]
        assert "properties" in page
        assert "Name" in page["properties"]

    def test_query_finds_test_page(self, api_key, database_id, page_id):
        results = query_database(database_id, api_key)
        ids = [r["id"] for r in results]
        assert page_id in ids

    def test_query_with_filter(self, api_key, database_id):
        """Filter by the test page's known Summary text."""
        filter_body = {
            "property": "Summary",
            "rich_text": {"contains": "unit testing"},
        }
        results = query_database(database_id, api_key, filter_body=filter_body)
        assert len(results) >= 1

        # Should include our test page
        titles = []
        for r in results:
            title_prop = r["properties"].get("Name", {})
            titles.append(extract_property_value(title_prop))
        assert any("Testing Ground" in t for t in titles)


class TestExtractPropertyValue:
    """Test the property value extraction helper against real data."""

    def test_extract_title(self, api_key, page_id):
        prop = _get_page_property(api_key, page_id, "Name")
        value = extract_property_value(prop)
        assert "Testing Ground" in value

    def test_extract_rich_text(self, api_key, page_id):
        prop = _get_page_property(api_key, page_id, "Summary")
        value = extract_property_value(prop)
        assert "unit testing" in value.lower()

    def test_extract_multi_select(self, api_key, page_id):
        prop = _get_page_property(api_key, page_id, "Type")
        value = extract_property_value(prop)
        assert "Documentation" in value

    def test_extract_created_time(self, api_key, page_id):
        prop = _get_page_property(api_key, page_id, "Created time")
        value = extract_property_value(prop)
        # Verify it's a valid ISO-8601 timestamp (not empty)
        assert len(value) >= 10  # at least "YYYY-MM-DD"
        assert "-" in value


# ── Property Update Tests ────────────────────────────────────────────


class TestPropertyUpdates:
    """Test setting and clearing properties on the test page.

    Each test restores the original value after modifying it.
    """

    def test_update_rich_text(self, api_key, page_id):
        """Set Decision, verify, then clear it."""
        # Set
        update = build_property_update("Decision", "rich_text", "Test decision value")
        _update_properties(api_key, page_id, {"Decision": update})

        # Verify
        prop = _get_page_property(api_key, page_id, "Decision")
        assert extract_property_value(prop) == "Test decision value"

        # Clear
        clear = build_property_update("Decision", "rich_text", "")
        _update_properties(api_key, page_id, {"Decision": clear})

        prop = _get_page_property(api_key, page_id, "Decision")
        assert extract_property_value(prop) == ""

    def test_update_multiple_properties(self, api_key, page_id):
        """Set multiple properties in one call."""
        updates = {
            "Decision": build_property_update("Decision", "rich_text", "Multi-update test"),
            "Approved By": build_property_update("Approved By", "rich_text", "pytest"),
        }
        _update_properties(api_key, page_id, updates)

        decision = _get_page_property(api_key, page_id, "Decision")
        approved = _get_page_property(api_key, page_id, "Approved By")
        assert extract_property_value(decision) == "Multi-update test"
        assert extract_property_value(approved) == "pytest"

        # Clean up
        clear = {
            "Decision": build_property_update("Decision", "rich_text", ""),
            "Approved By": build_property_update("Approved By", "rich_text", ""),
        }
        _update_properties(api_key, page_id, clear)

    def test_schema_detection(self, api_key, page_id):
        """get_page_property_schema returns type info for all properties."""
        schema = get_page_property_schema(page_id, api_key)

        assert "Name" in schema
        assert schema["Name"]["type"] == "title"
        assert "Summary" in schema
        assert schema["Summary"]["type"] == "rich_text"
        assert "Type" in schema
        assert schema["Type"]["type"] == "multi_select"
