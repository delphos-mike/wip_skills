"""Unit tests for read_page block rendering functions.

Tests block_to_markdown and block_to_text with synthetic Notion API block
structures — no network calls needed.
"""

from read_page import block_to_markdown, block_to_text

# ── Helpers ──────────────────────────────────────────────────────────


def _rich_text(text: str) -> list:
    """Build a minimal Notion rich_text array."""
    return [{"type": "text", "text": {"content": text}, "plain_text": text}]


def _table_row_block(cells: list[str]) -> dict:
    """Build a table_row block from a list of cell strings."""
    return {
        "type": "table_row",
        "table_row": {
            "cells": [_rich_text(cell) for cell in cells],
        },
    }


def _table_block(
    rows: list[list[str]],
    has_column_header: bool = True,
    has_row_header: bool = False,
) -> dict:
    """Build a table block with children from row data."""
    children = [_table_row_block(row) for row in rows]
    return {
        "type": "table",
        "table": {
            "table_width": max(len(r) for r in rows),
            "has_column_header": has_column_header,
            "has_row_header": has_row_header,
        },
        "children": children,
    }


# ── block_to_markdown: table tests ──────────────────────────────────


class TestTableToMarkdown:
    """Tables render as pipe-delimited markdown tables."""

    def test_basic_table_with_header(self):
        block = _table_block(
            [["Name", "Score"], ["Alice", "95"], ["Bob", "87"]],
            has_column_header=True,
        )
        result = block_to_markdown(block)
        lines = result.split("\n")

        assert lines[0] == "| Name | Score |"
        assert lines[1] == "| --- | --- |"
        assert lines[2] == "| Alice | 95 |"
        assert lines[3] == "| Bob | 87 |"
        assert len(lines) == 4

    def test_table_without_header(self):
        block = _table_block(
            [["Alice", "95"], ["Bob", "87"]],
            has_column_header=False,
        )
        result = block_to_markdown(block)
        lines = result.split("\n")

        # No separator row
        assert lines[0] == "| Alice | 95 |"
        assert lines[1] == "| Bob | 87 |"
        assert len(lines) == 2

    def test_single_column_table(self):
        block = _table_block(
            [["Header"], ["Value"]],
            has_column_header=True,
        )
        result = block_to_markdown(block)
        lines = result.split("\n")

        assert lines[0] == "| Header |"
        assert lines[1] == "| --- |"
        assert lines[2] == "| Value |"

    def test_empty_cells(self):
        block = _table_block(
            [["A", "B"], ["", "data"], ["data", ""]],
            has_column_header=True,
        )
        result = block_to_markdown(block)
        lines = result.split("\n")

        assert lines[0] == "| A | B |"
        assert lines[2] == "|  | data |"
        assert lines[3] == "| data |  |"

    def test_table_no_children(self):
        """A table block with no children produces empty output."""
        block = {
            "type": "table",
            "table": {
                "table_width": 2,
                "has_column_header": True,
            },
            # No 'children' key — e.g. if recursive fetch failed
        }
        result = block_to_markdown(block)
        assert result == ""

    def test_wide_table(self):
        """Tables with many columns render correctly."""
        block = _table_block(
            [
                ["A", "B", "C", "D", "E"],
                ["1", "2", "3", "4", "5"],
            ],
            has_column_header=True,
        )
        result = block_to_markdown(block)
        lines = result.split("\n")

        assert lines[0] == "| A | B | C | D | E |"
        assert lines[1] == "| --- | --- | --- | --- | --- |"
        assert lines[2] == "| 1 | 2 | 3 | 4 | 5 |"

    def test_table_does_not_recurse_children_generically(self):
        """Table rows must not be passed through generic child handling.

        If the table handler didn't return early, the generic children loop
        would try to render table_row blocks as regular blocks, producing
        garbage output.
        """
        block = _table_block(
            [["Name", "Score"], ["Alice", "95"]],
            has_column_header=True,
        )
        result = block_to_markdown(block)

        # Should NOT contain indented child output from generic handler
        assert "  " not in result  # no indented lines from child recursion


