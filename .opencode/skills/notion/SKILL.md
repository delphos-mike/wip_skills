---
name: notion
description: Complete Notion document management via API. Search, read, write, update, delete, and analyze content. Handle page overwriting, section updates, auto-linking, comment extraction, and full CRUD operations. Use for document automation, content management, and collaboration workflows.
scripts:
  - search_pages.py
  - read_page.py
  - edit_page.py
  - append_blocks.py
  - insert_block.py
  - update_block.py
  - delete_blocks.py
  - clear_page.py
  - replace_page_content.py
  - sync_page.py
  - update_from_json.py
  - find_section.py
  - link_pages.py
  - extract_comments.py
  - summarize_comments.py
---

# Notion Document Management

## ⚠️ CRITICAL: Comment Preservation

**Notion comments are attached to specific blocks. Deleting or replacing a block PERMANENTLY loses its comments!**

### Safe Operations (Comments Preserved)
- ✅ **`sync_page.py`** - Updates blocks in-place (SAFE - comments preserved)
- ✅ **`update_block.py`** - Updates single block content (SAFE)
- ✅ **`append_blocks.py`** - Adds new blocks (SAFE)
- ✅ **`insert_block.py`** - Inserts at position (SAFE - doesn't delete)

### Dangerous Operations (Comments Lost!)
- ⚠️ **`replace_page_content.py`** - Deletes ALL blocks → loses ALL comments
- ⚠️ **`update_from_json.py`** - Deletes ALL blocks → loses ALL comments
- ⚠️ **`clear_page.py`** - Deletes ALL blocks → loses ALL comments
- ⚠️ **`delete_blocks.py`** - Explicitly deletes blocks → loses their comments
- ⚠️ **`sync_page.py --delete-removed`** - Deletes removed blocks → loses their comments

### Decision Tree

```
Need to edit existing page content?
│
├─ Yes → Are there comments you need to preserve?
│   │
│   ├─ Yes → Use sync_page.py (updates in-place)
│   │         OR update_block.py (single block)
│   │
│   └─ No → Use replace_page_content.py (faster)
│           OR update_from_json.py (JSON workflow)
│
└─ No → Just adding content?
    │
    ├─ At end → append_blocks.py
    ├─ At specific position → insert_block.py
    └─ Delete content → delete_blocks.py or clear_page.py

```

## Setup

Create `~/.envs/notion.env`:
```bash
NOTION_API_KEY=ntn_...
```

Share your integration with pages in Notion:
1. Open page → `•••` (three dots) → "Connections"
2. Add your integration

## Quick Reference

| Task | Script | Comments Safe? |
|------|--------|----------------|
| Search for pages | `search_pages.py` | N/A |
| Read page content | `read_page.py` | N/A |
| Add content to end | `append_blocks.py` | ✅ Yes |
| Insert at position | `insert_block.py` | ✅ Yes |
| Update specific block | `update_block.py` | ✅ Yes |
| Smart sync changes | `sync_page.py` | ✅ Yes (updates in-place) |
| Replace all content | `replace_page_content.py` | ❌ No (deletes all) |
| Update from JSON | `update_from_json.py` | ❌ No (deletes all) |
| Delete blocks | `delete_blocks.py` | ❌ No (explicit delete) |
| Clear page | `clear_page.py` | ❌ No (deletes all) |
| Find section by heading | `find_section.py` | N/A |
| Link pages together | `link_pages.py` | ✅ Yes |
| Extract comments | `extract_comments.py` | N/A |
| Summarize comments | `summarize_comments.py` | N/A |

## All Scripts Reference

### 1. search_pages.py - Find Pages

Find pages by keyword across your workspace.

```bash
search_pages.py <query> [--limit N] [--output json|table]
```

**Examples:**
```bash
search_pages.py "project plan" --limit 10
search_pages.py "RFC" --output json
```

**Output:** Table or JSON with titles, IDs, and URLs

---

### 2. read_page.py - Read Content

Read all content from a page, including nested blocks.

```bash
read_page.py <page_url_or_id> [--output markdown|json|text]
```

**Examples:**
```bash
read_page.py https://notion.so/Page-abc123
read_page.py 2f542374-e1fe-80e9... --output json > page.json
```

**Output:** Markdown, JSON (full structure), or plain text

---

### 3. append_blocks.py - Add to End

Append content to the end of a page. **Comment-safe.**

```bash
append_blocks.py <page_url_or_id> --text "content"
append_blocks.py <page_url_or_id> --markdown "# Heading\n..."
append_blocks.py <page_url_or_id> --file content.md
```

**Supported Markdown:**
- Headings: `#`, `##`, `###`
- Lists: `-` (bullets), `1.` (numbered)
- Todos: `- [ ]`, `- [x]`
- Tables: `| Header | Header |`
- Code blocks: ` ```language ` (see **Code Block Languages** below for valid values)
- Mermaid diagrams: ` ```mermaid ` (rendered as interactive diagrams by Notion)
- Quotes: `> text`
- Dividers: `---`
- Inline: `**bold**`, `*italic*`, `` `code` ``

**Examples:**
```bash
append_blocks.py <page_id> --text "Quick note"
append_blocks.py <page_id> --markdown "## Update\n- Item 1\n- Item 2"
append_blocks.py <page_id> --file notes.md
```

---

### 4. insert_block.py - Insert at Position

Insert blocks at specific positions or after specific blocks. **Comment-safe.**

```bash
insert_block.py <page_id> --text "content" [--position N]
insert_block.py <page_id> --markdown "..." [--after block_id]
insert_block.py <page_id> --file content.md
```

**Examples:**
```bash
# Insert at position 0 (beginning)
insert_block.py <page_id> --markdown "## New Section" --position 0

# Insert after specific block
insert_block.py <page_id> --text "Follow-up" --after <block_id>
```

---

### 5. update_block.py - Update Single Block

Update the content of a specific block. **Comment-safe.**

```bash
update_block.py <block_id> --text "new content"
update_block.py <block_id> --heading-2 "New Heading"
update_block.py <block_id> --code "code content" --language python
```

**Supported Types:** paragraph, heading_1/2/3, code, quote, bulleted_list_item, numbered_list_item, to_do

**Example:**
```bash
update_block.py <block_id> --text "Updated content"
```

---

### 6. sync_page.py - Smart Sync (RECOMMENDED)

**The safest way to edit existing pages with comments.**

Intelligently syncs changes by updating blocks in-place, preserving comments.

```bash
sync_page.py <page_id> <json_file> [--delete-removed] [--force]
```

**How it works:**
1. Reads current page state
2. Compares with your edited JSON
3. **Updates** changed blocks in-place (preserves comments!)
4. **Inserts** new blocks
5. **Deletes** removed blocks only if `--delete-removed` flag used

**Safety Features:**
- Content hash verification
- Warns when blocks may have been reordered
- Detects position shifts (e.g., content inserted at top)
- Interactive confirmation for low-confidence matches (< 80%)
- `--force` flag to skip safety checks

**Workflow:**
```bash
# 1. Pull page to JSON
read_page.py <page_id> --output json > page.json

# 2. Edit JSON locally (fast, no API calls!)
# ... modify page.json ...

# 3. Push changes (preserves comments)
sync_page.py <page_id> page.json
```

**When to use:**
- **Default choice** for editing existing pages
- Any page with comments/discussions
- Content with collaboration history

---

### 7. replace_page_content.py - Replace All

**⚠️ WARNING: Deletes ALL blocks and their comments!**

Clears entire page and replaces with new content.

```bash
replace_page_content.py <page_id> --markdown "# New Content..."
replace_page_content.py <page_id> --file content.md
```

**When to use:**
- New pages (no existing comments)
- Intentionally clearing all content
- Prototypes/templates where comments don't matter

**Don't use if:** Page has any comments you need to preserve!

---

### 8. update_from_json.py - JSON Replace

**⚠️ WARNING: Deletes ALL blocks and their comments!**

Similar to replace_page_content.py but takes JSON block structure.

```bash
update_from_json.py <page_id> <json_file>
```

**When to use:**
- Programmatic page creation
- Templates/scaffolding
- No comments exist

**Don't use if:** Page has comments to preserve!

---

### 9. delete_blocks.py - Delete Blocks

**⚠️ WARNING: Deleted blocks lose their comments!**

Delete specific blocks, ranges, or all blocks.

```bash
delete_blocks.py <block_id1> [<block_id2> ...]
delete_blocks.py --all <page_id>
delete_blocks.py --range <page_id> <start> <end>
```

**Examples:**
```bash
# Delete specific blocks
delete_blocks.py <block_id1> <block_id2>

# Delete all blocks (same as clear_page.py)
delete_blocks.py --all <page_id>

# Delete range by position
delete_blocks.py --range <page_id> 0 5
```

---

### 10. clear_page.py - Clear All Content

**⚠️ WARNING: Deletes ALL blocks and their comments!**

Remove all content from a page.

```bash
clear_page.py <page_id> [--yes]
```

**Example:**
```bash
# With confirmation prompt
clear_page.py <page_id>

# Skip confirmation
clear_page.py <page_id> --yes
```

---

### 11. find_section.py - Find Section by Heading

Locate a section by heading text and get its block ID and position.

```bash
find_section.py <page_id> <heading_text>
```

**Example:**
```bash
find_section.py <page_id> "Implementation Details"
```

**Output:** Block ID, position, and heading level

---

### 12. link_pages.py - Create Page Links

Add links from one page to another(s).

```bash
link_pages.py <source_page> <target_page1> [<target_page2> ...]
```

**Example:**
```bash
link_pages.py <source_page> <related_page1> <related_page2>
```

---

### 13. extract_comments.py - Extract Comments

Extract all comments from a page with context.

```bash
extract_comments.py <page_url_or_id>
```

**Output:** JSON file with:
- Block context (where comment was made)
- Comment text and author
- Timestamps
- Discussion thread IDs

**Example:**
```bash
extract_comments.py https://www.notion.so/Design-Doc-abc123
# Creates: /tmp/<page_name>_comments.json
```

---

### 14. summarize_comments.py - Summarize Comments

Generate human-readable comment summaries organized by user and thread.

```bash
summarize_comments.py <comments_json_file>
```

**Output:**
- User statistics
- Discussion thread analysis
- Participation metrics
- Markdown report

**Example:**
```bash
summarize_comments.py /tmp/design_doc_comments.json
```

---

## Common Workflows

### Safe Editing Workflow (Preserves Comments)

```bash
# 1. Pull page
read_page.py <page_id> --output json > page.json

# 2. Edit locally (instant, no API calls)
# Edit page.json with your favorite editor or script

# 3. Push with smart sync (preserves comments!)
sync_page.py <page_id> page.json
```

### Comment Analysis Workflow

```bash
# 1. Extract comments
extract_comments.py <page_url>

# 2. Analyze
summarize_comments.py /tmp/<page_name>_comments.json
```

### Bulk Content Update

```bash
# Find all pages
search_pages.py "Weekly Report" --output json > pages.json

# Process each page
for page_id in $(jq -r '.results[].id' pages.json); do
  append_blocks.py $page_id --markdown "## Auto-Generated Update\n..."
done
```

## Agent Guidance

### When to Use Each Script

**User wants to read/search:**
- "Find my project doc" → `search_pages.py`
- "Read this page" → `read_page.py`
- "Extract comments" → `extract_comments.py`

**User wants to add content:**
- "Add this to the end" → `append_blocks.py`
- "Insert at the top" → `insert_block.py --position 0`
- "Add after section X" → `insert_block.py --after`

**User wants to edit existing content:**
- "Update this page" → **Ask: "Does this page have comments?"**
  - Yes → `sync_page.py` (safe!)
  - No/don't care → `replace_page_content.py` (faster)
- "Update one block" → `update_block.py`
- "Update section X" → `find_section.py` + `update_block.py`

**User wants to delete:**
- "Clear the page" → `clear_page.py` (warn about comments!)
- "Delete these blocks" → `delete_blocks.py` (warn about comments!)

### Red Flags (Always Ask User First)

- User says "update this page" but you don't know if there are comments
- User asks to replace content without mentioning comments
- Any operation that might delete existing blocks

**Always ask:** "This page might have comments. Should I preserve them or is it okay to lose them?"

### Decision Framework

```python
if operation == "add_new_content":
    use("append_blocks.py" or "insert_block.py")

elif operation == "edit_existing":
    if has_comments or unsure:
        use("sync_page.py")  # Safe default
    else:
        use("replace_page_content.py")  # Faster

elif operation == "delete":
    warn_user_about_comments()
    if confirmed:
        use("delete_blocks.py" or "clear_page.py")
```

## API Details

### Rate Limiting
- Notion API limit: **3 requests per second**
- All scripts include automatic rate limiting
- Batch operations supported (up to 100 blocks)

### Authentication
All requests require:
```bash
Authorization: Bearer $NOTION_API_KEY
Notion-Version: 2022-06-28
Content-Type: application/json
```

### Page ID Formats
Scripts accept all formats:
- URL: `https://www.notion.so/Page-Title-2f542374e1fe80e9a480d59873e7241c`
- UUID: `2f542374-e1fe-80e9-a480-d59873e7241c`
- Hex: `2f542374e1fe80e9a480d59873e7241c`

## Common Issues

### "Could not find page" (404)
- Integration doesn't have access
- Share the page with your integration in Notion
- Check page ID format

### Rate Limiting
- Scripts automatically handle 3 req/sec limit
- Use batch operations for large updates
- Consider local editing workflow (pull → edit → push)

### Code Block Languages

The Notion API only accepts specific language values for code blocks. Using an unsupported value (e.g., `dockerfile`) causes a 400 validation error. Common mappings:

| Markdown fence | Notion language value |
|---|---|
| ` ```dockerfile ` | `docker` |
| ` ```sh ` | `shell` |
| ` ```yml ` | `yaml` |
| ` ```tf ` | `hcl` |
| ` ```mermaid ` | `mermaid` |

Full list of valid values: `abap`, `abc`, `agda`, `arduino`, `ascii art`, `assembly`, `bash`, `basic`, `bnf`, `c`, `c#`, `c++`, `clojure`, `coffeescript`, `coq`, `css`, `dart`, `dhall`, `diff`, `docker`, `ebnf`, `elixir`, `elm`, `erlang`, `f#`, `flow`, `fortran`, `gherkin`, `glsl`, `go`, `graphql`, `groovy`, `haskell`, `hcl`, `html`, `idris`, `java`, `javascript`, `json`, `julia`, `kotlin`, `latex`, `less`, `lisp`, `livescript`, `llvm ir`, `lua`, `makefile`, `markdown`, `markup`, `matlab`, `mathematica`, `mermaid`, `nix`, `notion formula`, `objective-c`, `ocaml`, `pascal`, `perl`, `php`, `plain text`, `powershell`, `prolog`, `protobuf`, `purescript`, `python`, `r`, `racket`, `reason`, `ruby`, `rust`, `sass`, `scala`, `scheme`, `scss`, `shell`, `smalltalk`, `solidity`, `sql`, `swift`, `toml`, `typescript`, `vb.net`, `verilog`, `vhdl`, `visual basic`, `webassembly`, `xml`, `yaml`, `java/c/c++/c#`.

When uploading markdown files, remap unsupported fences before calling append/replace scripts.

### Mermaid Diagrams

Notion renders ` ```mermaid ` code blocks as interactive diagrams. When writing mermaid for Notion:

- Use `flowchart TD` or `flowchart LR` instead of `graph TD`/`graph LR` (better rendering)
- Use `\n` for line breaks in node labels, NOT `<br/>` (renders as literal text)
- Keep node labels short — long labels cause layout overflow
- Avoid special characters in subgraph labels (no quotes with colons or parens)
- Use `-->|label|` edge syntax instead of `-- label -->`

**Good (renders cleanly in Notion):**
```
flowchart TD
    A[Webserver\nport 3000] -->|gRPC| B[Code Server\nport 4000]
```

**Bad (breaks layout in Notion):**
```
graph TD
    A["Webserver<br/>UI + API<br/>port 3000"] -- gRPC --> B["Code Server<br/>port 4000"]
```

### Lost Comments
- **Prevention:** Always use `sync_page.py` for pages with comments
- **Recovery:** Comments cannot be recovered once blocks are deleted
- **Best practice:** Extract comments first as backup

## Technical Implementation

### Security
- ✅ API keys never exposed in process arguments
- ✅ Secure HTTP requests via Python `requests` library
- ✅ No subprocess/curl vulnerabilities

### Reliability
- ✅ Automatic rate limiting (3 req/sec)
- ✅ Retry logic with exponential backoff
- ✅ Comprehensive error handling
- ✅ JSON validation

### Code Quality
- ✅ Centralized utilities module (`notion_utils.py`)
- ✅ Consistent markdown parsing with table support
- ✅ Shared API call infrastructure
- ✅ DRY principles applied throughout

## Tips for Agents

1. **Default to safe:** When in doubt, use `sync_page.py`
2. **Always warn:** Before any destructive operation
3. **Ask about comments:** If user wants to edit/delete existing content
4. **Use workflows:** Pull → Edit → Push pattern is fastest
5. **Batch operations:** Group multiple changes into single API call
6. **Check access:** Verify integration permissions first

## Output Files

Scripts write to `/tmp/` by default:
- `<page_name>_comments.json` - Comment data
- `<page_name>_summary.txt` - Human-readable summary
- `<page_name>_report.md` - Markdown report
