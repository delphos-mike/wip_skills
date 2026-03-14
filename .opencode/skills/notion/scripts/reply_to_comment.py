#!/usr/bin/env python3
"""Reply to an existing comment discussion thread in Notion.

Requires a discussion_id, which can be obtained from extract_comments.py
or from the output of create_comment.py.

Usage:
    reply_to_comment.py <page_url_or_id> <discussion_id> "Reply text"
    reply_to_comment.py <page_url_or_id> <discussion_id> --file reply.txt

Examples:
    # Reply to a discussion thread
    reply_to_comment.py abc123 def456-disc-id "I agree, let's fix this"

    # Reply from file
    reply_to_comment.py abc123 def456-disc-id --file detailed_reply.txt

    # Chain: create comment then reply to it
    #   create_comment.py abc123 "Initial thought" > comment.json
    #   discussion_id=$(python3 -c "import json,sys; print(json.load(sys.stdin)['discussion_id'])" < comment.json)
    #   reply_to_comment.py abc123 $discussion_id "Follow-up thought"
"""

import argparse
import json
import sys
from pathlib import Path

from notion_utils import load_api_key, parse_notion_id
from create_comment import create_comment


def main():
    parser = argparse.ArgumentParser(
        description="Reply to a Notion comment discussion thread",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page", help="Notion page URL or ID")
    parser.add_argument("discussion_id", help="Discussion thread ID to reply to")
    parser.add_argument("text", nargs="?", help="Reply text")
    parser.add_argument("--file", "-f", help="Read reply text from file")

    args = parser.parse_args()

    # Get reply text
    if args.file:
        text = Path(args.file).read_text().strip()
    elif args.text:
        text = args.text
    else:
        parser.error("Provide reply text as argument or via --file")
        return

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page)

        print(
            f"Replying to discussion {args.discussion_id} on page {page_id}...",
            file=sys.stderr,
        )

        result = create_comment(
            api_key, page_id, text, discussion_id=args.discussion_id
        )

        if result.get("object") == "error":
            print(
                f"Error: {result.get('message', 'Unknown error')}",
                file=sys.stderr,
            )
            sys.exit(1)

        comment_id = result.get("id", "unknown")
        print(f"Reply created: {comment_id}", file=sys.stderr)

        # Output full response as JSON for programmatic use
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