# ── block_to_text: table tests ──────────────────────────────────────


class TestTableToText:
    """Tables render as tab-separated values in text mode."""

    def test_basic_table(self):
        block = _table_block(
            [["Name", "Score"], ["Alice", "95"], ["Bob", "87"]],
        )
        result = block_to_text(block)
        lines = result.split("\n")

        assert lines[0] == "Name\tScore"
        assert lines[1] == "Alice\t95"
        assert lines[2] == "Bob\t87"
        assert len(lines) == 3

    def test_empty_cells_text(self):
        block = _table_block(
            [["A", "B"], ["", "data"]],
        )
        result = block_to_text(block)
        lines = result.split("\n")

        assert lines[0] == "A\tB"
        assert lines[1] == "\tdata"

    def test_table_no_children_text(self):
        block = {
            "type": "table",
            "table": {"table_width": 2, "has_column_header": True},
        }
        result = block_to_text(block)
        assert result == ""


# ── block_to_markdown: image tests ───────────────────────────────────


class TestImageToMarkdown:
    """Images render as markdown image syntax."""

    def test_external_image_no_caption(self):
        block = {
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": "https://example.com/photo.png"},
                "caption": [],
            },
        }
        result = block_to_markdown(block)
        assert result == "![](https://example.com/photo.png)"

    def test_external_image_with_caption(self):
        block = {
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": "https://example.com/photo.png"},
                "caption": _rich_text("A nice photo"),
            },
        }
        result = block_to_markdown(block)
        assert result == "![A nice photo](https://example.com/photo.png)"

    def test_file_image(self):
        """Notion-hosted images use the 'file' key instead of 'external'."""
        block = {
            "type": "image",
            "image": {
                "type": "file",
                "file": {"url": "https://prod-files-secure.s3.amazonaws.com/abc123"},
                "caption": [],
            },
        }
        result = block_to_markdown(block)
        assert "https://prod-files-secure.s3.amazonaws.com/abc123" in result

    def test_image_no_url(self):
        """Image block with no URL produces empty output."""
        block = {
            "type": "image",
            "image": {"type": "external", "external": {}, "caption": []},
        }
        result = block_to_markdown(block)
        assert result == ""

    def test_image_to_text_is_empty(self):
        """Images have no rich_text, so text mode produces nothing."""
        block = {
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": "https://example.com/photo.png"},
                "caption": [],
            },
        }
        result = block_to_text(block)
        assert result == ""


# ── Non-table blocks still work ─────────────────────────────────────


class TestNonTableBlocksUnchanged:
    """Verify existing block types aren't broken by the table additions."""

    def test_paragraph(self):
        block = {"type": "paragraph", "paragraph": {"rich_text": _rich_text("Hello world")}}
        assert block_to_markdown(block) == "Hello world"

    def test_heading(self):
        block = {"type": "heading_2", "heading_2": {"rich_text": _rich_text("Title")}}
        assert block_to_markdown(block) == "## Title"

    def test_bullet(self):
        block = {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": _rich_text("Item")},
        }
        assert block_to_markdown(block) == "- Item"

    def test_code(self):
        block = {
            "type": "code",
            "code": {"rich_text": _rich_text("print('hi')"), "language": "python"},
        }
        result = block_to_markdown(block)
        assert "```python" in result
        assert "print('hi')" in result

    def test_divider(self):
        block = {"type": "divider", "divider": {}}
        assert block_to_markdown(block) == "---"

    def test_unknown_block_type_silent(self):
        """Unknown block types produce empty output (not an error)."""
        block = {"type": "unsupported_widget", "unsupported_widget": {}}
        assert block_to_markdown(block) == ""
        assert block_to_text(block) == ""
