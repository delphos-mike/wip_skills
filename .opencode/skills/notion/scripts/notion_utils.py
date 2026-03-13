#!/usr/bin/env python3
"""Shared utilities for Notion API scripts.

This module provides common functionality for all Notion scripts:
- Automatic virtual environment setup (zero manual bootstrap)
- Secure API key loading (never exposed in process arguments)
- Standardized API calls with rate limiting and retry logic
- Notion ID parsing and validation
- Concurrent API helpers
- Error handling
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

# ── Auto-bootstrap: ensure we're running in the skill's venv ────────
#
# When an agent runs `python3 read_page.py`, the system python has no
# `requests` installed. This block detects that, creates the skill's
# venv (using uv or stdlib venv), installs deps, and re-execs the
# original command under the venv's python. The re-exec only happens
# once — the second invocation lands inside the venv and skips this.

_SKILL_DIR = Path(__file__).parent.parent
_VENV_DIR = _SKILL_DIR / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python3"
_REQUIREMENTS = _SKILL_DIR / "requirements.txt"


def _is_inside_venv() -> bool:
    """Check if we're running inside the skill's virtual environment."""
    # sys.prefix changes when a venv is active
    return sys.prefix == str(_VENV_DIR) or str(_VENV_DIR) in sys.prefix


def _bootstrap_and_reexec() -> None:
    """Create the venv, install deps, and re-exec the current script."""
    print("notion-skill: first run — setting up Python environment...", file=sys.stderr)

    if not _VENV_DIR.exists():
        # Prefer uv for speed (creates venv + installs in one shot)
        uv = _find_uv()
        if uv:
            print(f"notion-skill: creating venv with uv...", file=sys.stderr)
            subprocess.check_call(
                [uv, "venv", str(_VENV_DIR), "--quiet"],
                stdout=sys.stderr,
            )
            if _REQUIREMENTS.exists():
                subprocess.check_call(
                    [
                        uv,
                        "pip",
                        "install",
                        "--quiet",
                        "-r",
                        str(_REQUIREMENTS),
                        "--python",
                        str(_VENV_PYTHON),
                    ],
                    stdout=sys.stderr,
                )
            else:
                subprocess.check_call(
                    [
                        uv,
                        "pip",
                        "install",
                        "--quiet",
                        "requests",
                        "--python",
                        str(_VENV_PYTHON),
                    ],
                    stdout=sys.stderr,
                )
        else:
            # Fallback to stdlib venv + pip
            print(
                f"notion-skill: creating venv with python3 -m venv...", file=sys.stderr
            )
            subprocess.check_call(
                [sys.executable, "-m", "venv", str(_VENV_DIR)],
                stdout=sys.stderr,
            )
            pip = str(_VENV_DIR / "bin" / "pip")
            if _REQUIREMENTS.exists():
                subprocess.check_call(
                    [pip, "install", "--quiet", "-r", str(_REQUIREMENTS)],
                    stdout=sys.stderr,
                )
            else:
                subprocess.check_call(
                    [pip, "install", "--quiet", "requests"],
                    stdout=sys.stderr,
                )

    print("notion-skill: environment ready, restarting...", file=sys.stderr)

    # Re-exec the original command under the venv's python
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON)] + sys.argv)


def _find_uv() -> str | None:
    """Find uv binary if available."""
    # Check common locations
    for candidate in [
        os.path.expanduser("~/.local/bin/uv"),
        os.path.expanduser("~/.cargo/bin/uv"),
        "/usr/local/bin/uv",
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # Check PATH
    from shutil import which

    return which("uv")


# Run the bootstrap check before importing anything that needs pip packages
if not _is_inside_venv() and _VENV_PYTHON.exists():
    # Venv exists but we're not in it — re-exec directly
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON)] + sys.argv)
elif not _is_inside_venv():
    # No venv at all — bootstrap then re-exec
    try:
        _bootstrap_and_reexec()
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"notion-skill: auto-bootstrap failed: {e}", file=sys.stderr)
        print(
            f"notion-skill: run manually: cd {_SKILL_DIR} && ./scripts/bootstrap",
            file=sys.stderr,
        )
        sys.exit(1)

# ── If we get here, we're inside the venv. Safe to import pip packages. ──

from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    # This should never happen after bootstrap, but just in case
    print("Error: 'requests' library not found even after bootstrap.", file=sys.stderr)
    print(f"  Try: cd {_SKILL_DIR} && ./scripts/bootstrap", file=sys.stderr)
    sys.exit(1)


# Rate limiting: Notion API allows 3 requests per second
_RATE_LIMIT_CALLS = 3
_RATE_LIMIT_PERIOD = 1.0  # seconds
_last_call_times: List[float] = []
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
            _last_call_times = [
                t for t in _last_call_times if current_time - t < _RATE_LIMIT_PERIOD
            ]

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


def load_api_key() -> str:
    """Load Notion API key from NOTION_API_KEY environment variable.

    Returns:
        str: Notion API key

    Raises:
        ValueError: If NOTION_API_KEY is not set
    """
    api_key = os.environ.get("NOTION_API_KEY")
    if api_key:
        return api_key

    raise ValueError(
        "NOTION_API_KEY environment variable is not set. "
        "Export it or add it to your shell profile."
    )


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
    data: Optional[Dict] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Dict[str, Any]:
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
                raise ValueError(
                    f"Invalid JSON response from API: {e}\nResponse text: {response.text[:200]}"
                )

            # Check for API errors
            if response.status_code == 429:  # Rate limited
                retry_after = int(
                    response.headers.get("Retry-After", retry_delay * (2**attempt))
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
                else:
                    raise requests.RequestException(
                        f"Rate limited: {result.get('message', 'Too many requests')}"
                    )

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


def extract_rich_text(rich_text: List[Dict]) -> str:
    """Extract plain text from Notion rich_text array.

    Args:
        rich_text: Notion rich_text array

    Returns:
        str: Concatenated plain text
    """
    if not rich_text:
        return ""
    return "".join([rt.get("plain_text", "") for rt in rich_text])


def get_all_blocks(block_id: str, api_key: str) -> List[Dict[str, Any]]:
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
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_children(block):
            children = get_all_blocks(block["id"], api_key)
            return block["id"], children

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(fetch_children, b): b for b in blocks_with_children
            }
            children_map = {}
            for future in as_completed(futures):
                try:
                    bid, children = future.result()
                    children_map[bid] = children
                except Exception:
                    pass  # Skip failed child fetches

            for block in blocks:
                if block["id"] in children_map:
                    block["children"] = children_map[block["id"]]

    return blocks


# Markdown Conversion Functions


def create_rich_text(text: str) -> List[Dict]:
    """Create rich_text array from text with inline markdown formatting.

    Supports:
    - **bold**
    - *italic*
    - `code`

    Args:
        text: Plain text with inline markdown

    Returns:
        list: Notion rich_text array
    """
    if not text:
        return [{"type": "text", "text": {"content": ""}}]

    result = []
    i = 0

    while i < len(text):
        # Check for **bold**
        if text[i : i + 2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                content = text[i + 2 : end]
                result.append(
                    {
                        "type": "text",
                        "text": {"content": content},
                        "annotations": {"bold": True},
                    }
                )
                i = end + 2
                continue

        # Check for `code`
        if text[i] == "`" and (i + 1 < len(text)) and text[i + 1] != "`":
            end = text.find("`", i + 1)
            if end != -1:
                content = text[i + 1 : end]
                result.append(
                    {
                        "type": "text",
                        "text": {"content": content},
                        "annotations": {"code": True},
                    }
                )
                i = end + 1
                continue

        # Check for *italic* (but not **)
        if text[i] == "*" and (i + 1 < len(text)) and text[i + 1] != "*":
            end = text.find("*", i + 1)
            if end != -1 and text[end - 1 : end + 1] != "**":
                content = text[i + 1 : end]
                result.append(
                    {
                        "type": "text",
                        "text": {"content": content},
                        "annotations": {"italic": True},
                    }
                )
                i = end + 1
                continue

        # Regular text - collect until next special char
        start = i
        while i < len(text):
            if text[i : i + 2] == "**":
                break
            if text[i] == "`":
                break
            if text[i] == "*" and (i + 1 >= len(text) or text[i + 1] != "*"):
                break
            i += 1

        if i > start:
            result.append({"type": "text", "text": {"content": text[start:i]}})

    return result if result else [{"type": "text", "text": {"content": text}}]


def parse_table_row(line: str) -> List[str]:
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


def create_table_block(rows: List[List[str]]) -> Optional[Dict[str, Any]]:
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

        table_rows.append(
            {"object": "block", "type": "table_row", "table_row": {"cells": cells}}
        )

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


def markdown_to_blocks(markdown: str) -> List[Dict[str, Any]]:
    """Convert markdown to Notion block format.

    Supported:
    - # Heading 1, ## Heading 2, ### Heading 3
    - Paragraphs
    - - Bullet lists
    - 1. Numbered lists
    - - [ ] Todo items
    - - [x] Completed todos
    - ```code blocks```
    - > Quotes
    - --- Dividers
    - | Tables |

    Args:
        markdown: Markdown text

    Returns:
        list: Notion blocks
    """
    import re

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
            while i < len(lines) and (
                is_table_row(lines[i]) or is_table_separator(lines[i])
            ):
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

        # Todo items
        elif line.strip().startswith("- [x] ") or line.strip().startswith("- [X] "):
            text = line.strip()[6:]
            blocks.append(
                {
                    "object": "block",
                    "type": "to_do",
                    "to_do": {"rich_text": create_rich_text(text), "checked": True},
                }
            )
        elif line.strip().startswith("- [ ] "):
            text = line.strip()[6:]
            blocks.append(
                {
                    "object": "block",
                    "type": "to_do",
                    "to_do": {"rich_text": create_rich_text(text), "checked": False},
                }
            )

        # Bulleted list
        elif line.strip().startswith("- ") or line.strip().startswith("* "):
            text = line.strip()[2:]
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": create_rich_text(text)},
                }
            )

        # Numbered list
        elif re.match(r"^\s*\d+\.\s", line):
            text = re.sub(r"^\s*\d+\.\s", "", line)
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": create_rich_text(text)},
                }
            )

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
                    "code": {"rich_text": create_rich_text(code), "language": language},
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
    items: List[Any],
    fn: Callable[[Any], Any],
    max_workers: int = 3,
    label: str = "items",
) -> List[Tuple[Any, Any]]:
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
    results: List[Tuple[Any, Any]] = []
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

            if i % 10 == 0 or i == total:
                print(f"  Processed {i}/{total} {label}...", file=sys.stderr)

    return results


def concurrent_deletes(
    block_ids: List[str],
    api_key: str,
    max_workers: int = 3,
) -> Tuple[int, int]:
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

    results = concurrent_api_calls(
        block_ids, delete_one, max_workers=max_workers, label="blocks"
    )

    deleted = sum(1 for _, success in results if success)
    failed = sum(1 for _, success in results if not success)
    return deleted, failed


def is_interactive() -> bool:
    """Check if running in an interactive terminal (not piped/agent context)."""
    return sys.stdin.isatty() and sys.stderr.isatty()
