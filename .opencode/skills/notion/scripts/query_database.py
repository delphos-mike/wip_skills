#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""Query a Notion database and display results.

Fetches all pages from a database with their properties. Supports filtering
by property values and output in table or JSON format.

Usage:
    query_database.py <database_url_or_id> [--output table|json]
    query_database.py <database_url_or_id> --filter "Status=Done"
    query_database.py <database_url_or_id> --empty Summary
    query_database.py <database_url_or_id> --not-empty Summary

Examples:
    # List all entries with their properties
    query_database.py 13e42374e1fe810b888ef967fd209a0b

    # JSON output with page IDs (useful for scripting)
    query_database.py 13e42374e1fe810b888ef967fd209a0b --output json

    # Find entries where Summary is empty
    query_database.py 13e42374e1fe810b888ef967fd209a0b --empty Summary

    # Find entries where Status equals "Done"
    query_database.py 13e42374e1fe810b888ef967fd209a0b --filter "Status=Done"
"""

import argparse
import json
import sys
from typing import Any

from notion_utils import api_call, load_api_key, parse_notion_id


def extract_property_value(prop: dict[str, Any]) -> str:
    """Extract a human-readable value from a Notion property object."""
    prop_type = prop.get("type", "")

    if prop_type == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    elif prop_type == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    elif prop_type == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    elif prop_type == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    elif prop_type == "multi_select":
        return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
    elif prop_type == "status":
        status = prop.get("status")
        return status.get("name", "") if status else ""
    elif prop_type == "checkbox":
        return str(prop.get("checkbox", False))
    elif prop_type == "date":
        date = prop.get("date")
        if date:
            start = date.get("start", "")
            end = date.get("end", "")
            return f"{start} → {end}" if end else start
        return ""
    elif prop_type == "url":
        return prop.get("url", "") or ""
    elif prop_type == "email":
        return prop.get("email", "") or ""
    elif prop_type == "phone_number":
        return prop.get("phone_number", "") or ""
    elif prop_type == "people":
        return ", ".join(p.get("name", p.get("id", "")) for p in prop.get("people", []))
    elif prop_type == "relation":
        return f"({len(prop.get('relation', []))} relations)"
    elif prop_type == "rollup":
        rollup = prop.get("rollup", {})
        rollup_type = rollup.get("type", "")
        if rollup_type == "number":
            return str(rollup.get("number", ""))
        elif rollup_type == "array":
            return f"({len(rollup.get('array', []))} items)"
        return ""
    elif prop_type == "formula":
        formula = prop.get("formula", {})
        formula_type = formula.get("type", "")
        return str(formula.get(formula_type, ""))
    elif prop_type == "created_time":
        return prop.get("created_time", "")
    elif prop_type == "last_edited_time":
        return prop.get("last_edited_time", "")
    elif prop_type == "created_by":
        user = prop.get("created_by", {})
        return user.get("name", user.get("id", ""))
    elif prop_type == "last_edited_by":
        user = prop.get("last_edited_by", {})
        return user.get("name", user.get("id", ""))
    elif prop_type == "files":
        files = prop.get("files", [])
        return ", ".join(f.get("name", "") for f in files)
    elif prop_type == "unique_id":
        uid = prop.get("unique_id", {})
        prefix = uid.get("prefix", "")
        number = uid.get("number", "")
        return f"{prefix}-{number}" if prefix else str(number)
    else:
        return f"({prop_type})"


def get_title_property_name(properties: dict[str, Any]) -> str:
    """Find the property name that has type 'title' (every DB has exactly one)."""
    for name, prop in properties.items():
        if prop.get("type") == "title":
            return name
    return "Name"  # fallback


def query_database(
    database_id: str,
    api_key: str,
    filter_body: dict | None = None,
) -> list[dict[str, Any]]:
    """Query a Notion database, handling pagination.

    Args:
        database_id: Database UUID
        api_key: Notion API key
        filter_body: Optional Notion filter object

    Returns:
        List of page objects with properties
    """
    all_results = []
    start_cursor = None

    while True:
        body: dict[str, Any] = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        if filter_body:
            body["filter"] = filter_body

        response = api_call(f"databases/{database_id}/query", api_key, "POST", body)

        results = response.get("results", [])
        all_results.extend(results)

        if not response.get("has_more", False):
            break
        start_cursor = response.get("next_cursor")

    return all_results


def format_table(pages: list[dict[str, Any]], properties_to_show: list[str] | None = None) -> str:
    """Format query results as a text table."""
    if not pages:
        return "No results found."

    # Determine which properties to show
    all_props = list(pages[0].get("properties", {}).keys())

    # Find the title property and put it first
    title_prop = get_title_property_name(pages[0].get("properties", {}))

    if properties_to_show:
        prop_names = properties_to_show
    else:
        # Title first, then alphabetical
        prop_names = [title_prop, *sorted(p for p in all_props if p != title_prop)]

    # Build rows
    rows = []
    for page in pages:
        row = {}
        for prop_name in prop_names:
            prop = page.get("properties", {}).get(prop_name, {})
            row[prop_name] = extract_property_value(prop)
        rows.append(row)

    # Calculate column widths
    col_widths = {}
    for prop_name in prop_names:
        max_val_len = max(len(row.get(prop_name, "")) for row in rows) if rows else 0
        col_widths[prop_name] = max(len(prop_name), min(max_val_len, 80))

    # Format header
    header = " | ".join(prop_name.ljust(col_widths[prop_name]) for prop_name in prop_names)
    separator = "-+-".join("-" * col_widths[prop_name] for prop_name in prop_names)

    # Format rows
    formatted_rows = []
    for row in rows:
        formatted = " | ".join(
            row.get(prop_name, "").ljust(col_widths[prop_name])[: col_widths[prop_name]] for prop_name in prop_names
        )
        formatted_rows.append(formatted)

    return "\n".join([header, separator, *formatted_rows])


def format_json(pages: list[dict[str, Any]]) -> str:
    """Format query results as JSON with extracted property values."""
    results = []
    for page in pages:
        entry = {
            "id": page["id"],
            "url": page.get("url", ""),
            "properties": {},
        }
        for prop_name, prop in page.get("properties", {}).items():
            entry["properties"][prop_name] = extract_property_value(prop)
        results.append(entry)
    return json.dumps(results, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Query a Notion database and display results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("database_id", help="Database URL or ID")
    parser.add_argument(
        "--output",
        "-o",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--filter",
        "-f",
        action="append",
        help='Filter by property value: "PropertyName=Value" (can be repeated)',
    )
    parser.add_argument(
        "--empty",
        action="append",
        help="Find entries where this property is empty (can be repeated)",
    )
    parser.add_argument(
        "--not-empty",
        action="append",
        help="Find entries where this property is not empty (can be repeated)",
    )
    parser.add_argument(
        "--props",
        "-p",
        help="Comma-separated list of properties to display",
    )

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        database_id = parse_notion_id(args.database_id)

        # Build filter if specified
        # Note: Notion filters require knowing the property type. We fetch the
        # database schema first to determine types for user-specified filters.
        filter_body = None
        filter_conditions = []

        if args.filter or args.empty or args.not_empty:
            # Fetch database schema to get property types
            db_info = api_call(f"databases/{database_id}", api_key)
            db_properties = db_info.get("properties", {})

            if args.filter:
                for f in args.filter:
                    if "=" not in f:
                        print(
                            f'Error: Filter must be "PropertyName=Value", got: {f}',
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    prop_name, value = f.split("=", 1)
                    prop_schema = db_properties.get(prop_name)
                    if not prop_schema:
                        print(
                            f"Error: Property '{prop_name}' not found. Available: {', '.join(db_properties.keys())}",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    prop_type = prop_schema["type"]
                    condition = _build_equals_filter(prop_name, prop_type, value)
                    if condition:
                        filter_conditions.append(condition)

            if args.empty:
                for prop_name in args.empty:
                    prop_schema = db_properties.get(prop_name)
                    if not prop_schema:
                        print(
                            f"Error: Property '{prop_name}' not found. Available: {', '.join(db_properties.keys())}",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    prop_type = prop_schema["type"]
                    condition = _build_empty_filter(prop_name, prop_type, is_empty=True)
                    if condition:
                        filter_conditions.append(condition)

            if args.not_empty:
                for prop_name in args.not_empty:
                    prop_schema = db_properties.get(prop_name)
                    if not prop_schema:
                        print(
                            f"Error: Property '{prop_name}' not found. Available: {', '.join(db_properties.keys())}",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    prop_type = prop_schema["type"]
                    condition = _build_empty_filter(prop_name, prop_type, is_empty=False)
                    if condition:
                        filter_conditions.append(condition)

            if len(filter_conditions) == 1:
                filter_body = filter_conditions[0]
            elif len(filter_conditions) > 1:
                filter_body = {"and": filter_conditions}

        # Query
        print(f"Querying database {database_id}...", file=sys.stderr)
        pages = query_database(database_id, api_key, filter_body)
        print(f"Found {len(pages)} results.", file=sys.stderr)

        # Parse properties to show
        properties_to_show = None
        if args.props:
            properties_to_show = [p.strip() for p in args.props.split(",")]

        # Output
        if args.output == "json":
            print(format_json(pages))
        else:
            print(format_table(pages, properties_to_show))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def _build_equals_filter(prop_name: str, prop_type: str, value: str) -> dict | None:
    """Build a Notion filter condition for equality check."""
    if prop_type == "rich_text":
        return {"property": prop_name, "rich_text": {"equals": value}}
    elif prop_type == "title":
        return {"property": prop_name, "title": {"equals": value}}
    elif prop_type == "select":
        return {"property": prop_name, "select": {"equals": value}}
    elif prop_type == "status":
        return {"property": prop_name, "status": {"equals": value}}
    elif prop_type == "checkbox":
        return {"property": prop_name, "checkbox": {"equals": value.lower() == "true"}}
    elif prop_type == "number":
        return {"property": prop_name, "number": {"equals": float(value)}}
    elif prop_type == "multi_select":
        return {"property": prop_name, "multi_select": {"contains": value}}
    else:
        print(
            f"Warning: Filtering on '{prop_type}' properties is not yet supported. Skipping.",
            file=sys.stderr,
        )
        return None


def _build_empty_filter(prop_name: str, prop_type: str, is_empty: bool) -> dict | None:
    """Build a Notion filter condition for empty/not-empty check.

    Notion API uses separate keys: is_empty: true vs is_not_empty: true.
    You cannot use is_empty: false.
    """
    empty_clause = {"is_empty": True} if is_empty else {"is_not_empty": True}

    if prop_type == "rich_text":
        return {"property": prop_name, "rich_text": empty_clause}
    elif prop_type == "title":
        return {"property": prop_name, "title": empty_clause}
    elif prop_type == "select":
        return {"property": prop_name, "select": empty_clause}
    elif prop_type == "status":
        return {"property": prop_name, "status": empty_clause}
    elif prop_type == "number":
        return {"property": prop_name, "number": empty_clause}
    elif prop_type == "date":
        return {"property": prop_name, "date": empty_clause}
    elif prop_type == "files":
        return {"property": prop_name, "files": empty_clause}
    elif prop_type == "relation":
        return {"property": prop_name, "relation": empty_clause}
    elif prop_type == "people":
        return {"property": prop_name, "people": empty_clause}
    elif prop_type == "checkbox":
        return {"property": prop_name, "checkbox": {"equals": not is_empty}}
    else:
        print(
            f"Warning: Empty filter on '{prop_type}' not supported. Skipping.",
            file=sys.stderr,
        )
        return None


if __name__ == "__main__":
    main()
