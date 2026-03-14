---
name: notion
description: Complete Notion document management via API. Search, read, write, update, delete, and analyze content. Handle page overwriting, section updates, auto-linking, comment extraction, and full CRUD operations. Use for document automation, content management, and collaboration workflows.
---

# Notion Document Management

## How to Run Scripts

Scripts live in this skill's `scripts/` directory. To invoke them, determine the
skill directory from this file's path and run with `python3`:

```bash
# Pattern: python3 <skill_dir>/scripts/<script_name>.py <args>
# Example (if skill is at .opencode/skills/notion/):
python3 .opencode/skills/notion/scripts/search_pages.py "query"
```

**Auto-bootstrap:** On first run, scripts automatically create a `.venv` in the
skill directory and install dependencies (prefers `uv`, falls back to `pip`).
No manual setup required.

**Environment:** Scripts read `NOTION_API_KEY` from the environment. The user
must create a Notion integration and share it with their pages.

## Comment Preservation (CRITICAL)

Notion comments are attached to specific blocks. Deleting or replacing a block
**permanently loses its comments**.

| Safe (comments preserved) | Dangerous (comments lost!) |
|---------------------------|----------------------------|
| `sync_page.py` | `replace_page_content.py` |
| `update_block.py` | `update_from_json.py` |
| `append_blocks.py` | `clear_page.py` |
| `insert_block.py` | `delete_blocks.py` |

**Default to safe operations.** Before any destructive operation, ask:
"This page might have comments. Should I preserve them?"

## Script Reference

### Search & Read

**search_pages.py** — Find pages by keyword
```bash
search_pages.py <query> [--limit N] [--output json|table]
```

**read_page.py** — Read page content (markdown, JSON, or text)
```bash
read_page.py <page_url_or_id> [--output markdown|json|text]
```

**find_section.py** — Locate a section by heading text
```bash
find_section.py <page_id> <heading_text>
```
Returns: block ID, position, heading level.

### Add Content (Safe)

**append_blocks.py** — Append to end of page
```bash
append_blocks.py <page_id> --text "content"
append_blocks.py <page_id> --markdown "## Heading\n- item"
append_blocks.py <page_id> --file content.md
```

**insert_block.py** — Insert at specific position
```bash
insert_block.py <page_id> --text "content" --position 0       # at top
insert_block.py <page_id> --markdown "..." --after <block_id>  # after block
```

**link_pages.py** — Add page links
```bash
link_pages.py <source_page> <target_page1> [<target_page2> ...]
```

### Edit Content

**update_block.py** — Update a single block (safe)
```bash
update_block.py <block_id> --text "new content"
update_block.py <block_id> --heading-2 "New Heading"
update_block.py <block_id> --code "print('hi')" --language python
```
Supported types: paragraph, heading_1/2/3, code, quote, bulleted_list_item,
numbered_list_item, to_do.

**sync_page.py** — Smart sync preserving comments (RECOMMENDED)
```bash
sync_page.py <page_id> <json_file> [--delete-removed] [--force]
```
Compares local JSON with remote page, updates changed blocks in-place.
Use `--delete-removed` to also remove blocks that were deleted locally.
Use `--force` to skip interactive safety checks.

### Replace Content (Destructive)

**replace_page_content.py** — Clear page and write new content
```bash
replace_page_content.py <page_id> --markdown "# New Content..."
replace_page_content.py <page_id> --file content.md
```

**update_from_json.py** — Replace from JSON block structure
```bash
update_from_json.py <page_id> <json_file>
```

### Delete Content (Destructive)

**delete_blocks.py** — Delete specific blocks or ranges
```bash
delete_blocks.py <block_id1> [<block_id2> ...]
delete_blocks.py --all <page_id>
delete_blocks.py --range <page_id> <start> <end>
```

**clear_page.py** — Remove all page content
```bash
clear_page.py <page_id> [--yes]
```

### Comments

**create_comment.py** — Create a page-level comment
```bash
create_comment.py <page_url_or_id> "Comment text"
create_comment.py <page_url_or_id> --file comment.txt
```
Supports inline markdown: `**bold**`, `*italic*`, `` `code` ``.

**reply_to_comment.py** — Reply to a discussion thread
```bash
reply_to_comment.py <page_url_or_id> <discussion_id> "Reply text"
```
Get `discussion_id` from `extract_comments.py` output or `create_comment.py` output.

**extract_comments.py** — Extract all comments with block context
```bash
extract_comments.py <page_url_or_id>
```
Fetches both page-level and block-level comments. Writes
`/tmp/<page_name>_comments.json` with comment text, author,
timestamps, discussion threads, and deep links.

**summarize_comments.py** — Human-readable comment summary
```bash
summarize_comments.py <comments_json_file>
```
Outputs user statistics, thread analysis, participation metrics.

## Workflows

### Safe Edit (preserves comments)
```bash
read_page.py <page_id> --output json > page.json
# Edit page.json locally
sync_page.py <page_id> page.json
```

### Comment Analysis
```bash
extract_comments.py <page_url>
summarize_comments.py /tmp/<page_name>_comments.json
```

### Comment Thread
```bash
# Create a comment
create_comment.py <page_id> "Initial thought"
# Get the discussion_id from the JSON output, then reply:
reply_to_comment.py <page_id> <discussion_id> "Follow-up"
```

### Bulk Update
```bash
search_pages.py "Weekly Report" --output json > pages.json
# Process each page from the JSON results
```

## Agent Decision Guide

```
User wants to READ/SEARCH:
  "Find page"       → search_pages.py
  "Read page"       → read_page.py
  "Get comments"    → extract_comments.py

User wants to ADD:
  "Add to end"      → append_blocks.py
  "Insert at top"   → insert_block.py --position 0
  "Insert after X"  → find_section.py + insert_block.py --after
  "Add comment"     → create_comment.py
  "Reply to comment"→ reply_to_comment.py

User wants to EDIT:
  "Update page"     → ASK about comments first!
    Has comments    → sync_page.py (pull→edit→push)
    No comments     → replace_page_content.py (faster)
  "Update one block"→ update_block.py
  "Update section"  → find_section.py + update_block.py

User wants to DELETE:
  → ALWAYS warn about comment loss
  → delete_blocks.py or clear_page.py
```

## Markdown Support

Scripts that accept `--markdown` or `--file` support: headings (`#`, `##`,
`###`), bullet lists (`-`), numbered lists (`1.`), todos (`- [ ]`, `- [x]`),
tables (`| H | H |`), code blocks (` ```lang `), quotes (`> `), dividers
(`---`), inline formatting (`**bold**`, `*italic*`, `` `code` ``), and
mermaid diagrams (` ```mermaid `).

**Code block languages:** Use Notion's exact names. Common mappings:
`dockerfile`→`docker`, `sh`→`shell`, `yml`→`yaml`, `tf`→`hcl`.

## Page ID Formats

Scripts accept all formats:
- URL: `https://www.notion.so/Page-Title-2f542374e1fe80e9a480d59873e7241c`
- UUID: `2f542374-e1fe-80e9-a480-d59873e7241c`
- Hex: `2f542374e1fe80e9a480d59873e7241c`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Could not find page" (404) | Share the page with your Notion integration |
| Rate limiting | Handled automatically (3 req/sec) |
| "ModuleNotFoundError: requests" | Delete `.venv` in skill dir; scripts will re-bootstrap |
