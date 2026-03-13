#!/usr/bin/env python3
"""Find and link page references in Notion content.

Usage:
    link_pages.py <page_id> --find-references
    link_pages.py <page_id> --link "Page Name" <mention_page_id>

Examples:
    # Find potential page references
    link_pages.py <page_id> --find-references

    # Create link to a page (searches for matches)
    link_pages.py <page_id> --link "RFC" <target_page_id>
"""

import argparse
import json
import re
import sys
from typing import Dict, List, Any

from notion_utils import load_api_key, parse_notion_id, api_call, get_all_blocks


def extract_text(rich_text: List[Dict]) -> str:
    return "".join([rt.get("plain_text", "") for rt in rich_text])


def search_pages(query: str, api_key: str) -> List[Dict]:
    """Search for pages matching query."""
    data = {
        "query": query,
        "filter": {"property": "object", "value": "page"},
        "page_size": 10,
    }

    response = api_call("search", api_key, "POST", data)
    return response.get("results", [])


def find_potential_references(blocks: List[Dict]) -> List[Dict]:
    """Find potential page references in content."""
    references = []

    # Common patterns that might be page references
    patterns = [
        r"\b(RFC[:\s-]*\w+)",  # RFC references
        r"\b(ADR[:\s-]*\d+)",  # ADR references
        r'"([^"]+)"',  # Quoted text (might be page titles)
        r"\[([^\]]+)\]",  # Bracketed text
    ]

    for block in blocks:
        block_type = block.get("type", "")
        content = block.get(block_type, {})

        if "rich_text" in content:
            text = extract_text(content["rich_text"])

            for pattern in patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if len(match) > 3:  # Skip very short matches
                        references.append(
                            {
                                "text": match,
                                "block_id": block["id"],
                                "block_type": block_type,
                            }
                        )

    return references


def create_page_mention(page_id: str) -> Dict:
    """Create a page mention rich_text object."""
    return {"type": "mention", "mention": {"type": "page", "page": {"id": page_id}}}


def main():
    parser = argparse.ArgumentParser(
        description="Find and link page references",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("page_id", help="Page ID")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--find-references", action="store_true", help="Find potential page references"
    )
    group.add_argument(
        "--link",
        nargs=2,
        metavar=("QUERY", "TARGET_PAGE_ID"),
        help="Search and link pages",
    )

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page_id)

        if args.find_references:
            print("Reading page...", file=sys.stderr)
            blocks = get_all_blocks(page_id, api_key)

            print("Finding references...", file=sys.stderr)
            references = find_potential_references(blocks)

            # Deduplicate
            unique_refs = {}
            for ref in references:
                if ref["text"] not in unique_refs:
                    unique_refs[ref["text"]] = ref

            print(
                f"\nFound {len(unique_refs)} potential references:\n", file=sys.stderr
            )

            for ref_text, ref in unique_refs.items():
                # Try to find matching pages
                matches = search_pages(ref_text, api_key)

                print(f"  '{ref_text}'", file=sys.stderr)
                if matches:
                    print(f"    Possible matches:", file=sys.stderr)
                    for match in matches[:3]:
                        title = (
                            match.get("properties", {})
                            .get("title", {})
                            .get("title", [{}])[0]
                            .get("plain_text", "Untitled")
                        )
                        print(f"      - {title} ({match['id']})", file=sys.stderr)
                else:
                    print(f"    No matches found", file=sys.stderr)
                print(file=sys.stderr)

            # Output JSON
            result = {
                "references": list(unique_refs.values()),
                "count": len(unique_refs),
            }
            print(json.dumps(result, indent=2))

        elif args.link:
            query, target_page_id = args.link
            target_page_id = parse_notion_id(target_page_id)

            print(f"Searching for pages matching '{query}'...", file=sys.stderr)
            matches = search_pages(query, api_key)

            if matches:
                print(f"Found {len(matches)} matching pages:", file=sys.stderr)
                for idx, match in enumerate(matches, 1):
                    title = (
                        match.get("properties", {})
                        .get("title", {})
                        .get("title", [{}])[0]
                        .get("plain_text", "Untitled")
                    )
                    print(f"  {idx}. {title} ({match['id']})", file=sys.stderr)

            print(f"\nCreating page mention for {target_page_id}...", file=sys.stderr)
            mention = create_page_mention(target_page_id)

            result = {
                "success": True,
                "mention": mention,
                "target_page_id": target_page_id,
            }

            print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
