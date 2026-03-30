#!/usr/bin/env python3
"""Shared utilities for Notion API scripts.

This module provides common functionality for all Notion scripts:
- Secure API key loading via 1Password CLI
- Standardized API calls with rate limiting and retry logic
- Notion ID parsing and validation
- Concurrent API helpers
- Error handling

Requirements: scripts are run via `uv run`, which resolves dependencies
from PEP 723 inline metadata in each entry-point script. This module is
imported as a sibling — no separate dependency declaration needed.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

_SKILL_DIR = Path(__file__).parent.parent


# Rate limiting: Notion API allows 3 requests per second
_RATE_LIMIT_CALLS = 3
_RATE_LIMIT_PERIOD = 1.0  # seconds
_last_call_times: list[float] = []
_rate_limit_lock = threading.Lock()


def rate_limit(func: Callable) -> Callable:
    """Decorator to enforce rate limiting (3 requests per second). Thread-safe.

    Computes the required sleep outside the lock so concurrent threads
    can overlap their waits instead of serializing through the lock.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        global _last_call_times
        sleep_time = 0.0

        with _rate_limit_lock:
            current_time = time.time()

            # Remove calls older than the rate limit period
            _last_call_times = [t for t in _last_call_times if current_time - t < _RATE_LIMIT_PERIOD]

            # If at limit, compute wait time but don't sleep yet
            if len(_last_call_times) >= _RATE_LIMIT_CALLS:
                sleep_time = _RATE_LIMIT_PERIOD - (current_time - _last_call_times[0])
                _last_call_times.pop(0)

            # Reserve our slot now (using projected time after sleep)
            _last_call_times.append(current_time + max(sleep_time, 0))

        # Sleep outside the lock so other threads can compute their waits
        if sleep_time > 0:
            time.sleep(sleep_time)

        return func(*args, **kwargs)

    return wrapper


_SECRETS_DIR = _SKILL_DIR / ".secrets"
_CACHED_KEY_FILE = _SECRETS_DIR / "notion_api_key"

# 1Password vault path for the Notion API key.
# Override with NOTION_OP_REF env var if your vault layout differs.
_OP_DEFAULT_REF = "op://it-ops-helpers/NOTION_SKILL_INTEGRATION/credential"


def _read_cached_key() -> str | None:
    """Read the cached API key from .secrets/notion_api_key."""
    if _CACHED_KEY_FILE.is_file():
        key = _CACHED_KEY_FILE.read_text().strip()
        if key:
            return key
    return None


