#!/usr/bin/env python3
"""Find sections in a Notion page by heading text.

Usage:
    find_section.py <page_id> "Section Name"
    find_section.py <page_id> --list-all

Examples:
    # Find specific section
    find_section.py <page_id> "Architecture"

    # List all sections
    find_section.py <page_id> --list-all

    # Find section (case-insensitive)
    find_section.py <page_id> "introduction"
"""

import argparse
import json
import sys
from typing import Dict, List, Any, Optional

from notion_utils import load_api_key, parse_notion_id, get_all_blocks


def extract_text(rich_text: List[Dict]) -> str:
    """Extract plain text from rich_text array."""
    return "".join([rt.get("plain_text", "") for rt in rich_text])


def find_sections(blocks: List[Dict]) -> List[Dict]:
    """Find all sections (headings) in blocks."""
    sections = []

    for idx, block in enumerate(blocks):
        block_type = block.get("type", "")

        if block_type in ["heading_1", "heading_2", "heading_3"]:
            content = block.get(block_type, {})
            text = extract_text(content.get("rich_text", []))

            # Find next heading to determine section range
            next_heading_idx = None
            for i in range(idx + 1, len(blocks)):
                if blocks[i].get("type", "") in ["heading_1", "heading_2", "heading_3"]:
                    next_heading_idx = i
                    break

            sections.append(
                {
                    "level": int(block_type[-1]),
                    "text": text,
                    "block_id": block["id"],
                    "block_index": idx,
                    "end_index": next_heading_idx or len(blocks),
                    "type": block_type,
                }
            )

    return sections


def find_section_by_name(sections: List[Dict], query: str) -> Optional[Dict]:
    """Find section by name (case-insensitive)."""
    query_lower = query.lower()

    for section in sections:
        if query_lower in section["text"].lower():
            return section

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Find sections in Notion page",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page_id", help="Page ID or URL")
    parser.add_argument("query", nargs="?", help="Section name to find")
    parser.add_argument("--list-all", action="store_true", help="List all sections")

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page_id)

        print("Reading page...", file=sys.stderr)
        blocks = get_all_blocks(page_id, api_key)

        print(f"Found {len(blocks)} blocks", file=sys.stderr)
        sections = find_sections(blocks)

        if args.list_all:
            # List all sections
            print(f"\nFound {len(sections)} sections:\n", file=sys.stderr)
            for idx, section in enumerate(sections, 1):
                indent = "  " * (section["level"] - 1)
                print(f"{idx}. {indent}{section['text']}", file=sys.stderr)
                print(f"   Block ID: {section['block_id']}", file=sys.stderr)
                print(
                    f"   Range: blocks {section['block_index']} to {section['end_index']}",
                    file=sys.stderr,
                )
                print(file=sys.stderr)

            # Output JSON
            print(json.dumps(sections, indent=2))

        elif args.query:
            # Find specific section
            section = find_section_by_name(sections, args.query)

            if section:
                print(f"\nFound section: {section['text']}", file=sys.stderr)
                print(f"Block ID: {section['block_id']}", file=sys.stderr)
                print(f"Level: {section['level']}", file=sys.stderr)
                print(
                    f"Range: blocks {section['block_index']} to {section['end_index']}",
                    file=sys.stderr,
                )

                # Get blocks in section
                section_blocks = blocks[section["block_index"] : section["end_index"]]

                result = {
                    "section": section,
                    "blocks": section_blocks,
                    "block_count": len(section_blocks),
                }

                print(json.dumps(result, indent=2))
            else:
                print(f"Section '{args.query}' not found", file=sys.stderr)
                sys.exit(1)

        else:
            print("Error: Provide query or --list-all", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
