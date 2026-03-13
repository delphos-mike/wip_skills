#!/usr/bin/env python3
"""Append blocks to a Notion page.

Usage:
    append_blocks.py <page_url_or_id> --text "content"
    append_blocks.py <page_url_or_id> --markdown "# Heading\nContent"
    append_blocks.py <page_url_or_id> --file content.md

Examples:
    # Append paragraph
    append_blocks.py <page_id> --text "New paragraph"

    # Append from markdown
    append_blocks.py <page_id> --markdown "## Section\n- Item 1\n- Item 2"

    # Append from file
    append_blocks.py <page_id> --file notes.md

    # Multiple blocks
    echo '{"blocks": [...]}' | append_blocks.py <page_id> --json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

from notion_utils import (
    load_api_key,
    parse_notion_id,
    api_call,
    markdown_to_blocks,
    create_rich_text,
)


def append_blocks(page_id: str, blocks: List[Dict[str, Any]], api_key: str):
    """Append blocks to a page."""
    if not blocks:
        return {"object": "list", "results": []}

    # Notion API allows max 100 blocks per request
    batch_size = 100
    response = None

    for i in range(0, len(blocks), batch_size):
        batch = blocks[i : i + batch_size]

        data = {"children": batch}
        response = api_call(f"blocks/{page_id}/children", api_key, "PATCH", data)

        if "object" in response and response["object"] == "error":
            print(f"Error: {response.get('message', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)

        print(f"Appended {len(batch)} blocks", file=sys.stderr)

    return response


def main():
    parser = argparse.ArgumentParser(
        description="Append blocks to a Notion page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page", help="Notion page URL or ID")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Plain text to append as paragraph")
    group.add_argument("--markdown", help="Markdown content to append")
    group.add_argument("--file", help="Markdown file to append")
    group.add_argument("--json", action="store_true", help="Read block JSON from stdin")

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page)

        # Determine blocks to append
        blocks: List[Dict[str, Any]] = []
        if args.text:
            blocks = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": create_rich_text(args.text)},
                }
            ]

        elif args.markdown:
            blocks = markdown_to_blocks(args.markdown)

        elif args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                sys.exit(1)
            markdown = file_path.read_text()
            blocks = markdown_to_blocks(markdown)

        elif args.json:
            data = json.load(sys.stdin)
            blocks = data.get("blocks", [])

        print(f"Appending {len(blocks)} blocks to page...", file=sys.stderr)
        result = append_blocks(page_id, blocks, api_key)

        # Output result
        print(
            json.dumps(
                {"success": True, "blocks_added": len(blocks), "page_id": page_id},
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
