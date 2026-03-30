#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""⚠️  WARNING: DELETES ALL BLOCKS AND THEIR COMMENTS!

Update a page from edited JSON structure.

⚠️  DANGER: This script deletes ALL blocks, permanently losing ALL comments!
   For safer editing that preserves comments, use sync_page.py instead.

Workflow:
    1. read_page.py <page_id> --output json > page.json
    2. Edit page.json locally (fast)
    3. update_from_json.py <page_id> page.json [--yes]

Usage:
    update_from_json.py <page_id> <json_file> [--yes]

Examples:
    # Pull, edit, push workflow (will prompt for confirmation)
    read_page.py <page_id> --output json > page.json
    # ... edit page.json ...
    update_from_json.py <page_id> page.json

    # Skip confirmation (use with caution!)
    update_from_json.py <page_id> page.json --yes

Safer alternative (preserves comments):
    sync_page.py <page_id> page.json
"""

import argparse
import json
import sys
from pathlib import Path

from notion_utils import api_call, get_all_blocks, is_interactive, load_api_key, parse_notion_id


def delete_block(block_id: str, api_key: str):
    api_call(f"blocks/{block_id}", api_key, "DELETE")


def clean_block(block: dict) -> dict:
    """Clean block for creation (remove read-only fields)."""
    cleaned = {"object": "block", "type": block["type"]}

    # Copy type-specific content
    block_type = block["type"]
    if block_type in block:
        content = block[block_type].copy()

        # Remove read-only fields
        content.pop("color", None)  # Color is read-only in some contexts

        cleaned[block_type] = content

    # Handle children recursively
    if block.get("has_children") and "children" in block:
        cleaned[block_type]["children"] = [clean_block(child) for child in block["children"]]

    return cleaned


def update_page(page_id: str, blocks: list[dict], api_key: str):
    """Replace page content with new blocks."""

    # Get and delete existing blocks
    print("Getting existing blocks...", file=sys.stderr)
    existing = get_all_blocks(page_id, api_key)

    print(f"Deleting {len(existing)} existing blocks...", file=sys.stderr)
    for block in existing:
        delete_block(block["id"], api_key)

    # Clean blocks for creation
    print(f"Preparing {len(blocks)} new blocks...", file=sys.stderr)
    cleaned_blocks = [clean_block(block) for block in blocks]

    # Add new blocks in batches
    print("Adding new blocks...", file=sys.stderr)
    batch_size = 100
    for i in range(0, len(cleaned_blocks), batch_size):
        batch = cleaned_blocks[i : i + batch_size]
        data = {"children": batch}
        response = api_call(f"blocks/{page_id}/children", api_key, "PATCH", data)

        if "object" in response and response["object"] == "error":
            print(f"Error: {response.get('message')}", file=sys.stderr)
            sys.exit(1)

        print(f"  Added batch {i // batch_size + 1} ({len(batch)} blocks)", file=sys.stderr)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="⚠️  WARNING: DELETES ALL BLOCKS AND COMMENTS!\nUpdate page from edited JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page_id", help="Page ID")
    parser.add_argument("json_file", help="JSON file with blocks")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page_id)

        json_path = Path(args.json_file)
        if not json_path.exists():
            print(f"Error: File not found: {json_path}", file=sys.stderr)
            sys.exit(1)

        # Load JSON
        with open(json_path) as f:
            data = json.load(f)

        # Extract blocks (support different formats)
        if isinstance(data, list):
            blocks = data
        elif "blocks" in data:
            blocks = data["blocks"]
        elif "results" in data:
            blocks = data["results"]
        else:
            print("Error: JSON must be array of blocks or contain 'blocks' key", file=sys.stderr)
            sys.exit(1)

        print(f"Loaded {len(blocks)} blocks from {json_path}", file=sys.stderr)

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
            print(f"   sync_page.py {page_id} {json_path}", file=sys.stderr)
            print("\n" + "=" * 70, file=sys.stderr)
            response = input("\nType 'yes' to delete all content and proceed: ")
            if response != "yes":
                print("Cancelled", file=sys.stderr)
                sys.exit(0)
            print("", file=sys.stderr)

        update_page(page_id, blocks, api_key)

        print(json.dumps({"success": True, "blocks_updated": len(blocks), "page_id": page_id}, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
