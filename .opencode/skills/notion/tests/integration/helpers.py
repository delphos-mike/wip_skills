"""Shared test helpers for integration tests."""

from notion_utils import api_call, concurrent_deletes


def clear_page(api_key: str, page_id: str) -> None:
    """Delete all blocks from the page."""
    blocks = get_top_blocks(api_key, page_id)
    if blocks:
        ids = [b["id"] for b in blocks]
        deleted, failed = concurrent_deletes(ids, api_key)
        if failed:
            raise RuntimeError(f"Failed to delete {failed} blocks during test cleanup (deleted {deleted} successfully)")


def get_top_blocks(api_key: str, page_id: str) -> list:
    """Fetch all top-level blocks from a page."""
    blocks = []
    cursor = None
    while True:
        endpoint = f"blocks/{page_id}/children?page_size=100"
        if cursor:
            endpoint += f"&start_cursor={cursor}"
        resp = api_call(endpoint, api_key)
        blocks.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return blocks


def append_blocks(api_key: str, page_id: str, blocks: list) -> int:
    """Append Notion blocks to a page (batched at 100)."""
    for i in range(0, len(blocks), 100):
        batch = blocks[i : i + 100]
        api_call(
            f"blocks/{page_id}/children",
            api_key,
            method="PATCH",
            data={"children": batch},
        )
    return len(blocks)
