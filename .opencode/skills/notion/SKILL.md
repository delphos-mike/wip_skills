---
description: Complete Notion document management via API. Search, read, write, update,
  delete, and analyze content. Handle page overwriting, section updates, auto-linking,
  comment extraction, and full CRUD operations. Use for document automation, content
  management, and collaboration workflows.
name: notion
---

# Notion Document Management

## How to Run Scripts

Scripts live in this skill's `scripts/` directory. Run them with `uv run`:

```bash
# Pattern: uv run <skill_dir>/scripts/<script_name>.py <args>
# Example (if skill is at .opencode/skills/notion/):
uv run .opencode/skills/notion/scripts/search_pages.py "query"
```

Each script declares its dependencies via PEP 723 inline metadata. `uv run`
resolves and caches them automatically — no venv or manual install needed.

**Prerequisites:** `uv` and 1Password CLI (`op`) must be installed.
On first run, scripts automatically fetch the Notion API key from 1Password
and cache it locally in `.secrets/notion_api_key` (0600 permissions).

API key resolution order:
1. `NOTION_API_KEY` environment variable (if set)
2. Cached key in `.secrets/notion_api_key`
3. 1Password CLI: `op read "op://it-ops-helpers/NOTION_SKILL_INTEGRATION/credential"`

Override the 1Password reference with `NOTION_OP_REF` env var if your vault
layout differs.

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

### Mandatory Pre-Write Read (CRITICAL)

Before ANY destructive operation (`replace_page_content.py`, `clear_page.py`,
`delete_blocks.py`, `update_from_json.py`): **ALWAYS read the page first** with
`read_page.py` and show the user what exists. Do not bypass this even if the
user says "update" or "replace" -- they may not remember what's on the page.

**NEVER pass `--yes` to destructive scripts without first reading and presenting
the existing content to the user.** The interactive prompt exists as a last-resort
safety net; bypassing it requires the agent to have already performed its own due
diligence.

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

### Database Operations

**query_database.py** — Query a Notion database with filtering
```bash
query_database.py <database_url_or_id> [--output table|json]
query_database.py <database_url_or_id> --empty Summary
query_database.py <database_url_or_id> --not-empty Summary
query_database.py <database_url_or_id> --filter "Status=Done"
query_database.py <database_url_or_id> --props "Name,Summary,Status"
```
Supports `--filter "Prop=Value"`, `--empty Prop`, `--not-empty Prop` (all
repeatable). Auto-detects property types from the database schema. Use
`--output json` for machine-readable output with page IDs.

**update_page_property.py** — Update properties on a database page
```bash
update_page_property.py <page_url_or_id> --set "Summary=New summary"
update_page_property.py <page_url_or_id> --set "Status=Done" --set "Priority=High"
update_page_property.py <page_url_or_id> --set "Summary="  # clear property
```
Supports rich_text, title, number, select, multi_select, status, checkbox,
url, email, phone_number, and date properties. Auto-detects property types.

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

**link_pages.py** — Find and link page references
```bash
link_pages.py <page_id> --find-references
link_pages.py <page_id> --link "QUERY" <target_page_id>
```

### Edit Content

**update_block.py** — Update a single block (safe)
```bash
update_block.py <block_id> --text "new content"
update_block.py <block_id> --file content.txt
```
Updates the rich_text content of a block. Block type is auto-detected.

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

**create_comment.py** — Create a page-level or block-level comment
```bash
create_comment.py <page_url_or_id> "Comment text"         # page-level
create_comment.py --block <block_id> "Comment text"        # block-level
create_comment.py <page_url_or_id> --file comment.txt
```
Supports inline markdown: `**bold**`, `*italic*`, `` `code` ``, `[text](url)`.
Block-level comments attach to a specific block (paragraph, heading, etc.).

**reply_to_comment.py** — Reply to a discussion thread
```bash
reply_to_comment.py <discussion_id> "Reply text"
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
# Page-level comment
create_comment.py <page_id> "Initial thought"
# Block-level comment (attaches to specific block)
create_comment.py --block <block_id> "Comment on this block"
# Get the discussion_id from the JSON output, then reply:
reply_to_comment.py <discussion_id> "Follow-up"
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
  "Query database"  → query_database.py
  "Find empty X"    → query_database.py --empty X
  "List DB entries" → query_database.py

User wants to UPDATE DATABASE PROPERTIES:
  "Set summary"     → update_page_property.py --set "Summary=..."
  "Update status"   → update_page_property.py --set "Status=Done"
  "Batch update"    → query_database.py (get IDs) + update_page_property.py

User wants to ADD:
  "Add to end"      → append_blocks.py
  "Insert at top"   → insert_block.py --position 0
  "Insert after X"  → find_section.py + insert_block.py --after
  "Add comment"     → create_comment.py (page-level)
  "Comment on block"→ create_comment.py --block <id>
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
**nested lists** (indent with 2/4 spaces or tabs for sub-items), tables
(`| H | H |`), code blocks (` ```lang `), quotes (`> `), dividers (`---`),
inline formatting (`**bold**`, `*italic*`, `` `code` ``),
**links** (`[text](url)`), and mermaid diagrams (` ```mermaid `).

Nested lists support arbitrary depth and mixed types (bullets with numbered
sub-items, todos as children, etc.).

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
| "ModuleNotFoundError: requests" | Ensure you run scripts via `uv run`, not `python3` directly |
| "1Password CLI (op) not found" | Install from https://developer.1password.com/docs/cli/get-started/ |
| "1Password lookup failed" | Sign in: `eval $(op signin)` — or check the `NOTION_OP_REF` value |
| Stale cached key | Delete `.secrets/notion_api_key` in skill dir; next run will re-fetch from 1Password |