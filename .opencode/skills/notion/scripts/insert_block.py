#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""Insert a block at a specific position in a page.

Usage:
    insert_block.py <page_or_block_id> --text "content" [--after block_id]
    insert_block.py <page_or_block_id> --markdown "# Heading" [--after block_id]
    insert_block.py <page_or_block_id> --file content.md [--position 0]

Examples:
    # Insert at end of page
    insert_block.py <page_id> --text "New content"

    # Insert after specific block
    insert_block.py <page_id> --text "New content" --after <block_id>

    # Insert at specific position (0-indexed)
    insert_block.py <page_id> --markdown "## New Section" --position 2
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from notion_utils import (
    api_call,
    create_rich_text,
    load_api_key,
    markdown_to_blocks,
    parse_notion_id,
)


def insert_blocks(
    parent_id: str,
    blocks: list[dict],
    api_key: str,
    after_block_id: str | None = None,
    position: int | None = None,
):
    """Insert blocks at a specific position.

    Uses the Notion API 'after' parameter to insert blocks after a specific block,
    making them siblings (not children) of the target block.
    """

    if position is not None:
        # Get existing blocks to find insertion point (paginate for >100)
        existing_blocks = []
        cursor = None
        while True:
            endpoint = f"blocks/{parent_id}/children?page_size=100"
            if cursor:
                endpoint += f"&start_cursor={cursor}"
            resp = api_call(endpoint, api_key)
            existing_blocks.extend(resp.get("results", []))
            if not resp.get("has_more") or (position > 0 and len(existing_blocks) >= position):
                break
            cursor = resp.get("next_cursor")

        if position >= 0 and position <= len(existing_blocks):
            if position > 0:
                after_block_id = existing_blocks[position - 1]["id"]
            # position == 0 means insert at top; leave after_block_id as None

    # Build request data
    data: dict[str, Any] = {"children": blocks}
    if after_block_id:
        data["after"] = after_block_id

    # Always append to parent (use 'after' param for positioning)
    response = api_call(f"blocks/{parent_id}/children", api_key, "PATCH", data)

    if "object" in response and response["object"] == "error":
        print(f"Error: {response.get('message', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    return response


def main():
    parser = argparse.ArgumentParser(
        description="Insert block at specific position",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("parent", help="Page or block ID")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Plain text to insert")
    group.add_argument("--markdown", help="Markdown content")
    group.add_argument("--file", help="Markdown file")

    parser.add_argument("--after", help="Insert after this block ID")
    parser.add_argument("--position", type=int, help="Insert at position (0-indexed)")

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        parent_id = parse_notion_id(args.parent)

        blocks: list[dict] = []
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

        after_id = parse_notion_id(args.after) if args.after else None

        print(f"Inserting {len(blocks)} blocks...", file=sys.stderr)
        insert_blocks(parent_id, blocks, api_key, after_id, args.position)

        print(json.dumps({"success": True, "blocks_inserted": len(blocks)}, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
