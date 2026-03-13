#!/usr/bin/env python3
"""Summarize Notion comments from extracted JSON.

Usage:
    summarize_comments.py <comments_json_file> [--output <dir>]

Examples:
    summarize_comments.py /tmp/page_comments.json
    summarize_comments.py comments.json --output ./reports
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

from notion_utils import load_api_key, api_call


def get_user_info(user_id: str, api_key: str) -> Dict[str, Any]:
    """Fetch user details from Notion API."""
    if not api_key:
        return {"name": user_id, "id": user_id}

    try:
        return api_call(f"users/{user_id}", api_key)
    except Exception:
        return {"name": user_id, "id": user_id}


def summarize_comments(comments_file: Path, output_dir: Path):
    """Generate summary reports from comments JSON."""
    # Load comments
    with open(comments_file) as f:
        comments = json.load(f)

    if not comments:
        print("No comments found in file", file=sys.stderr)
        return

    # Get page info from first comment
    page_id = comments[0].get("page_id", "unknown")
    page_title = comments[0].get("page_title", "Untitled")

    print(f"Analyzing comments for: {page_title}", file=sys.stderr)
    print(f"Total comments: {len(comments)}", file=sys.stderr)

    # Load API key for user lookups
    try:
        api_key = load_api_key()
    except:
        api_key = None
        print(
            "Warning: No API key found, using user IDs instead of names",
            file=sys.stderr,
        )

    # Group by user
    comments_by_user = defaultdict(list)
    for comment in comments:
        user_id = comment.get("created_by", "unknown")
        comments_by_user[user_id].append(comment)

    # Get user names
    print(f"Looking up {len(comments_by_user)} users...", file=sys.stderr)
    user_cache = {}
    for user_id in comments_by_user.keys():
        if user_id not in user_cache and api_key:
            user_info = get_user_info(user_id, api_key)
            user_cache[user_id] = user_info.get("name", user_id)
        elif user_id not in user_cache:
            user_cache[user_id] = user_id

    # Group by discussion
    discussions = defaultdict(list)
    for comment in comments:
        disc_id = comment.get("discussion_id", "unknown")
        discussions[disc_id].append(comment)

    # Generate markdown report
    report_file = (
        output_dir / f"{page_title.replace(' ', '_').lower()}_comments_report.md"
    )

    with open(report_file, "w") as f:
        f.write(f"# {page_title} - Comment Analysis\n\n")
        f.write(f"**Page ID:** `{page_id}`\n\n")
        f.write(f"---\n\n")

        f.write("## Summary Statistics\n\n")
        f.write(f"- **Total Comments:** {len(comments)}\n")
        f.write(f"- **Total Commenters:** {len(comments_by_user)}\n")
        f.write(f"- **Discussion Threads:** {len(discussions)}\n\n")

        f.write("---\n\n")
        f.write("## Comments by User\n\n")

        # Sort by comment count
        sorted_users = sorted(
            comments_by_user.items(), key=lambda x: len(x[1]), reverse=True
        )

        for user_id, user_comments in sorted_users:
            user_name = user_cache.get(user_id, user_id)
            percentage = (len(user_comments) / len(comments)) * 100

            f.write(f"### {user_name}\n\n")
            f.write(f"**User ID:** `{user_id}`\n\n")
            f.write(f"- **Comment Count:** {len(user_comments)} ({percentage:.1f}%)\n")

            # Count unique discussions
            user_discussions = set(c.get("discussion_id") for c in user_comments)
            f.write(f"- **Discussion Threads:** {len(user_discussions)}\n\n")

        f.write("---\n\n")
        f.write("## Discussion Threads\n\n")

        # Sort discussions by comment count
        sorted_discussions = sorted(
            discussions.items(), key=lambda x: len(x[1]), reverse=True
        )

        for disc_id, disc_comments in sorted_discussions:
            f.write(f"### Discussion: `{disc_id}`\n\n")
            f.write(f"**Comments:** {len(disc_comments)}\n")

            # Get participants
            participants = set(c.get("created_by") for c in disc_comments)
            f.write(f"**Participants:** {len(participants)}\n")

            # Get context from first comment
            first_comment = sorted(
                disc_comments, key=lambda x: x.get("created_time", "")
            )[0]
            context = first_comment.get("block_context", "")[:150]
            if len(first_comment.get("block_context", "")) > 150:
                context += "..."

            f.write(f"**Context:** {context}\n\n")

            # Show thread
            f.write("**Thread:**\n\n")
            for comment in sorted(
                disc_comments, key=lambda x: x.get("created_time", "")
            ):
                user_name = user_cache.get(
                    comment.get("created_by"), comment.get("created_by", "Unknown")
                )
                comment_text = comment.get("comment_text", "")
                timestamp = comment.get("created_time", "")

                # Include link if available
                comment_link = comment.get("comment_link")
                if comment_link:
                    f.write(f"- **[{user_name}]({comment_link})** ({timestamp}):\n")
                else:
                    f.write(f"- **{user_name}** ({timestamp}):\n")

                f.write(f"  > {comment_text}\n\n")

        f.write("---\n\n")
        f.write("## Detailed Comments by User\n\n")

        for user_id, user_comments in sorted_users:
            user_name = user_cache.get(user_id, user_id)

            f.write(f"### {user_name} - All Comments\n\n")

            # Sort by time
            sorted_comments = sorted(
                user_comments, key=lambda x: x.get("created_time", "")
            )

            for idx, comment in enumerate(sorted_comments, 1):
                f.write(f"#### Comment {idx}/{len(user_comments)}\n\n")
                f.write(f"**Time:** {comment.get('created_time')}\n")
                f.write(f"**Discussion:** `{comment.get('discussion_id')}`\n")

                # Link if available
                if comment.get("comment_link"):
                    f.write(f"**Link:** {comment.get('comment_link')}\n")

                f.write(f"**Block Type:** {comment.get('block_type')}\n\n")
                f.write(f"**Context:**\n> {comment.get('block_context', '')[:200]}\n\n")
                f.write(f"**Comment:**\n> {comment.get('comment_text')}\n\n")
                f.write("---\n\n")

    print(f"✓ Report saved to: {report_file}", file=sys.stderr)

    # Generate text summary
    summary_file = (
        output_dir / f"{page_title.replace(' ', '_').lower()}_comments_summary.txt"
    )

    with open(summary_file, "w") as f:
        f.write(f"COMMENT SUMMARY: {page_title}\n")
        f.write(f"{'=' * 80}\n\n")
        f.write(f"Total Comments: {len(comments)}\n")
        f.write(f"Total Commenters: {len(comments_by_user)}\n")
        f.write(f"Discussion Threads: {len(discussions)}\n\n")

        for user_id, user_comments in sorted_users:
            user_name = user_cache.get(user_id, user_id)
            f.write(f"\n{'-' * 80}\n")
            f.write(f"USER: {user_name}\n")
            f.write(f"COMMENTS: {len(user_comments)}\n")
            f.write(f"{'-' * 80}\n\n")

            for idx, comment in enumerate(
                sorted(user_comments, key=lambda x: x.get("created_time", "")), 1
            ):
                f.write(f"Comment {idx}:\n")
                f.write(f"  Time: {comment.get('created_time')}\n")
                f.write(f"  Context: {comment.get('block_context', '')[:100]}...\n")
                f.write(f"  Text: {comment.get('comment_text')}\n\n")

    print(f"✓ Summary saved to: {summary_file}", file=sys.stderr)

    # Print statistics
    result = {
        "page_title": page_title,
        "total_comments": len(comments),
        "total_commenters": len(comments_by_user),
        "discussion_threads": len(discussions),
        "report_file": str(report_file),
        "summary_file": str(summary_file),
    }

    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Summarize Notion comments from extracted JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("comments_file", help="Path to comments JSON file")
    parser.add_argument(
        "--output", "-o", default="/tmp", help="Output directory (default: /tmp)"
    )

    args = parser.parse_args()

    try:
        comments_file = Path(args.comments_file)
        if not comments_file.exists():
            print(f"Error: File not found: {comments_file}", file=sys.stderr)
            sys.exit(1)

        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        summarize_comments(comments_file, output_dir)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
