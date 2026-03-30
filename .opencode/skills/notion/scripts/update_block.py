#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""Update an existing Notion block.

Usage:
    update_block.py <block_id> --text "new content"
    update_block.py <block_id> --file content.txt

Examples:
    # Update paragraph text
    update_block.py <block_id> --text "Updated content"

    # Update from file
    update_block.py <block_id> --file content.txt
"""

import argparse
import json
import sys
from pathlib import Path

from notion_utils import (
    api_call,
    create_rich_text,
    load_api_key,
    parse_notion_id,
)


def update_block(block_id: str, content: str, api_key: str, block_type: str | None = None):
    """Update an existing block."""

    # Get current block to determine type
    block = api_call(f"blocks/{block_id}", api_key)

    if "object" in block and block["object"] == "error":
        print(f"Error: {block.get('message', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    current_type = block.get("type", "paragraph")

    # Use specified type or keep current
    update_type = block_type or current_type

    # Build update payload based on type
    if update_type == "paragraph":
        data = {"paragraph": {"rich_text": create_rich_text(content)}}
    elif update_type.startswith("heading_"):
        data = {update_type: {"rich_text": create_rich_text(content)}}
    elif update_type == "bulleted_list_item":
        data = {"bulleted_list_item": {"rich_text": create_rich_text(content)}}
    elif update_type == "numbered_list_item":
        data = {"numbered_list_item": {"rich_text": create_rich_text(content)}}
    elif update_type == "to_do":
        # Preserve checked state
        checked = block.get(update_type, {}).get("checked", False)
        data = {"to_do": {"rich_text": create_rich_text(content), "checked": checked}}
    elif update_type == "quote":
        data = {"quote": {"rich_text": create_rich_text(content)}}
    elif update_type == "code":
        language = block.get(update_type, {}).get("language", "plain text")
        data = {"code": {"rich_text": create_rich_text(content), "language": language}}
    else:
        data = {"paragraph": {"rich_text": create_rich_text(content)}}

    # Update block
    response = api_call(f"blocks/{block_id}", api_key, "PATCH", data)

    if "object" in response and response["object"] == "error":
        print(f"Error: {response.get('message', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    return response


def main():
    parser = argparse.ArgumentParser(
        description="Update existing Notion block",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("block_id", help="Block ID to update")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="New text content")
    group.add_argument("--file", help="File with new content")

    parser.add_argument("--type", help="Block type (paragraph, heading_1, etc.)")

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        block_id = parse_notion_id(args.block_id)

        content = ""
        if args.text:
            content = args.text
        elif args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                sys.exit(1)
            content = file_path.read_text().strip()

        print(f"Updating block {block_id}...", file=sys.stderr)
        update_block(block_id, content, api_key, args.type)

        print(json.dumps({"success": True, "block_id": block_id}, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
