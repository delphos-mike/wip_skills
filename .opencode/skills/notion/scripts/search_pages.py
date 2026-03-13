#!/usr/bin/env python3
"""Search for Notion pages.

Usage:
    search_pages.py <query> [--limit N] [--output json|table]

Examples:
    search_pages.py "project plan"
    search_pages.py "RFC" --limit 10
    search_pages.py "design" --output json
"""
import argparse
import json
import sys
from typing import Dict, List, Any

from notion_utils import load_api_key, api_call


def search_pages(query: str, api_key: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search for pages matching query."""
    all_results = []
    cursor = None

    while len(all_results) < limit:
        data = {
            "query": query,
            "filter": {"property": "object", "value": "page"},
            "page_size": min(100, limit - len(all_results))
        }

        if cursor:
            data["start_cursor"] = cursor

        response = api_call('search', api_key, 'POST', data)

        if 'results' in response:
            all_results.extend(response['results'])

        if not response.get('has_more', False):
            break

        cursor = response.get('next_cursor')

    return all_results[:limit]


def extract_title(page: Dict[str, Any]) -> str:
    """Extract page title from properties."""
    if 'properties' not in page:
        return "Untitled"

    for prop_name, prop_data in page['properties'].items():
        if prop_data.get('type') == 'title':
            title_array = prop_data.get('title', [])
            return ''.join([t.get('plain_text', '') for t in title_array]) or "Untitled"

    return "Untitled"


def format_table(results: List[Dict[str, Any]]):
    """Format results as a table."""
    if not results:
        print("No results found")
        return

    print(f"\nFound {len(results)} pages:\n")
    print(f"{'#':<4} {'Title':<50} {'ID':<38} {'URL'}")
    print("-" * 150)

    for idx, page in enumerate(results, 1):
        title = extract_title(page)
        page_id = page['id']
        url = page.get('url', '')

        # Truncate long titles
        if len(title) > 47:
            title = title[:47] + "..."

        print(f"{idx:<4} {title:<50} {page_id:<38} {url}")


def main():
    parser = argparse.ArgumentParser(
        description='Search for Notion pages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('query', help='Search query')
    parser.add_argument('--limit', '-l', type=int, default=20,
                       help='Maximum number of results (default: 20)')
    parser.add_argument('--output', '-o', choices=['json', 'table'], default='table',
                       help='Output format (default: table)')

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        results = search_pages(args.query, api_key, args.limit)

        if args.output == 'json':
            # Output full JSON for programmatic use
            output = {
                'query': args.query,
                'count': len(results),
                'results': results
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable table
            format_table(results)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
