#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""Update properties on a Notion database page.

Modifies one or more properties on a page (database entry). Supports text,
number, select, checkbox, URL, and date properties.

Usage:
    update_page_property.py <page_url_or_id> --set "PropertyName=Value" [--set ...]

Examples:
    # Set a rich_text property
    update_page_property.py <page_id> --set "Summary=This is a summary"

    # Set multiple properties at once
    update_page_property.py <page_id> --set "Status=Done" --set "Priority=High"

    # Set a checkbox
    update_page_property.py <page_id> --set "Reviewed=true"

    # Set a number
    update_page_property.py <page_id> --set "Score=95"

    # Clear a property (set to empty)
    update_page_property.py <page_id> --set "Summary="
"""

import argparse
import json
import sys
from typing import Any

from notion_utils import api_call, load_api_key, parse_notion_id


def get_page_property_schema(page_id: str, api_key: str) -> dict[str, dict]:
    """Fetch the page and return its property schemas with types.

    We get the page object which includes property metadata. For database
    pages, each property has a type field we can use to build the update.
    """
    page = api_call(f"pages/{page_id}", api_key)
    return page.get("properties", {})


def build_property_update(
    prop_name: str,
    prop_type: str,
    value: str,
) -> dict[str, Any] | None:
    """Build the Notion API property update payload for a given type.

    Args:
        prop_name: Property name
        prop_type: Notion property type
        value: String value to set

    Returns:
        Property update dict, or None if type is unsupported
    """
    if prop_type == "rich_text":
        if not value:
            return {"rich_text": []}
        return {"rich_text": [{"text": {"content": value}}]}

    elif prop_type == "title":
        if not value:
            return {"title": []}
        return {"title": [{"text": {"content": value}}]}

    elif prop_type == "number":
        if not value:
            return {"number": None}
        return {"number": float(value)}

    elif prop_type == "select":
        if not value:
            return {"select": None}
        return {"select": {"name": value}}

    elif prop_type == "multi_select":
        if not value:
            return {"multi_select": []}
        names = [n.strip() for n in value.split(",")]
        return {"multi_select": [{"name": n} for n in names]}

    elif prop_type == "status":
        if not value:
            return {"status": None}
        return {"status": {"name": value}}

    elif prop_type == "checkbox":
        return {"checkbox": value.lower() in ("true", "1", "yes")}

    elif prop_type == "url":
        if not value:
            return {"url": None}
        return {"url": value}

    elif prop_type == "email":
        if not value:
            return {"email": None}
        return {"email": value}

    elif prop_type == "phone_number":
        if not value:
            return {"phone_number": None}
        return {"phone_number": value}

    elif prop_type == "date":
        if not value:
            return {"date": None}
        # Support "start" or "start→end" format
        if "→" in value:
            start, end = value.split("→", 1)
            return {"date": {"start": start.strip(), "end": end.strip()}}
        return {"date": {"start": value.strip()}}

    else:
        print(
            f"Warning: Setting '{prop_type}' properties is not supported. Skipping '{prop_name}'.",
            file=sys.stderr,
        )
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Update properties on a Notion database page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page_id", help="Page URL or ID")
    parser.add_argument(
        "--set",
        "-s",
        action="append",
        required=True,
        dest="updates",
        help='Property to set: "PropertyName=Value" (can be repeated)',
    )

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page_id)

        # Parse updates
        updates = []
        for update_str in args.updates:
            if "=" not in update_str:
                print(
                    f'Error: Update must be "PropertyName=Value", got: {update_str}',
                    file=sys.stderr,
                )
                sys.exit(1)
            prop_name, value = update_str.split("=", 1)
            updates.append((prop_name.strip(), value))

        # Fetch current property schemas to determine types
        print("Fetching page properties...", file=sys.stderr)
        properties = get_page_property_schema(page_id, api_key)

        # Build the update payload
        property_updates = {}
        for prop_name, value in updates:
            if prop_name not in properties:
                print(
                    f"Error: Property '{prop_name}' not found on this page. Available: {', '.join(properties.keys())}",
                    file=sys.stderr,
                )
                sys.exit(1)

            prop_type = properties[prop_name].get("type", "")
            update = build_property_update(prop_name, prop_type, value)
            if update is not None:
                property_updates[prop_name] = update

        if not property_updates:
            print("No valid property updates to apply.", file=sys.stderr)
            sys.exit(1)

        # Apply the update
        print(
            f"Updating {len(property_updates)} properties on page {page_id}...",
            file=sys.stderr,
        )
        result = api_call(
            f"pages/{page_id}",
            api_key,
            "PATCH",
            {"properties": property_updates},
        )

        # Verify and report
        updated_props = {}
        for prop_name in property_updates:
            prop = result.get("properties", {}).get(prop_name, {})
            prop_type = prop.get("type", "")

            # Extract the value to confirm
            if prop_type == "rich_text":
                val = "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
            elif prop_type == "title":
                val = "".join(t.get("plain_text", "") for t in prop.get("title", []))
            elif prop_type == "select":
                sel = prop.get("select")
                val = sel.get("name", "") if sel else "(empty)"
            elif prop_type == "status":
                status = prop.get("status")
                val = status.get("name", "") if status else "(empty)"
            elif prop_type == "checkbox":
                val = str(prop.get("checkbox", False))
            elif prop_type == "number":
                val = str(prop.get("number", ""))
            else:
                val = "(updated)"
            updated_props[prop_name] = val

        print(
            json.dumps(
                {"success": True, "page_id": page_id, "updated": updated_props},
                indent=2,
            )
        )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
