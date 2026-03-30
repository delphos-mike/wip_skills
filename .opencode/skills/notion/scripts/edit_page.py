#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests>=2.31.0"]
# ///
"""✅ SAFE: Edit Notion page preserving comments.

Simple wrapper for the safe edit workflow that preserves comments.

This is a convenient wrapper around:
  1. read_page.py (pull content)
  2. Your editor (edit locally)
  3. sync_page.py (push changes, preserving comments)

Usage:
    edit_page.py <page_id>              # Interactive workflow
    edit_page.py <page_id> <json_file>  # Direct sync from edited file

Examples:
    # Interactive workflow (recommended)
    edit_page.py <page_id>
    # Downloads to /tmp/page_XXXXX.json, opens in $EDITOR, then syncs

    # Direct sync (if you already edited the JSON)
    edit_page.py <page_id> edited_page.json
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from notion_utils import load_api_key, parse_notion_id


def main():
    parser = argparse.ArgumentParser(
        description="✅ SAFE: Edit Notion page preserving comments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page_id", help="Page ID or URL")
    parser.add_argument("json_file", nargs="?", help="Pre-edited JSON file (optional)")
    parser.add_argument(
        "--delete-removed", action="store_true", help="Delete blocks not in edited content (loses their comments!)"
    )
    parser.add_argument("--force", "-f", action="store_true", help="Skip confidence checks in sync")

    args = parser.parse_args()

    try:
        load_api_key()  # validate key is available
        page_id = parse_notion_id(args.page_id)

        script_dir = Path(__file__).parent

        if args.json_file:
            # Direct sync from provided file
            json_path = Path(args.json_file)
            if not json_path.exists():
                print(f"Error: File not found: {json_path}", file=sys.stderr)
                sys.exit(1)

            print(f"Syncing from {json_path}...", file=sys.stderr)
            cmd = [str(script_dir / "sync_page.py"), page_id, str(json_path)]
            if args.delete_removed:
                cmd.append("--delete-removed")
            if args.force:
                cmd.append("--force")

            result = subprocess.run(cmd)
            sys.exit(result.returncode)

        else:
            # Interactive workflow
            print("=" * 70, file=sys.stderr)
            print("✅ SAFE EDIT WORKFLOW (Preserves Comments)", file=sys.stderr)
            print("=" * 70, file=sys.stderr)

            # Step 1: Download
            print("\n[1/3] Downloading page content...", file=sys.stderr)
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", prefix=f"notion_page_{page_id[:8]}_", delete=False, dir="/tmp"
            )
            temp_path = temp_file.name
            temp_file.close()

            cmd = [str(script_dir / "read_page.py"), page_id, "--output", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error downloading page: {result.stderr}", file=sys.stderr)
                sys.exit(1)

            with open(temp_path, "w") as f:
                f.write(result.stdout)

            print(f"✓ Downloaded to: {temp_path}", file=sys.stderr)

            # Step 2: Edit
            print("\n[2/3] Opening editor...", file=sys.stderr)
            editor = os.environ.get("EDITOR", "vim")
            print(f"Using editor: {editor}", file=sys.stderr)
            print("Edit the JSON file, then save and quit to continue.", file=sys.stderr)
            print("(Or quit without saving to cancel)", file=sys.stderr)

            # Get file timestamp before editing
            original_mtime = os.path.getmtime(temp_path)

            subprocess.run([editor, temp_path])

            # Check if file was modified
            new_mtime = os.path.getmtime(temp_path)
            if new_mtime == original_mtime:
                print("\n✗ File unchanged. Cancelled.", file=sys.stderr)
                os.unlink(temp_path)
                sys.exit(0)

            # Validate JSON
            try:
                with open(temp_path) as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                print(f"\n✗ Invalid JSON: {e}", file=sys.stderr)
                print(f"File saved at: {temp_path}", file=sys.stderr)
                sys.exit(1)

            # Step 3: Sync
            print("\n[3/3] Syncing changes...", file=sys.stderr)
            cmd = [str(script_dir / "sync_page.py"), page_id, temp_path]
            if args.delete_removed:
                cmd.append("--delete-removed")
            if args.force:
                cmd.append("--force")

            result = subprocess.run(cmd)

            if result.returncode == 0:
                print(f"\n✓ Success! Temporary file: {temp_path}", file=sys.stderr)
                print("(File kept for backup - you can delete it)", file=sys.stderr)
            else:
                print(f"\n✗ Sync failed. File saved at: {temp_path}", file=sys.stderr)

            sys.exit(result.returncode)

    except KeyboardInterrupt:
        print("\n\nCancelled by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
