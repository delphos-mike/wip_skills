"""Integration tests: markdown upload → Notion → read back → verify."""

from helpers import append_blocks, get_top_blocks
from notion_utils import (
    extract_rich_text,
    get_all_blocks,
    markdown_to_blocks,
)
from read_page import block_to_markdown, block_to_text

# ── Helpers ──────────────────────────────────────────────────────────


def _block_text(block: dict) -> str:
    """Extract plain text from a block."""
    btype = block["type"]
    rt = block.get(btype, {}).get("rich_text", [])
    return extract_rich_text(rt)


def _blocks_of_type(blocks: list, btype: str) -> list:
    return [b for b in blocks if b["type"] == btype]


def _count_links(blocks: list) -> int:
    """Count rich_text items that carry a link annotation."""
    n = 0
    for b in blocks:
        btype = b["type"]
        for rt in b.get(btype, {}).get("rich_text", []):
            if rt.get("text", {}).get("link"):
                n += 1
    return n


# ── Tests ────────────────────────────────────────────────────────────


class TestHeadingsAndParagraphs:
    """Basic block types survive a round-trip."""

    MARKDOWN = """\
# Heading One
## Heading Two
### Heading Three

A simple paragraph with **bold**, *italic*, and `code`.

Another paragraph."""

    def test_heading_types(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        h1 = _blocks_of_type(remote, "heading_1")
        h2 = _blocks_of_type(remote, "heading_2")
        h3 = _blocks_of_type(remote, "heading_3")

        assert len(h1) == 1
        assert _block_text(h1[0]) == "Heading One"
        assert len(h2) == 1
        assert _block_text(h2[0]) == "Heading Two"
        assert len(h3) == 1
        assert _block_text(h3[0]) == "Heading Three"

    def test_paragraphs(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        paras = _blocks_of_type(remote, "paragraph")
        texts = [_block_text(p) for p in paras]

        assert any("bold" in t for t in texts)
        assert any("Another paragraph" in t for t in texts)

    def test_inline_formatting_preserved(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        # Find the paragraph containing "bold"
        para = next(b for b in remote if b["type"] == "paragraph" and "bold" in _block_text(b))
        rt_items = para["paragraph"]["rich_text"]

        annotations = {item["plain_text"]: item.get("annotations", {}) for item in rt_items}
        assert annotations.get("bold", {}).get("bold") is True
        assert annotations.get("italic", {}).get("italic") is True
        assert annotations.get("code", {}).get("code") is True


class TestLinks:
    """Markdown links render as Notion link annotations."""

    MARKDOWN = """\
Check [Notion](https://notion.so) docs.

Multiple: [Google](https://google.com) and [GitHub](https://github.com).

Formatted: [**Bold Link**](https://bold.example.com)."""

    def test_links_present(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        assert _count_links(remote) >= 4

    def test_link_urls_correct(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        # Notion may normalize URLs (e.g. add trailing slash), so strip
        # trailing slashes before comparing.
        urls = set()
        for b in remote:
            btype = b["type"]
            for rt in b.get(btype, {}).get("rich_text", []):
                link = rt.get("text", {}).get("link")
                if link:
                    urls.add(link["url"].rstrip("/"))

        assert "https://notion.so" in urls
        assert "https://google.com" in urls
        assert "https://github.com" in urls
        assert "https://bold.example.com" in urls


class TestNestedLists:
    """Nested bullet, numbered, and todo lists produce children blocks."""

    MARKDOWN = """\
- Parent 1
  - Child 1a
  - Child 1b
    - Grandchild 1b-i
- Parent 2
  - Child 2a"""

    def test_top_level_count(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        bullets = _blocks_of_type(remote, "bulleted_list_item")
        assert len(bullets) == 2  # Parent 1, Parent 2

    def test_children_exist(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        parents_with_children = [b for b in remote if b.get("has_children")]
        assert len(parents_with_children) >= 2

    def test_deep_nesting(self, api_key, page_id):
        """Verify 3 levels: Parent → Child → Grandchild."""
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)

        # Use recursive fetch to get children
        all_blocks = get_all_blocks(page_id, api_key)

        parent1 = next(b for b in all_blocks if _block_text(b) == "Parent 1")
        assert "children" in parent1
        child_1b = next(c for c in parent1["children"] if _block_text(c) == "Child 1b")
        assert "children" in child_1b
        grandchild = child_1b["children"][0]
        assert _block_text(grandchild) == "Grandchild 1b-i"


class TestNumberedLists:
    MARKDOWN = """\
1. First
  1. Sub-first
  2. Sub-second
2. Second"""

    def test_numbered_nesting(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        numbered = _blocks_of_type(remote, "numbered_list_item")
        assert len(numbered) == 2
        assert any(b.get("has_children") for b in numbered)


class TestMixedListTypes:
    MARKDOWN = """\
- Bullet parent
  1. Numbered child
  2. Numbered child 2
- Another bullet
  - [ ] Todo unchecked
  - [x] Todo checked"""

    def test_mixed_types(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)

        all_blocks = get_all_blocks(page_id, api_key)

        bullet_parent = next(b for b in all_blocks if _block_text(b) == "Bullet parent")
        child_types = {c["type"] for c in bullet_parent.get("children", [])}
        assert "numbered_list_item" in child_types

        another = next(b for b in all_blocks if _block_text(b) == "Another bullet")
        child_types2 = {c["type"] for c in another.get("children", [])}
        assert "to_do" in child_types2


class TestCodeBlocks:
    MARKDOWN = """\
```python
def hello():
    print("world")
```"""

    def test_code_block(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        code = _blocks_of_type(remote, "code")
        assert len(code) == 1
        assert code[0]["code"]["language"] == "python"
        assert "def hello" in _block_text(code[0])


class TestQuotesAndDividers:
    MARKDOWN = """\
> This is a quote

---

Final paragraph."""

    def test_quote(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        quotes = _blocks_of_type(remote, "quote")
        assert len(quotes) == 1
        assert _block_text(quotes[0]) == "This is a quote"

    def test_divider(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        dividers = _blocks_of_type(remote, "divider")
        assert len(dividers) == 1


class TestImages:
    """Image blocks survive a round-trip and render correctly."""

    # Use a stable, public image URL unlikely to disappear
    IMAGE_URL = "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"

    MARKDOWN = f"![Test logo]({IMAGE_URL})"

    def test_image_roundtrip(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        images = _blocks_of_type(remote, "image")
        assert len(images) == 1

        image_block = images[0]["image"]
        assert image_block["type"] == "external"
        assert image_block["external"]["url"] == self.IMAGE_URL

    def test_image_to_markdown(self, api_key, page_id):
        """Full round-trip: upload image → fetch → render markdown."""
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)

        all_blocks = get_all_blocks(page_id, api_key)
        image = next(b for b in all_blocks if b["type"] == "image")
        md = block_to_markdown(image)

        assert md.startswith("![")
        assert self.IMAGE_URL in md

    def test_image_to_text(self, api_key, page_id):
        """Images produce no text output (no rich_text content)."""
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)

        all_blocks = get_all_blocks(page_id, api_key)
        image = next(b for b in all_blocks if b["type"] == "image")
        text = block_to_text(image)

        # Images don't have rich_text, so text output is empty
        assert text == ""


class TestTables:
    MARKDOWN = """\
| Name | Score |
|------|-------|
| Alice | 95 |
| Bob | 87 |"""

    def test_table_roundtrip(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        tables = _blocks_of_type(remote, "table")
        assert len(tables) == 1

        table = tables[0]["table"]
        assert table["table_width"] == 2
        assert table["has_column_header"] is True

    def test_table_row_count(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)

        # Tables have children (rows) — need recursive fetch
        all_blocks = get_all_blocks(page_id, api_key)
        table = next(b for b in all_blocks if b["type"] == "table")
        rows = table.get("children", [])
        # Header + 2 data rows = 3
        assert len(rows) == 3

    def test_table_to_markdown(self, api_key, page_id):
        """Full round-trip: upload table → fetch with children → render markdown."""
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)

        all_blocks = get_all_blocks(page_id, api_key)
        table = next(b for b in all_blocks if b["type"] == "table")
        md = block_to_markdown(table)

        assert "| Name | Score |" in md
        assert "| --- | --- |" in md
        assert "Alice" in md
        assert "Bob" in md

    def test_table_to_text(self, api_key, page_id):
        """Full round-trip: upload table → fetch with children → render text."""
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)

        all_blocks = get_all_blocks(page_id, api_key)
        table = next(b for b in all_blocks if b["type"] == "table")
        text = block_to_text(table)

        lines = text.split("\n")
        assert "Name" in lines[0] and "Score" in lines[0]
        assert "Alice" in lines[1] and "95" in lines[1]
        assert "Bob" in lines[2] and "87" in lines[2]


class TestComplexDocument:
    """A realistic document with multiple block types."""

    MARKDOWN = """\
# Project Status

## Summary

The project is **on track**. See [dashboard](https://example.com/dash) for details.

## Tasks

- [x] Design review complete
- [ ] Implementation in progress
  - Backend API
  - Frontend components
- [ ] Testing pending

## Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Coverage | 85% | 90% |
| Latency | 120ms | 100ms |

## Notes

> Important: deadline is Friday.

---

```shell
./scripts/deploy --env staging
```

*Last updated: today*"""

    def test_complex_block_count(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        # Should have a healthy number of blocks
        assert len(remote) >= 10

    def test_complex_block_types(self, api_key, page_id):
        blocks = markdown_to_blocks(self.MARKDOWN)
        append_blocks(api_key, page_id, blocks)
        remote = get_top_blocks(api_key, page_id)

        types = {b["type"] for b in remote}
        assert "heading_1" in types
        assert "heading_2" in types
        assert "paragraph" in types
        assert "to_do" in types
        assert "table" in types
        assert "quote" in types
        assert "divider" in types
        assert "code" in types
