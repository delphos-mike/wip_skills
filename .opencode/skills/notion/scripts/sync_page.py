#!/usr/bin/env python3
"""Sync page content while preserving comments.

Uses diff algorithm to:
- UPDATE blocks that changed (preserves comments)
- INSERT new blocks
- DELETE removed blocks (loses their comments)

Usage:
    sync_page.py <page_id> <json_file> [--delete-removed]

Examples:
    # Update changed blocks only (safe)
    sync_page.py <page_id> edited.json

    # Also delete blocks not in new content
    sync_page.py <page_id> edited.json --delete-removed
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from notion_utils import load_api_key, api_call, parse_notion_id, get_all_blocks


def extract_text_content(block: Dict) -> str:
    """Extract text content from block for comparison."""
    block_type = block.get('type', '')
    content = block.get(block_type, {})

    if 'rich_text' in content:
        return ''.join([rt.get('plain_text', '') for rt in content['rich_text']])
    return ''


def compute_content_hash(block: Dict) -> str:
    """Compute a hash of block content for verification."""
    block_type = block.get('type', '')
    content_str = f"{block_type}:{extract_text_content(block)}"
    return hashlib.sha256(content_str.encode()).hexdigest()[:12]


def blocks_match(old_block: Dict, new_block: Dict) -> bool:
    """Check if blocks represent the same content."""
    if old_block.get('type') != new_block.get('type'):
        return False

    old_text = extract_text_content(old_block)
    new_text = extract_text_content(new_block)

    return old_text == new_text


def compute_match_confidence(old_blocks: List[Dict], new_blocks: List[Dict]) -> Tuple[float, List[str]]:
    """Compute confidence score for position-based matching.

    Returns:
        Tuple of (confidence_score, warnings)
        confidence_score: 0.0-1.0, where 1.0 is perfect confidence
        warnings: List of potential issues detected
    """
    if not old_blocks or not new_blocks:
        return 1.0, []

    warnings = []

    # Check for content hashes
    old_hashes = [compute_content_hash(b) for b in old_blocks]
    new_hashes = [compute_content_hash(b) for b in new_blocks]

    # Find blocks that appear to have moved
    old_hash_set = set(old_hashes)
    new_hash_set = set(new_hashes)

    # Blocks in new but not in old positions where they were
    position_mismatches = 0
    for i in range(min(len(old_hashes), len(new_hashes))):
        if old_hashes[i] != new_hashes[i]:
            # Check if this old hash appears elsewhere in new
            if old_hashes[i] in new_hashes[i+1:]:
                position_mismatches += 1

    if position_mismatches > 0:
        warnings.append(f"{position_mismatches} blocks may have been reordered")

    # Check for significant content at the beginning that's new
    if len(new_blocks) > 0 and len(old_blocks) > 0:
        if new_hashes[0] not in old_hash_set:
            if old_hashes[0] in new_hashes[1:]:
                warnings.append("New content inserted at the beginning - all positions shifted")

    # Compute confidence score
    if not warnings:
        confidence = 1.0
    elif "all positions shifted" in str(warnings):
        confidence = 0.3  # Very low confidence when positions shifted
    else:
        confidence = max(0.5, 1.0 - (position_mismatches / len(old_blocks)))

    return confidence, warnings


def update_block(block_id: str, new_block: Dict, api_key: str):
    """Update existing block (preserves comments)."""
    block_type = new_block['type']
    data = {block_type: new_block[block_type]}

    response = api_call(f'blocks/{block_id}', api_key, 'PATCH', data)
    return response


def create_block(parent_id: str, block: Dict, api_key: str):
    """Create new block."""
    data = {"children": [block]}
    response = api_call(f'blocks/{parent_id}/children', api_key, 'PATCH', data)
    return response


def delete_block(block_id: str, api_key: str):
    """Delete block (loses comments!)."""
    api_call(f'blocks/{block_id}', api_key, 'DELETE')


def sync_blocks(page_id: str, old_blocks: List[Dict], new_blocks: List[Dict],
                api_key: str, delete_removed: bool = False, force: bool = False):
    """Sync blocks with minimal changes.

    Args:
        page_id: Parent page ID
        old_blocks: Current blocks in page
        new_blocks: New blocks to sync
        api_key: Notion API key
        delete_removed: Whether to delete blocks not in new content
        force: Skip confidence checks and warnings
    """
    stats = {'updated': 0, 'created': 0, 'deleted': 0, 'unchanged': 0}

    # Check confidence in position-based matching
    if not force:
        confidence, warnings = compute_match_confidence(old_blocks, new_blocks)

        if warnings:
            print("\n⚠️  WARNING: Potential matching issues detected:", file=sys.stderr)
            for warning in warnings:
                print(f"  - {warning}", file=sys.stderr)

            if confidence < 0.8:
                print(f"\nMatching confidence: {confidence:.1%} (LOW)", file=sys.stderr)
                print("This may result in updating wrong blocks, losing comments!", file=sys.stderr)
                print("\nOptions:", file=sys.stderr)
                print("  1. Review the changes and use --force to proceed anyway", file=sys.stderr)
                print("  2. Use replace_page_content.py to clear and rewrite (loses all comments)", file=sys.stderr)
                print("  3. Manually update specific blocks with update_block.py", file=sys.stderr)

                response = input("\nProceed anyway? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("Cancelled", file=sys.stderr)
                    sys.exit(0)
            else:
                print(f"Matching confidence: {confidence:.1%}", file=sys.stderr)

    # Simple strategy: match by position and type
    for i in range(min(len(old_blocks), len(new_blocks))):
        old_block = old_blocks[i]
        new_block = new_blocks[i]

        if blocks_match(old_block, new_block):
            stats['unchanged'] += 1
            print(f"  [{i+1}] Unchanged", file=sys.stderr)
        else:
            # Update in place (preserves comments)
            print(f"  [{i+1}] Updating...", file=sys.stderr)
            update_block(old_block['id'], new_block, api_key)
            stats['updated'] += 1

    # New blocks to add
    if len(new_blocks) > len(old_blocks):
        print(f"  Adding {len(new_blocks) - len(old_blocks)} new blocks...", file=sys.stderr)
        for block in new_blocks[len(old_blocks):]:
            create_block(page_id, block, api_key)
            stats['created'] += 1

    # Old blocks to remove (only if --delete-removed)
    if delete_removed and len(old_blocks) > len(new_blocks):
        print(f"  ⚠️  Deleting {len(old_blocks) - len(new_blocks)} blocks (COMMENTS WILL BE LOST)...", file=sys.stderr)
        for block in old_blocks[len(new_blocks):]:
            delete_block(block['id'], api_key)
            stats['deleted'] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Sync page content (preserves comments)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('page_id', help='Page ID')
    parser.add_argument('json_file', help='JSON file with new blocks')
    parser.add_argument('--delete-removed', action='store_true',
                       help='Delete blocks not in new content (loses comments!)')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Skip confidence checks and warnings')

    args = parser.parse_args()

    try:
        api_key = load_api_key()
        page_id = parse_notion_id(args.page_id)

        json_path = Path(args.json_file)
        if not json_path.exists():
            print(f"Error: File not found: {json_path}", file=sys.stderr)
            sys.exit(1)

        # Load new blocks
        with open(json_path) as f:
            data = json.load(f)

        if isinstance(data, list):
            new_blocks = data
        elif 'blocks' in data:
            new_blocks = data['blocks']
        else:
            print("Error: JSON must be array or contain 'blocks' key", file=sys.stderr)
            sys.exit(1)

        # Get current blocks
        print("Fetching current page state...", file=sys.stderr)
        old_blocks = get_all_blocks(page_id, api_key)

        print(f"\nSyncing: {len(old_blocks)} old → {len(new_blocks)} new", file=sys.stderr)

        stats = sync_blocks(page_id, old_blocks, new_blocks, api_key, args.delete_removed, args.force)

        print(f"\n✓ Sync complete:", file=sys.stderr)
        print(f"  Unchanged: {stats['unchanged']}", file=sys.stderr)
        print(f"  Updated: {stats['updated']}", file=sys.stderr)
        print(f"  Created: {stats['created']}", file=sys.stderr)
        if stats['deleted'] > 0:
            print(f"  ⚠️  Deleted: {stats['deleted']} (comments lost)", file=sys.stderr)

        print(json.dumps({'success': True, **stats}, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
