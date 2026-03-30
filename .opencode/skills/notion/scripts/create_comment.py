#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""Create a comment on a Notion page or block.

Creates page-level or block-level comments. To reply to an existing
discussion thread, use reply_to_comment.py instead.

Usage:
    create_comment.py <page_url_or_id> "Comment text"
    create_comment.py <page_url_or_id> --file comment.txt
    create_comment.py --block <block_id> "Comment text"

Examples:
    # Page-level comment
    create_comment.py https://www.notion.so/My-Page-abc123 "Looks good!"

    # Block-level comment (attaches to a specific block)
    create_comment.py --block def456 "This paragraph needs revision"

    # Comment from file
    create_comment.py abc123 --file review_notes.txt
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from notion_utils import api_call, create_rich_text, load_api_key, parse_notion_id


def create_comment(
    api_key: str,
    text: str,
    page_id: str | None = None,
    block_id: str | None = None,
    discussion_id: str | None = None,
) -> dict[str, Any]:
    """Create a comment on a Notion page, block, or discussion thread.

    Exactly one of page_id, block_id, or discussion_id must be provided.
    The Notion API requires these to be mutually exclusive.

    Args:
        api_key: Notion API key
        text: Comment text (supports inline markdown: **bold**, *italic*, `code`,
              [link](url))
        page_id: Page ID for page-level comments
        block_id: Block ID for block-level comments
        discussion_id: Discussion thread ID for replies

    Returns:
        dict: API response with comment details

    Raises:
        ValueError: If zero or multiple targets are provided
    """
    targets = sum(1 for t in (page_id, block_id, discussion_id) if t)
    if targets != 1:
        raise ValueError("Exactly one of page_id, block_id, or discussion_id must be provided")

    rich_text = create_rich_text(text)

    data: dict[str, Any] = {"rich_text": rich_text}

    if page_id:
        data["parent"] = {"page_id": page_id}
    elif block_id:
        data["parent"] = {"block_id": block_id}
    elif discussion_id:
        data["discussion_id"] = discussion_id

    return api_call("comments", api_key, method="POST", data=data)


def get_page_comments(api_key: str, block_id: str) -> list[dict[str, Any]]:
    """Get all comments for a block or page.

    Args:
        api_key: Notion API key
        block_id: Block or page ID to get comments for

    Returns:
        list: Comment objects
    """
    comments = []
    cursor = None

    while True:
        endpoint = f"comments?block_id={block_id}"
        if cursor:
            endpoint += f"&start_cursor={cursor}"

        response = api_call(endpoint, api_key)

        if "results" in response:
            comments.extend(response["results"])

        if not response.get("has_more", False):
            break

        cursor = response.get("next_cursor")

    return comments


def main():
    parser = argparse.ArgumentParser(
        description="Create a comment on a Notion page or block",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page", nargs="?", help="Notion page URL or ID (for page-level comments)")
    parser.add_argument("text", nargs="?", help="Comment text")
    parser.add_argument("--file", "-f", help="Read comment text from file")
    parser.add_argument(
        "--block",
        "-b",
        help="Block ID to attach comment to (creates block-level comment)",
    )

    args = parser.parse_args()

    # Validate: need either page or block
    if not args.page and not args.block:
        parser.error("Provide either a page ID or --block <block_id>")
        return

    # Get comment text
    # When --block is used, the first positional arg is the text (not a page ID)
    if args.file:
        text = Path(args.file).read_text().strip()
    elif args.block and args.page and not args.text:
        # argparse captured the comment text as 'page' since it comes first
        text = args.page
        args.page = None
    elif args.text:
        text = args.text
    else:
        parser.error("Provide comment text as argument or via --file")
        return

    try:
        api_key = load_api_key()

        if args.block:
            block_id = parse_notion_id(args.block)
            print(f"Creating comment on block {block_id}...", file=sys.stderr)
            result = create_comment(api_key, text, block_id=block_id)
        else:
            page_id = parse_notion_id(args.page)
            print(f"Creating comment on page {page_id}...", file=sys.stderr)
            result = create_comment(api_key, text, page_id=page_id)

        if result.get("object") == "error":
            print(
                f"Error: {result.get('message', 'Unknown error')}",
                file=sys.stderr,
            )
            sys.exit(1)

        comment_id = result.get("id", "unknown")
        discussion_id = result.get("discussion_id", "unknown")

        print(f"Comment created: {comment_id}", file=sys.stderr)
        print(f"Discussion ID: {discussion_id}", file=sys.stderr)

        # Output full response as JSON for programmatic use
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