def _cache_key(api_key: str) -> None:
    """Cache API key to .secrets/notion_api_key with restrictive permissions."""
    try:
        _SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(str(_SECRETS_DIR), 0o700)
        fd = os.open(str(_CACHED_KEY_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(api_key + "\n")
    except OSError as e:
        print(
            f"notion-skill: Warning: Could not cache API key: {e}",
            file=sys.stderr,
        )


def _require_op() -> str:
    """Return the path to the 1Password CLI binary, or raise."""
    from shutil import which

    op_bin = which("op")
    if not op_bin:
        raise RuntimeError(
            "1Password CLI (`op`) is required but not found in PATH.\n"
            "Install it: https://developer.1password.com/docs/cli/get-started/\n"
            "Then sign in: eval $(op signin)"
        )
    return op_bin


def _fetch_key_from_op() -> str:
    """Fetch the Notion API key from 1Password CLI.

    Raises:
        RuntimeError: If op CLI is missing or the lookup fails.
    """
    op_ref = os.environ.get("NOTION_OP_REF", _OP_DEFAULT_REF)
    op_bin = _require_op()

    try:
        result = subprocess.run(
            [op_bin, "read", op_ref],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            key = result.stdout.strip()
            if key:
                return key

        stderr = result.stderr.strip() if result.stderr else "unknown error"
        raise RuntimeError(
            f"1Password lookup failed: {stderr}\n"
            f"  Reference: {op_ref}\n"
            "  Make sure you are signed in: eval $(op signin)"
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("1Password CLI timed out after 30s. Is the app responsive?") from e
    except OSError as e:
        raise RuntimeError(f"Failed to run 1Password CLI: {e}") from e


def load_api_key() -> str:
    """Load Notion API key with cascading resolution.

    Resolution order:
      1. NOTION_API_KEY environment variable (fastest, covers chezmoi/dotfile users)
      2. Cached key in .secrets/notion_api_key (persists across sessions)
      3. 1Password CLI (`op read`) — fetched and cached for future use

    The 1Password CLI is a hard requirement. If the key is not in the
    environment or cache, `op` must be installed and authenticated.

    The cached key file is stored in the skill directory under .secrets/ with
    0600 permissions. Override the 1Password reference with NOTION_OP_REF env var.

    Returns:
        str: Notion API key

    Raises:
        RuntimeError: If op CLI is missing or lookup fails
    """
    # 1. Environment variable
    api_key = os.environ.get("NOTION_API_KEY")
    if api_key:
        return api_key

    # 2. Cached key file
    api_key = _read_cached_key()
    if api_key:
        return api_key

    # 3. 1Password CLI (required)
    api_key = _fetch_key_from_op()
    _cache_key(api_key)
    print(
        f"notion-skill: API key fetched from 1Password and cached to {_CACHED_KEY_FILE}",
        file=sys.stderr,
    )
    return api_key


def parse_notion_id(id_input: str) -> str:
    """Parse Notion ID from URL or ID string.

    Handles:
    - Full Notion URLs
    - UUID with or without dashes
    - Page IDs embedded in URLs

    Args:
        id_input: Notion URL or ID string

    Returns:
        str: Formatted UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

    Raises:
        ValueError: If input is not a valid Notion ID format
    """
    # Extract from URL if needed
    if id_input.startswith("http"):
        parsed = urlparse(id_input)
        path_parts = parsed.path.rstrip("/").split("/")
        id_input = path_parts[-1]
        # Handle URLs like /Page-Name-abc123def456...
        if "-" in id_input:
            parts = id_input.split("-")
            id_input = parts[-1]

    # Remove dashes
    clean_id = id_input.replace("-", "")

    # Validate format (32 hex characters)
    if not re.match(r"^[0-9a-f]{32}$", clean_id, re.IGNORECASE):
        raise ValueError(f"Invalid Notion ID format: {id_input}")

    # Format as UUID
    return f"{clean_id[:8]}-{clean_id[8:12]}-{clean_id[12:16]}-{clean_id[16:20]}-{clean_id[20:]}"


@rate_limit
def api_call(
    endpoint: str,
    api_key: str,
    method: str = "GET",
    data: dict | None = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> dict[str, Any]:
    """Make a Notion API call with rate limiting and retry logic.

    Args:
        endpoint: API endpoint (e.g., 'pages/123' or 'blocks/456/children')
        api_key: Notion API key
        method: HTTP method (GET, POST, PATCH, DELETE)
        data: Request body for POST/PATCH requests
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (exponential backoff)

    Returns:
        dict: API response as JSON

    Raises:
        requests.RequestException: If API call fails after retries
        ValueError: If response is not valid JSON
    """
    url = f"https://api.notion.com/v1/{endpoint}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    for attempt in range(max_retries):
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Try to parse response as JSON
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON response from API: {e}\nResponse text: {response.text[:200]}") from e

            # Check for API errors
            if response.status_code == 429:  # Rate limited
                retry_after = float(response.headers.get("Retry-After", retry_delay * (2**attempt)))
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
                else:
                    raise requests.RequestException(f"Rate limited: {result.get('message', 'Too many requests')}")

            if response.status_code >= 400:
                error_msg = result.get("message", f"HTTP {response.status_code}")
                if attempt < max_retries - 1 and response.status_code >= 500:
                    # Retry server errors
                    time.sleep(retry_delay * (2**attempt))
                    continue
                else:
                    raise requests.RequestException(f"API error: {error_msg}")

            return result

        except requests.Timeout:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2**attempt))
                continue
            else:
                raise
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2**attempt))
                continue
            else:
                raise

    raise requests.RequestException(f"Failed after {max_retries} attempts")


def extract_rich_text(rich_text: list[dict]) -> str:
    """Extract plain text from Notion rich_text array.

    Args:
        rich_text: Notion rich_text array

    Returns:
        str: Concatenated plain text
    """
    if not rich_text:
        return ""
    return "".join([rt.get("plain_text", "") for rt in rich_text])


def get_all_blocks(block_id: str, api_key: str) -> list[dict[str, Any]]:
    """Get all blocks recursively with pagination support.

    Fetches children concurrently for blocks that have them.

    Args:
        block_id: Parent block/page ID
        api_key: Notion API key

    Returns:
        list: All blocks with nested children
    """
    blocks = []
    cursor = None

    while True:
        endpoint = f"blocks/{block_id}/children?page_size=100"
        if cursor:
            endpoint += f"&start_cursor={cursor}"

        response = api_call(endpoint, api_key)

        if "results" in response:
            blocks.extend(response["results"])

        if not response.get("has_more", False):
            break

        cursor = response.get("next_cursor")

    # Fetch children concurrently for blocks that have them
    blocks_with_children = [b for b in blocks if b.get("has_children")]
    if blocks_with_children:

        def fetch_children(block):
            children = get_all_blocks(block["id"], api_key)
            return block["id"], children

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_children, b): b for b in blocks_with_children}
            children_map = {}
            for future in as_completed(futures):
                try:
                    bid, children = future.result()
                    children_map[bid] = children
                except Exception as e:
                    failed_block = futures[future]
                    print(
                        f"  Warning: Failed to fetch children of block "
                        f"{failed_block['id']} "
                        f"(type={failed_block.get('type', 'unknown')}): {e}",
                        file=sys.stderr,
                    )

            for block in blocks:
                if block["id"] in children_map:
                    block["children"] = children_map[block["id"]]

    return blocks


