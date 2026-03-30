#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""⚠️  WARNING: DELETES ALL BLOCKS AND THEIR COMMENTS!

Replace entire page content with new content.

⚠️  DANGER: This script deletes ALL blocks, permanently losing ALL comments!
   For safer editing that preserves comments, use sync_page.py instead.

Usage:
    replace_page_content.py <page_id> --markdown "# New Content..." [--yes]
    replace_page_content.py <page_id> --file content.md [--yes]

Examples:
    # Replace with markdown (will prompt for confirmation)
    replace_page_content.py <page_id> --markdown "# Title\nContent"

    # Replace from file (will prompt for confirmation)
    replace_page_content.py <page_id> --file new_content.md

    # Skip confirmation (use with caution!)
    replace_page_content.py <page_id> --file content.md --yes

Safer alternative:
    # Use this to preserve comments on existing blocks
    read_page.py <page_id> --output json > page.json
    # ... edit page.json ...
    sync_page.py <page_id> page.json
"""

import argparse
import json
import sys
from pathlib import Path

from notion_utils import (
    api_call,
    concurrent_deletes,
    get_all_blocks,
    is_interactive,
    load_api_key,
    markdown_to_blocks,
    parse_notion_id,
)


def delete_block(block_id: str, api_key: str):
    """Delete a block."""
    api_call(f"blocks/{block_id}", api_key, "DELETE")


def replace_content(page_id: str, new_blocks: list[dict], api_key: str):
    """Replace entire page content."""

    # Get existing blocks
    print("Getting existing blocks...", file=sys.stderr)
    existing = get_all_blocks(page_id, api_key)

    # Delete all existing blocks concurrently
    if existing:
        print(f"Deleting {len(existing)} existing blocks...", file=sys.stderr)
        block_ids = [b["id"] for b in existing]
        _deleted, failed = concurrent_deletes(block_ids, api_key)
        if failed:
            print(f"  Warning: {failed} blocks failed to delete", file=sys.stderr)

    # Add new content in batches
    print(f"Adding {len(new_blocks)} new blocks...", file=sys.stderr)
    batch_size = 100
    for i in range(0, len(new_blocks), batch_size):
        batch = new_blocks[i : i + batch_size]
        data = {"children": batch}
        response = api_call(f"blocks/{page_id}/children", api_key, "PATCH", data)

        if "object" in response and response["object"] == "error":
            print(f"Error: {response.get('message')}", file=sys.stderr)
            sys.exit(1)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="⚠️  WARNING: DELETES ALL BLOCKS AND COMMENTS!\nReplace entire page content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page_id", help="Page ID")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--markdown", help="Markdown content")
    group.add_argument("--file", help="Markdown file")

    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page_id)

        blocks: list[dict] = []
        if args.markdown:
            blocks = markdown_to_blocks(args.markdown)
        elif args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                sys.exit(1)
            markdown = file_path.read_text()
            blocks = markdown_to_blocks(markdown)

        # Safety confirmation
        if not args.yes:
            if not is_interactive():
                print(
                    "Error: confirmation required. Use --yes to skip in non-interactive mode.",
                    file=sys.stderr,
                )
                sys.exit(1)
            print("\n" + "=" * 70, file=sys.stderr)
            print("⚠️  WARNING: DANGEROUS OPERATION", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            print("\nThis will DELETE ALL BLOCKS and their COMMENTS!", file=sys.stderr)
            print("\n💡 Safer alternative (preserves comments):", file=sys.stderr)
            print("   read_page.py <page_id> --output json > page.json", file=sys.stderr)
            print("   # ... edit page.json ...", file=sys.stderr)
            print("   sync_page.py <page_id> page.json", file=sys.stderr)
            print("\n" + "=" * 70, file=sys.stderr)
            response = input("\nType 'yes' to delete all content and proceed: ")
            if response != "yes":
                print("Cancelled", file=sys.stderr)
                sys.exit(0)
            print("", file=sys.stderr)

        replace_content(page_id, blocks, api_key)

        print(json.dumps({"success": True, "blocks_added": len(blocks)}, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
