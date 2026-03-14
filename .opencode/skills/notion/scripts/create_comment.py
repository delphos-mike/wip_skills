#!/usr/bin/env python3
"""Create a comment on a Notion page or block.

Creates page-level comments. To reply to an existing discussion thread,
use reply_to_comment.py instead.

Usage:
    create_comment.py <page_url_or_id> "Comment text"
    create_comment.py <page_url_or_id> --file comment.txt
    create_comment.py <page_url_or_id> --block <block_id> "Comment text"

Examples:
    # Page-level comment
    create_comment.py https://www.notion.so/My-Page-abc123 "Looks good!"

    # Comment referencing a specific block context
    create_comment.py abc123 --block def456 "This paragraph needs revision"

    # Comment from file
    create_comment.py abc123 --file review_notes.txt
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from notion_utils import api_call, create_rich_text, load_api_key, parse_notion_id


def create_comment(
    api_key: str,
    page_id: str,
    text: str,
    discussion_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a comment on a Notion page.

    Args:
        api_key: Notion API key
        page_id: Page ID to comment on
        text: Comment text (supports inline markdown: **bold**, *italic*, `code`)
        discussion_id: If provided, replies to an existing discussion thread

    Returns:
        dict: API response with comment details
    """
    rich_text = create_rich_text(text)

    data: Dict[str, Any] = {
        "parent": {"page_id": page_id},
        "rich_text": rich_text,
    }

    if discussion_id:
        data["discussion_id"] = discussion_id

    return api_call("comments", api_key, method="POST", data=data)


def get_page_comments(api_key: str, block_id: str) -> List[Dict[str, Any]]:
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
        description="Create a comment on a Notion page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page", help="Notion page URL or ID")
    parser.add_argument("text", nargs="?", help="Comment text")
    parser.add_argument("--file", "-f", help="Read comment text from file")
    parser.add_argument(
        "--block", "-b", help="Block ID to associate the comment with (contextual)"
    )

    args = parser.parse_args()

    # Get comment text
    if args.file:
        text = Path(args.file).read_text().strip()
    elif args.text:
        text = args.text
    else:
        parser.error("Provide comment text as argument or via --file")
        return

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page)

        print(f"Creating comment on page {page_id}...", file=sys.stderr)

        result = create_comment(api_key, page_id, text)

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
        sys.exit(1)


if __name__ == "__main__":
    main()