# Markdown Conversion Functions


def _make_rich_text_item(
    content: str,
    annotations: dict[str, bool] | None = None,
    url: str | None = None,
) -> dict:
    """Build a single Notion rich_text item.

    Args:
        content: Text content
        annotations: Optional formatting (bold, italic, code, etc.)
        url: Optional link URL

    Returns:
        dict: Notion rich_text item
    """
    text_obj: dict[str, Any] = {"content": content}
    if url:
        text_obj["link"] = {"url": url}

    item: dict[str, Any] = {"type": "text", "text": text_obj}
    if annotations:
        item["annotations"] = annotations
    return item


def _parse_inline_formatting(text: str, url: str | None = None) -> list[dict]:
    """Parse inline markdown formatting (**bold**, *italic*, `code`).

    This handles the inner formatting within a text segment. If url is
    provided, all generated rich_text items will include the link.

    Args:
        text: Text with possible inline formatting
        url: Optional link URL to attach to all items

    Returns:
        list: Notion rich_text items
    """
    if not text:
        return [_make_rich_text_item("", url=url)]

    result = []
    i = 0

    while i < len(text):
        # Check for ***bold italic*** or ___bold italic___
        if text[i : i + 3] == "***" or text[i : i + 3] == "___":
            marker = text[i : i + 3]
            end = text.find(marker, i + 3)
            if end != -1:
                content = text[i + 3 : end]
                result.append(_make_rich_text_item(content, {"bold": True, "italic": True}, url=url))
                i = end + 3
                continue

        # Check for **bold**
        if text[i : i + 2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                content = text[i + 2 : end]
                result.append(_make_rich_text_item(content, {"bold": True}, url=url))
                i = end + 2
                continue

        # Check for `code`
        if text[i] == "`" and (i + 1 < len(text)) and text[i + 1] != "`":
            end = text.find("`", i + 1)
            if end != -1:
                content = text[i + 1 : end]
                result.append(_make_rich_text_item(content, {"code": True}, url=url))
                i = end + 1
                continue

        # Check for *italic* (but not **)
        if text[i] == "*" and (i + 1 < len(text)) and text[i + 1] != "*":
            end = text.find("*", i + 1)
            if end != -1 and text[end - 1 : end + 1] != "**":
                content = text[i + 1 : end]
                result.append(_make_rich_text_item(content, {"italic": True}, url=url))
                i = end + 1
                continue
            # No closing * found — treat this * as literal text, advance past it
            # to prevent infinite loop
            i += 1
            continue

        # Regular text - collect until next special char
        start = i
        while i < len(text):
            if text[i : i + 3] in ("***", "___"):
                break
            if text[i : i + 2] == "**":
                break
            if text[i] == "`":
                break
            if text[i] == "*" and (i + 1 >= len(text) or text[i + 1] != "*"):
                break
            i += 1

        if i > start:
            result.append(_make_rich_text_item(text[start:i], url=url))

    return result if result else [_make_rich_text_item(text, url=url)]


def create_rich_text(text: str) -> list[dict]:
    """Create rich_text array from text with inline markdown formatting.

    Supports:
    - **bold**
    - *italic*
    - ***bold italic***
    - `code`
    - [link text](url)
    - [**bold link**](url) (formatting inside links)

    Args:
        text: Plain text with inline markdown

    Returns:
        list: Notion rich_text array
    """
    if not text:
        return [_make_rich_text_item("")]

    # First pass: split text into segments that are either markdown links
    # or plain text (which may contain inline formatting).
    # Pattern matches [text](url) but not ![text](url) (images)
    link_pattern = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")

    result: list[dict] = []
    last_end = 0

    for match in link_pattern.finditer(text):
        # Process any text before this link
        before = text[last_end : match.start()]
        if before:
            result.extend(_parse_inline_formatting(before))

        # Process the link — inner text may have formatting
        link_text = match.group(1)
        link_url = match.group(2)
        result.extend(_parse_inline_formatting(link_text, url=link_url))

        last_end = match.end()

    # Process any remaining text after the last link
    remaining = text[last_end:]
    if remaining:
        result.extend(_parse_inline_formatting(remaining))

    return result if result else [_make_rich_text_item(text)]


def parse_table_row(line: str) -> list[str]:
    """Parse a markdown table row into cells."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_table_separator(line: str) -> bool:
    """Check if line is a markdown table separator (|---|---|)."""
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return False
    content = line.replace("|", "").replace("-", "").replace(":", "").strip()
    return len(content) == 0 and "-" in line


def is_table_row(line: str) -> bool:
    """Check if line looks like a markdown table row."""
    line = line.strip()
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def create_table_block(rows: list[list[str]]) -> dict[str, Any] | None:
    """Create a Notion table block from parsed rows."""
    if not rows:
        return None

    num_cols = max(len(row) for row in rows)

    table_rows = []
    for row in rows:
        # Pad row to have correct number of columns
        while len(row) < num_cols:
            row.append("")

        cells = []
        for cell in row[:num_cols]:
            cells.append(create_rich_text(cell))

        table_rows.append({"object": "block", "type": "table_row", "table_row": {"cells": cells}})

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": num_cols,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def _get_indent_level(line: str) -> int:
    """Get the indentation level of a line (number of leading spaces / 2, or tabs)."""
    stripped = line.lstrip()
    indent = len(line) - len(stripped)
    # Tabs count as one level, spaces count as level per 2 (common indent)
    if "\t" in line[:indent]:
        return line[:indent].count("\t")
    return indent // 2


def _parse_list_item(line: str) -> dict[str, Any] | None:
    """Parse a single list line into a Notion block (without children).

    Returns None if the line is not a list item.
    """
    stripped = line.strip()

    # Todo items (checked)
    if stripped.startswith("- [x] ") or stripped.startswith("- [X] "):
        return {
            "object": "block",
            "type": "to_do",
            "to_do": {"rich_text": create_rich_text(stripped[6:]), "checked": True},
        }

    # Todo items (unchecked)
    if stripped.startswith("- [ ] "):
        return {
            "object": "block",
            "type": "to_do",
            "to_do": {"rich_text": create_rich_text(stripped[6:]), "checked": False},
        }

    # Bulleted list
    if stripped.startswith("- ") or stripped.startswith("* "):
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": create_rich_text(stripped[2:])},
        }

    # Numbered list
    m = re.match(r"^\d+\.\s+(.*)", stripped)
    if m:
        return {
            "object": "block",
            "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": create_rich_text(m.group(1))},
        }

    return None


def _is_list_line(line: str) -> bool:
    """Check if a line is any kind of list item (bullet, numbered, todo)."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("- ") or stripped.startswith("* "):
        return True
    if re.match(r"^\d+\.\s", stripped):
        return True
    return False


def _collect_nested_list(lines: list[str], start: int, base_indent: int) -> tuple[list[dict[str, Any]], int]:
    """Collect a run of list items starting at `start`, building nested children.

    Processes list items at `base_indent` level and any indented sub-items
    as children of the preceding item.

    Args:
        lines: All document lines
        start: Starting line index
        base_indent: Indentation level of the parent context

    Returns:
        (blocks, next_index): list of Notion blocks, and the next line to process
    """
    blocks: list[dict[str, Any]] = []
    i = start

    while i < len(lines):
        line = lines[i]

        # Stop on empty lines or non-list content at/below base indent
        if not line.strip():
            # Blank line might separate list groups — peek ahead
            # If the next non-blank line is still a list item at the same
            # or deeper indent, continue. Otherwise, break.
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _is_list_line(lines[j]):
                indent = _get_indent_level(lines[j])
                if indent >= base_indent:
                    i = j
                    continue
            break

        indent = _get_indent_level(line)

        # If this line is less indented than our base, it belongs to parent
        if indent < base_indent:
            break

        # If this line is more indented, it's a child of the last block
        if indent > base_indent and blocks:
            children, new_i = _collect_nested_list(lines, i, indent)
            if children:
                last_block = blocks[-1]
                block_type = last_block["type"]
                if "children" not in last_block[block_type]:
                    last_block[block_type]["children"] = []
                last_block[block_type]["children"].extend(children)
            # Guard against infinite loop: if no progress was made, skip line
            if new_i <= i:
                i += 1
            else:
                i = new_i
            continue

        # Parse list item at our level
        item = _parse_list_item(line)
        if item:
            blocks.append(item)
            i += 1
        else:
            # Not a list item at this level — stop
            break

    return blocks, i


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    """Convert markdown to Notion block format.

    Supported:
    - # Heading 1, ## Heading 2, ### Heading 3
    - Paragraphs
    - - Bullet lists (with nesting via indentation)
    - 1. Numbered lists (with nesting via indentation)
    - - [ ] Todo items (with nesting via indentation)
    - - [x] Completed todos
    - [link text](url) — inline links
    - ```code blocks```
    - > Quotes
    - --- Dividers
    - | Tables |
    - ![alt](url) — Images

    Args:
        markdown: Markdown text

    Returns:
        list: Notion blocks
    """
    blocks = []
    lines = markdown.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Table detection
        if is_table_row(line):
            table_rows = []
            while i < len(lines) and (is_table_row(lines[i]) or is_table_separator(lines[i])):
                if not is_table_separator(lines[i]):
                    table_rows.append(parse_table_row(lines[i]))
                i += 1

            if table_rows:
                table_block = create_table_block(table_rows)
                if table_block:
                    blocks.append(table_block)
            continue

        # Headings
        if line.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": create_rich_text(line[4:])},
                }
            )
        elif line.startswith("## "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": create_rich_text(line[3:])},
                }
            )
        elif line.startswith("# "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": create_rich_text(line[2:])},
                }
            )

        # List items (bullet, numbered, todo) — handled together for nesting
        elif _is_list_line(line):
            indent = _get_indent_level(line)
            nested_blocks, i = _collect_nested_list(lines, i, indent)
            blocks.extend(nested_blocks)
            continue  # _collect_nested_list already advanced i

        # Code block
        elif line.strip().startswith("```"):
            language = line.strip()[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code = "\n".join(code_lines)
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code}}],
                        "language": language,
                    },
                }
            )

        # Quote
        elif line.strip().startswith("> "):
            text = line.strip()[2:]
            blocks.append(
                {
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": create_rich_text(text)},
                }
            )

        # Divider
        elif line.strip() in ["---", "***", "___"]:
            blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Image - ![alt text](url)
        elif line.strip().startswith("!["):
            match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
            if match:
                # alt_text = match.group(1)  # Notion doesn't support alt text in API
                url = match.group(2)
                blocks.append(
                    {
                        "object": "block",
                        "type": "image",
                        "image": {"type": "external", "external": {"url": url}},
                    }
                )
            else:
                # Invalid image syntax, treat as paragraph
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": create_rich_text(line)},
                    }
                )

        # Paragraph (default)
        else:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": create_rich_text(line)},
                }
            )

        i += 1

    return blocks


