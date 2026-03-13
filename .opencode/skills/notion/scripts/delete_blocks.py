#!/usr/bin/env python3
"""⚠️  WARNING: DELETES BLOCKS AND THEIR COMMENTS!

Delete blocks from a Notion page.

⚠️  DANGER: Deleted blocks permanently lose their comments!

Usage:
    delete_blocks.py <block_id> [<block_id2> ...] [--yes]
    delete_blocks.py --all <page_id> [--yes]
    delete_blocks.py --range <page_id> <start> <end> [--yes]

Examples:
    # Delete specific blocks (will prompt for confirmation)
    delete_blocks.py <block_id1> <block_id2>

    # Delete all blocks in a page (will prompt for confirmation)
    delete_blocks.py --all <page_id>

    # Delete range of blocks by position (will prompt for confirmation)
    delete_blocks.py --range <page_id> 0 5

    # Skip confirmation (use with caution!)
    delete_blocks.py --all <page_id> --yes
"""

import argparse
import json
import sys

from notion_utils import (
    load_api_key,
    parse_notion_id,
    get_all_blocks,
    concurrent_deletes,
    is_interactive,
)


def confirm_delete(count: int, extra: str = "") -> bool:
    """Prompt for confirmation before deleting blocks.

    Returns True if confirmed or non-interactive (requires --yes in that case).
    """
    if not is_interactive():
        print(
            "Error: confirmation required. Use --yes to skip in non-interactive mode.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n" + "=" * 70, file=sys.stderr)
    print("WARNING: DANGEROUS OPERATION", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(
        f"\nThis will DELETE {count} BLOCKS{extra} and their COMMENTS!", file=sys.stderr
    )
    print("\n" + "=" * 70, file=sys.stderr)
    response = input("\nType 'yes' to delete blocks and proceed: ")
    if response != "yes":
        print("Cancelled", file=sys.stderr)
        sys.exit(0)
    print("", file=sys.stderr)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="WARNING: DELETES BLOCKS AND COMMENTS!\nDelete blocks from Notion page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("block_ids", nargs="*", help="Block IDs to delete")
    parser.add_argument("--all", metavar="PAGE_ID", help="Delete all blocks in page")
    parser.add_argument(
        "--range",
        nargs=3,
        metavar=("PAGE_ID", "START", "END"),
        help="Delete range of blocks (positions)",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Ensure exactly one mode is specified
    modes = sum([bool(args.block_ids), bool(args.all), bool(args.range)])
    if modes == 0:
        parser.error("Must specify block_ids, --all, or --range")
    if modes > 1:
        parser.error("Cannot combine block_ids, --all, and --range")

    try:
        api_key = load_api_key()

        if args.all:
            page_id = parse_notion_id(args.all)
            print("Getting all blocks from page...", file=sys.stderr)
            blocks = get_all_blocks(page_id, api_key)
            block_ids = [b["id"] for b in blocks]

            if not args.yes:
                confirm_delete(len(block_ids))

            print(f"Deleting {len(block_ids)} blocks concurrently...", file=sys.stderr)
            deleted, failed = concurrent_deletes(block_ids, api_key)
            print(
                json.dumps(
                    {"success": failed == 0, "deleted": deleted, "failed": failed},
                    indent=2,
                )
            )

        elif args.range:
            page_id = parse_notion_id(args.range[0])
            start = int(args.range[1])
            end = int(args.range[2])

            print("Getting blocks...", file=sys.stderr)
            blocks = get_all_blocks(page_id, api_key)
            to_delete = [b["id"] for b in blocks[start:end]]

            if not args.yes:
                confirm_delete(len(to_delete), f" (positions {start}-{end})")

            print(f"Deleting {len(to_delete)} blocks concurrently...", file=sys.stderr)
            deleted, failed = concurrent_deletes(to_delete, api_key)
            print(
                json.dumps(
                    {"success": failed == 0, "deleted": deleted, "failed": failed},
                    indent=2,
                )
            )

        else:
            block_ids = [parse_notion_id(bid) for bid in args.block_ids]

            if not args.yes:
                confirm_delete(len(block_ids))

            print(f"Deleting {len(block_ids)} blocks concurrently...", file=sys.stderr)
            deleted, failed = concurrent_deletes(block_ids, api_key)
            print(
                json.dumps(
                    {"success": failed == 0, "deleted": deleted, "failed": failed},
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
