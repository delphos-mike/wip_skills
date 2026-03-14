# Notion Skill Quick Reference

## ⚠️ COMMENT SAFETY FIRST!

**Deleting a block = Deleting its comments forever!**

| Safe | Dangerous |
|------|-----------|
| ✅ sync_page.py | ❌ replace_page_content.py |
| ✅ update_block.py | ❌ update_from_json.py |
| ✅ append_blocks.py | ❌ clear_page.py |
| ✅ insert_block.py | ❌ delete_blocks.py |

## I Want To...

| Goal | Command | Safe? |
|------|---------|-------|
| **Find a page** | `search_pages.py "keyword"` | N/A |
| **Read a page** | `read_page.py <page_id>` | N/A |
| **Add to end of page** | `append_blocks.py <page_id> --text "content"` | ✅ |
| **Insert at top** | `insert_block.py <page_id> --text "content" --position 0` | ✅ |
| **Update one block** | `update_block.py <block_id> --text "new content"` | ✅ |
| **Edit page (with comments)** | `sync_page.py <page_id> edited.json` | ✅ |
| **Replace entire page** | `replace_page_content.py <page_id> --file new.md` | ❌ |
| **Clear page** | `clear_page.py <page_id>` | ❌ |
| **Delete blocks** | `delete_blocks.py <block_id1> <block_id2>` | ❌ |
| **Find section** | `find_section.py <page_id> "Heading Text"` | N/A |
| **Link pages** | `link_pages.py <source> <target1> <target2>` | ✅ |
| **Extract comments** | `extract_comments.py <page_id>` | N/A |
| **Create comment** | `create_comment.py <page_id> "text"` | N/A |
| **Comment on block** | `create_comment.py --block <block_id> "text"` | N/A |
| **Reply to comment** | `reply_to_comment.py <disc_id> "text"` | N/A |
| **Summarize comments** | `summarize_comments.py comments.json` | N/A |

## Common Patterns

### Safe Edit Workflow
```bash
read_page.py <page_id> --output json > page.json
# Edit page.json
sync_page.py <page_id> page.json
```

### Add Markdown Content
```bash
append_blocks.py <page_id> --markdown "## Title\n- Item 1\n- Item 2"
```

### From File
```bash
append_blocks.py <page_id> --file notes.md
```

### Comment Analysis
```bash
extract_comments.py <page_id>
summarize_comments.py /tmp/<page>_comments.json
```

### Comment Thread
```bash
create_comment.py <page_id> "Initial thought"
# Or attach to a specific block:
create_comment.py --block <block_id> "Comment on this block"
# Get discussion_id from JSON output, then reply:
reply_to_comment.py <discussion_id> "Follow-up"
```

## Decision Tree

```
What do you want to do?

ADD CONTENT
  └─ append_blocks.py (end) or insert_block.py (specific position)

EDIT CONTENT
  ├─ Has comments? → sync_page.py (SAFE)
  └─ No comments? → replace_page_content.py (faster)

DELETE CONTENT
  └─ delete_blocks.py or clear_page.py (⚠️ WARN USER!)

READ/SEARCH
  ├─ Find page → search_pages.py
  ├─ Read content → read_page.py
  └─ Get comments → extract_comments.py

COMMENT
  ├─ Page comment → create_comment.py <page_id>
  ├─ Block comment → create_comment.py --block <block_id>
  └─ Reply to thread → reply_to_comment.py
```

## Markdown Support

All markdown scripts support:
- Headings: `#`, `##`, `###`
- Lists: `-` bullets, `1.` numbered
- **Nested lists**: indent with 2/4 spaces or tabs
- Todos: `- [ ]`, `- [x]`
- **Links**: `[text](url)`
- **Tables**: `| Header | Header |`
- Code: ` ```python `
- Quotes: `> text`
- Inline: `**bold**`, `*italic*`, `` `code` ``

## When to Ask User

**ALWAYS ask before:**
- Replacing page content
- Deleting blocks
- Clearing pages
- Using any ❌ dangerous operation

**Question:** "This page might have comments. Should I preserve them?"

## Setup

```bash
# Set in your shell environment
export NOTION_API_KEY=ntn_...
```

## All Commands

```bash
# Search & Read
search_pages.py "query" [--limit N] [--output json|table]
read_page.py <page_id> [--output markdown|json|text]

# Add Content (SAFE)
append_blocks.py <page_id> --text|--markdown|--file
insert_block.py <page_id> --text|--markdown|--file [--position N] [--after block_id]

# Edit Content
update_block.py <block_id> --text|--heading-1|--code etc
sync_page.py <page_id> <json_file> [--delete-removed] [--force]  # SAFE

# Replace Content (DANGEROUS)
replace_page_content.py <page_id> --markdown|--file  # ⚠️ LOSES COMMENTS
update_from_json.py <page_id> <json_file>  # ⚠️ LOSES COMMENTS

# Delete (DANGEROUS)
delete_blocks.py <block_id> [<block_id2> ...]  # ⚠️ LOSES COMMENTS
delete_blocks.py --all <page_id>  # ⚠️ LOSES ALL COMMENTS
delete_blocks.py --range <page_id> <start> <end>  # ⚠️ LOSES COMMENTS
clear_page.py <page_id> [--yes]  # ⚠️ LOSES ALL COMMENTS

# Utilities
find_section.py <page_id> "Heading Text"
link_pages.py <source_page> <target_page1> [<target_page2> ...]

# Comments
extract_comments.py <page_id>
create_comment.py <page_id> "text"                     # page-level
create_comment.py --block <block_id> "text"            # block-level
create_comment.py <page_id> --file comment.txt
reply_to_comment.py <discussion_id> "reply text"
summarize_comments.py <comments_json>
```

## Quick Examples

```bash
# Find and read
search_pages.py "RFC"
read_page.py https://notion.so/Page-abc123 > page.md

# Add content
append_blocks.py <page_id> --text "Quick note"
append_blocks.py <page_id> --markdown "## Update\n- Done\n- Todo"

# Safe edit
read_page.py <page_id> --output json > page.json
# ... edit page.json ...
sync_page.py <page_id> page.json

# Extract comments
extract_comments.py <page_id>
summarize_comments.py /tmp/page_comments.json
```

## Error Messages

| Error | Solution |
|-------|----------|
| "Could not find page" | Share page with integration in Notion |
| Rate limited | Scripts handle automatically (3 req/sec) |
| Invalid page ID | Use full URL or properly formatted UUID |

## Remember

1. **Default to safe:** Use `sync_page.py` when editing
2. **Always warn:** Before any ❌ operation
3. **Extract first:** Get comments before risky operations
4. **Use workflows:** Pull → Edit → Push is fastest
