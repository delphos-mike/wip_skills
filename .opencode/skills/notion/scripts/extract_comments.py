#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""Extract comments from a Notion page.

Usage:
    extract_comments.py <page_url_or_id> [--output <dir>]

Examples:
    extract_comments.py https://www.notion.so/Page-Title-abc123...
    extract_comments.py 2f542374-e1fe-80e9-a480-d59873e7241c
    extract_comments.py <page_id> --output ./output
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from notion_utils import api_call, concurrent_api_calls, get_all_blocks, load_api_key, parse_notion_id


def get_page_info(page_id: str, api_key: str) -> dict[str, Any]:
    """Get page metadata."""
    return api_call(f"pages/{page_id}", api_key)


def get_page_blocks(page_id: str, api_key: str) -> list[dict[str, Any]]:
    """Get all blocks from a page, including nested children.

    Uses get_all_blocks for recursive fetch so comments on nested blocks
    (list children, toggles, table rows, etc.) are not missed.
    """
    all_blocks = get_all_blocks(page_id, api_key)

    # Flatten the recursive tree into a flat list for comment extraction
    flat = []

    def _flatten(blocks):
        for b in blocks:
            flat.append(b)
            if "children" in b:
                _flatten(b["children"])

    _flatten(all_blocks)
    return flat


def extract_text_from_block(block: dict[str, Any]) -> str:
    """Extract readable text from a block."""
    block_type = block.get("type", "")
    block_content = block.get(block_type, {})

    text_parts = []

    # Handle different block types
    if "rich_text" in block_content:
        text_parts = [rt.get("plain_text", "") for rt in block_content["rich_text"]]
    elif "title" in block_content:
        text_parts = [rt.get("plain_text", "") for rt in block_content["title"]]
    elif "caption" in block_content:
        text_parts = [rt.get("plain_text", "") for rt in block_content["caption"]]

    return "".join(text_parts)


def build_comment_link(page_id: str, discussion_id: str) -> str:
    """Build direct link to a comment in Notion.

    Format: https://www.notion.so/<page_id>?p=<discussion_id>&pm=c

    TODO: Verify this format works correctly with Notion's URL structure.
    May need to adjust based on actual Notion behavior.
    """
    # Remove dashes from IDs for URL
    clean_page_id = page_id.replace("-", "")
    clean_discussion_id = discussion_id.replace("-", "")

    return f"https://www.notion.so/{clean_page_id}?p={clean_discussion_id}&pm=c"


def extract_comments(page_id: str, api_key: str, output_dir: Path) -> dict[str, Any]:
    """Extract all comments from a page."""
    print(f"Fetching page info for {page_id}...", file=sys.stderr)
    page_info = get_page_info(page_id, api_key)

    if "object" in page_info and page_info["object"] == "error":
        print(f"Error: {page_info.get('message', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    # Get page title
    page_title = "Untitled"
    if "properties" in page_info:
        for _prop_name, prop_data in page_info["properties"].items():
            if prop_data.get("type") == "title" and prop_data.get("title"):
                page_title = "".join([t.get("plain_text", "") for t in prop_data["title"]])
                break

    print(f"Page: {page_title}", file=sys.stderr)
    print("Fetching blocks...", file=sys.stderr)

    blocks = get_page_blocks(page_id, api_key)
    print(f"Found {len(blocks)} blocks", file=sys.stderr)

    # Save blocks for reference
    safe_title = re.sub(r"[^\w\-]", "_", page_title.lower())[:100]
    blocks_file = output_dir / f"{safe_title}_blocks.json"
    with open(blocks_file, "w") as f:
        json.dump({"results": blocks}, f, indent=2)

    all_comments = []
    blocks_with_comments = 0

    # Fetch page-level comments first (comments not attached to a specific block)
    print("\nFetching page-level comments...", file=sys.stderr)
    page_level_comments = []
    cursor = None
    while True:
        endpoint = f"comments?block_id={page_id}"
        if cursor:
            endpoint += f"&start_cursor={cursor}"
        response = api_call(endpoint, api_key)
        page_level_comments.extend(response.get("results", []))
        if not response.get("has_more", False):
            break
        cursor = response.get("next_cursor")

    if page_level_comments:
        print(f"  Page-level: {len(page_level_comments)} comments", file=sys.stderr)
        for comment in page_level_comments:
            comment_text = "".join([rt.get("plain_text", "") for rt in comment.get("rich_text", [])])
            discussion_id = comment.get("discussion_id")
            comment_link = build_comment_link(page_id, discussion_id) if discussion_id else None
            comment_info = {
                "page_id": page_id,
                "page_title": page_title,
                "block_id": page_id,
                "block_type": "page",
                "block_context": f"[Page: {page_title}]",
                "comment_id": comment.get("id"),
                "comment_text": comment_text,
                "created_by": comment.get("created_by", {}).get("id"),
                "created_time": comment.get("created_time"),
                "last_edited_time": comment.get("last_edited_time"),
                "discussion_id": discussion_id,
                "comment_link": comment_link,
            }
            all_comments.append(comment_info)

    # Fetch block-level comments concurrently
    print(f"Fetching comments for {len(blocks)} blocks concurrently...", file=sys.stderr)

    def fetch_comments_for_block(block):
        """Fetch comments for a single block (runs in thread pool)."""
        block_id = block["id"]
        endpoint = f"comments?block_id={block_id}"
        response = api_call(endpoint, api_key)
        return response.get("results", [])

    results = concurrent_api_calls(blocks, fetch_comments_for_block, max_workers=3, label="blocks")

    for block, comments in results:
        if not comments:
            continue

        blocks_with_comments += 1
        block_id = block["id"]
        block_text = extract_text_from_block(block)
        block_type = block.get("type", "unknown")

        print(f"  Block {block_type}: {len(comments)} comments", file=sys.stderr)

        for comment in comments:
            comment_text = "".join([rt.get("plain_text", "") for rt in comment.get("rich_text", [])])

            discussion_id = comment.get("discussion_id")
            comment_link = build_comment_link(page_id, discussion_id) if discussion_id else None

            comment_info = {
                "page_id": page_id,
                "page_title": page_title,
                "block_id": block_id,
                "block_type": block_type,
                "block_context": block_text,
                "comment_id": comment.get("id"),
                "comment_text": comment_text,
                "created_by": comment.get("created_by", {}).get("id"),
                "created_time": comment.get("created_time"),
                "last_edited_time": comment.get("last_edited_time"),
                "discussion_id": discussion_id,
                "comment_link": comment_link,
            }

            all_comments.append(comment_info)

    page_level_count = len(page_level_comments)
    block_level_count = len(all_comments) - page_level_count
    print(
        f"\n✓ Found {len(all_comments)} comments "
        f"({page_level_count} page-level, {block_level_count} on {blocks_with_comments} blocks)",
        file=sys.stderr,
    )

    # Save comments
    comments_file = output_dir / f"{safe_title}_comments.json"
    with open(comments_file, "w") as f:
        json.dump(all_comments, f, indent=2)

    print(f"✓ Saved to: {comments_file}", file=sys.stderr)

    return {
        "page_id": page_id,
        "page_title": page_title,
        "total_blocks": len(blocks),
        "blocks_with_comments": blocks_with_comments,
        "total_comments": len(all_comments),
        "comments_file": str(comments_file),
        "blocks_file": str(blocks_file),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract comments from a Notion page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page", help="Notion page URL or ID")
    parser.add_argument("--output", "-o", default="/tmp", help="Output directory (default: /tmp)")

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page)
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = extract_comments(page_id, api_key, output_dir)

        # Print summary as JSON for programmatic use
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