# ── Concurrency helpers ─────────────────────────────────────────────


def concurrent_api_calls(
    items: list[Any],
    fn: Callable[[Any], Any],
    max_workers: int = 3,
    label: str = "items",
) -> list[tuple[Any, Any]]:
    """Run API calls concurrently while respecting rate limits.

    The rate_limit decorator on api_call handles per-request throttling.
    We cap workers at 3 (Notion's rate limit) to avoid excessive queuing.

    Args:
        items: Items to process
        fn: Function to call for each item. Receives one item, returns result.
        max_workers: Max concurrent threads (default 3, matching Notion rate limit)
        label: Label for progress messages

    Returns:
        List of (item, result) tuples in completion order
    """
    results: list[tuple[Any, Any]] = []
    failed_count = 0
    total = len(items)

    with ThreadPoolExecutor(max_workers=min(max_workers, total or 1)) as executor:
        future_to_item = {executor.submit(fn, item): item for item in items}

        for i, future in enumerate(as_completed(future_to_item), 1):
            item = future_to_item[future]
            try:
                result = future.result()
                results.append((item, result))
            except Exception as e:
                print(f"  Error processing {label} {i}/{total}: {e}", file=sys.stderr)
                results.append((item, None))
                failed_count += 1

            if i % 10 == 0 or i == total:
                print(f"  Processed {i}/{total} {label}...", file=sys.stderr)

    if failed_count:
        print(
            f"  Warning: {failed_count}/{total} {label} failed",
            file=sys.stderr,
        )

    return results


def concurrent_deletes(
    block_ids: list[str],
    api_key: str,
    max_workers: int = 3,
) -> tuple[int, int]:
    """Delete multiple blocks concurrently.

    Args:
        block_ids: List of block IDs to delete
        api_key: Notion API key
        max_workers: Max concurrent threads

    Returns:
        Tuple of (deleted_count, failed_count)
    """

    def delete_one(block_id: str) -> bool:
        try:
            response = api_call(f"blocks/{block_id}", api_key, "DELETE")
            if response.get("object") == "error":
                print(
                    f"  Error deleting {block_id}: {response.get('message')}",
                    file=sys.stderr,
                )
                return False
            return True
        except Exception as e:
            print(f"  Error deleting {block_id}: {e}", file=sys.stderr)
            return False

    results = concurrent_api_calls(block_ids, delete_one, max_workers=max_workers, label="blocks")

    deleted = sum(1 for _, success in results if success)
    failed = sum(1 for _, success in results if not success)
    return deleted, failed


def is_interactive() -> bool:
    """Check if running in an interactive terminal (not piped/agent context)."""
    return sys.stdin.isatty() and sys.stderr.isatty()
