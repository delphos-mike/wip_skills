#!/usr/bin/env python3
"""Clear all content from a Notion page.

Usage:
    clear_page.py <page_id>
    clear_page.py <page_url>

Examples:
    # Clear all blocks from page
    clear_page.py 2fd42374-e1fe-80db-88cc-dfcf055f4a9f

    # Clear using URL
    clear_page.py https://notion.so/Page-Title-abc123...

Warning: This will delete ALL blocks from the page!
"""

import argparse
import json
import sys
from typing import Dict, List

from notion_utils import (
    load_api_key,
    parse_notion_id,
    api_call,
    get_all_blocks,
    concurrent_deletes,
    is_interactive,
)


def clear_page(page_id: str, api_key: str):
    """Clear all blocks from a page."""
    print("Getting all blocks from page...", file=sys.stderr)
    blocks = get_all_blocks(page_id, api_key)

    if not blocks:
        print("Page is already empty", file=sys.stderr)
        return {"success": True, "deleted": 0}

    print(f"Deleting {len(blocks)} blocks concurrently...", file=sys.stderr)
    block_ids = [block["id"] for block in blocks]
    deleted, failed = concurrent_deletes(block_ids, api_key)

    return {
        "success": failed == 0,
        "deleted": deleted,
        "failed": failed,
        "total": len(blocks),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Clear all content from a Notion page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page_id", help="Page ID or URL to clear")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page_id)

        # Confirmation (unless --yes or non-interactive)
        if not args.yes:
            if not is_interactive():
                print(
                    "Error: confirmation required. Use --yes to skip in non-interactive mode.",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(
                "WARNING: This will delete ALL blocks from the page!",
                file=sys.stderr,
            )
            response = input("Are you sure? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                print("Cancelled", file=sys.stderr)
                sys.exit(0)

        result = clear_page(page_id, api_key)

        if result["success"]:
            print(
                f"✓ Successfully cleared page ({result['deleted']} blocks deleted)",
                file=sys.stderr,
            )
        else:
            print(
                f"⚠ Partial success: {result['deleted']} deleted, {result['failed']} failed",
                file=sys.stderr,
            )

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
