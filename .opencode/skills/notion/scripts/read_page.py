#!/usr/bin/env python3
"""Read Notion page content.

Usage:
    read_page.py <page_url_or_id> [--output markdown|json|text]

Examples:
    read_page.py https://www.notion.so/Page-abc123
    read_page.py 2f542374-e1fe-80e9-a480-d59873e7241c
    read_page.py <page_id> --output json
"""
import argparse
import json
import sys
from typing import Dict, List, Any

from notion_utils import (
    load_api_key,
    parse_notion_id,
    api_call,
    get_all_blocks,
    extract_rich_text
)


def block_to_markdown(block: Dict[str, Any], indent_level: int = 0) -> str:
    """Convert a block to markdown format."""
    block_type = block.get('type', '')
    block_content = block.get(block_type, {})
    indent = '  ' * indent_level
    lines = []

    if block_type == 'paragraph':
        text = extract_rich_text(block_content.get('rich_text', []))
        if text:
            lines.append(f"{indent}{text}")

    elif block_type.startswith('heading_'):
        level = int(block_type[-1])
        text = extract_rich_text(block_content.get('rich_text', []))
        lines.append(f"{indent}{'#' * level} {text}")

    elif block_type == 'bulleted_list_item':
        text = extract_rich_text(block_content.get('rich_text', []))
        lines.append(f"{indent}- {text}")

    elif block_type == 'numbered_list_item':
        text = extract_rich_text(block_content.get('rich_text', []))
        lines.append(f"{indent}1. {text}")

    elif block_type == 'to_do':
        text = extract_rich_text(block_content.get('rich_text', []))
        checked = block_content.get('checked', False)
        checkbox = '[x]' if checked else '[ ]'
        lines.append(f"{indent}- {checkbox} {text}")

    elif block_type == 'toggle':
        text = extract_rich_text(block_content.get('rich_text', []))
        lines.append(f"{indent}▶ {text}")

    elif block_type == 'code':
        text = extract_rich_text(block_content.get('rich_text', []))
        language = block_content.get('language', '')
        lines.append(f"{indent}```{language}")
        lines.append(text)
        lines.append(f"{indent}```")

    elif block_type == 'quote':
        text = extract_rich_text(block_content.get('rich_text', []))
        lines.append(f"{indent}> {text}")

    elif block_type == 'callout':
        text = extract_rich_text(block_content.get('rich_text', []))
        icon = block_content.get('icon', {})
        emoji = icon.get('emoji', '💡')
        lines.append(f"{indent}{emoji} {text}")

    elif block_type == 'divider':
        lines.append(f"{indent}---")

    elif block_type == 'child_page':
        title = block_content.get('title', 'Untitled')
        lines.append(f"{indent}📄 {title}")

    elif block_type == 'child_database':
        title = block_content.get('title', 'Untitled')
        lines.append(f"{indent}🗂️ {title}")

    elif block_type == 'image':
        # Handle both external and file types
        image_data = block_content.get('external') or block_content.get('file', {})
        url = image_data.get('url', '')
        if url:
            # Get caption if available
            caption = extract_rich_text(block_content.get('caption', []))
            if caption:
                lines.append(f"{indent}![{caption}]({url})")
            else:
                lines.append(f"{indent}![]({url})")

    # Handle children
    if 'children' in block:
        for child in block['children']:
            child_lines = block_to_markdown(child, indent_level + 1)
            if child_lines:
                lines.append(child_lines)

    return '\n'.join(lines)


def block_to_text(block: Dict[str, Any], indent_level: int = 0) -> str:
    """Convert a block to plain text."""
    block_type = block.get('type', '')
    block_content = block.get(block_type, {})
    indent = '  ' * indent_level
    lines = []

    # Extract text from rich_text
    if 'rich_text' in block_content:
        text = extract_rich_text(block_content.get('rich_text', []))
        if text:
            prefix = ''
            if block_type == 'bulleted_list_item':
                prefix = '• '
            elif block_type == 'numbered_list_item':
                prefix = '1. '
            elif block_type == 'to_do':
                checked = block_content.get('checked', False)
                prefix = '[x] ' if checked else '[ ] '

            lines.append(f"{indent}{prefix}{text}")

    # Handle children
    if 'children' in block:
        for child in block['children']:
            child_text = block_to_text(child, indent_level + 1)
            if child_text:
                lines.append(child_text)

    return '\n'.join(lines)


def read_page(page_id: str, api_key: str, output_format: str = 'markdown'):
    """Read and format page content."""
    # Get page metadata
    page_info = api_call(f'pages/{page_id}', api_key)

    if 'object' in page_info and page_info['object'] == 'error':
        print(f"Error: {page_info.get('message', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)

    # Extract title
    title = "Untitled"
    if 'properties' in page_info:
        for prop_name, prop_data in page_info['properties'].items():
            if prop_data.get('type') == 'title' and prop_data.get('title'):
                title = extract_rich_text(prop_data['title'])
                break

    # Get all blocks
    print(f"Reading page: {title}...", file=sys.stderr)
    blocks = get_all_blocks(page_id, api_key)
    print(f"Found {len(blocks)} blocks", file=sys.stderr)

    if output_format == 'json':
        output = {
            'page_id': page_id,
            'title': title,
            'url': page_info.get('url', ''),
            'created_time': page_info.get('created_time'),
            'last_edited_time': page_info.get('last_edited_time'),
            'blocks': blocks
        }
        print(json.dumps(output, indent=2))

    elif output_format == 'markdown':
        print(f"# {title}\n")
        for block in blocks:
            md = block_to_markdown(block)
            if md:
                print(md)
                print()

    elif output_format == 'text':
        print(f"{title}\n{'=' * len(title)}\n")
        for block in blocks:
            text = block_to_text(block)
            if text:
                print(text)
                print()


def main():
    parser = argparse.ArgumentParser(
        description='Read Notion page content',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('page', help='Notion page URL or ID')
    parser.add_argument('--output', '-o', choices=['markdown', 'json', 'text'],
                       default='markdown', help='Output format (default: markdown)')

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page)
        read_page(page_id, api_key, args.output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
