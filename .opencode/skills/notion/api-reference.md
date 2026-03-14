# Notion API Reference

Quick reference for Notion API endpoints used by this skill.

## Official Documentation

- [Getting Started](https://developers.notion.com/guides/get-started/getting-started)
- [API Reference](https://developers.notion.com/reference/intro)
- [Working with Comments](https://developers.notion.com/reference/create-a-comment)

## Authentication

All API requests require:

```bash
-H "Authorization: Bearer $NOTION_API_KEY"
-H "Notion-Version: 2022-06-28"
-H "Content-Type: application/json"
```

Base URL: `https://api.notion.com/v1/`

## Key Endpoints

### Pages

```bash
# Get page
GET /v1/pages/{page_id}

# Search pages
POST /v1/search
{
  "query": "search term",
  "filter": { "property": "object", "value": "page" }
}
```

### Blocks

```bash
# Get block
GET /v1/blocks/{block_id}

# Get child blocks (page content)
GET /v1/blocks/{block_id}/children?page_size=100

# Supports pagination via start_cursor
GET /v1/blocks/{block_id}/children?page_size=100&start_cursor={cursor}
```

### Comments

```bash
# Get comments for a block (or page)
GET /v1/comments?block_id={block_id}

# Create a page-level comment
POST /v1/comments
{
  "parent": { "page_id": "{page_id}" },
  "rich_text": [
    {
      "type": "text",
      "text": { "content": "Comment text" }
    }
  ]
}

# Create a block-level comment (attaches to specific block)
POST /v1/comments
{
  "parent": { "block_id": "{block_id}" },
  "rich_text": [
    {
      "type": "text",
      "text": { "content": "Comment on this block" }
    }
  ]
}

# Reply to a discussion (ONLY discussion_id, NO parent)
POST /v1/comments
{
  "discussion_id": "{discussion_id}",
  "rich_text": [
    {
      "type": "text",
      "text": { "content": "Reply text" }
    }
  ]
}
```

**Important:** `parent.page_id`, `parent.block_id`, and `discussion_id` are
**mutually exclusive** — only one can be specified per request. Sending
multiple will result in a validation error.

### Users

```bash
# Get user
GET /v1/users/{user_id}

# List all users
GET /v1/users?page_size=100

# Get bot user (self)
GET /v1/users/me
```

## Comment Structure

Comments in Notion are organized into discussions. A comment's parent can be
either a page or a block:

```json
{
  "object": "comment",
  "id": "comment-id",
  "parent": {
    "type": "page_id",
    "page_id": "page-id"
  },
  "discussion_id": "discussion-id",
  "created_time": "2025-01-15T10:30:00.000Z",
  "last_edited_time": "2025-01-15T10:30:00.000Z",
  "created_by": {
    "object": "user",
    "id": "user-id"
  },
  "rich_text": [
    {
      "type": "text",
      "text": {
        "content": "Comment text"
      },
      "plain_text": "Comment text"
    }
  ]
}
```

Block-level comments have `"type": "block_id"` in their parent:

```json
{
  "parent": {
    "type": "block_id",
    "block_id": "block-id"
  }
}
```

## Rich Text with Links

Links in rich text use the `link` field inside `text`:

```json
{
  "type": "text",
  "text": {
    "content": "Click here",
    "link": { "url": "https://example.com" }
  },
  "annotations": {
    "bold": false,
    "italic": false,
    "code": false
  }
}
```

Links can be combined with annotations (bold, italic, code). The
`markdown_to_blocks()` function automatically converts `[text](url)` syntax.

## Block Types

Common block types you'll encounter:

- `paragraph` - Text paragraph
- `heading_1`, `heading_2`, `heading_3` - Headings
- `bulleted_list_item` - Bullet point
- `numbered_list_item` - Numbered item
- `to_do` - Checklist item
- `toggle` - Toggle/collapsible block
- `code` - Code block
- `quote` - Quote block
- `callout` - Callout/notice block
- `divider` - Horizontal line
- `table_of_contents` - TOC block
- `child_page` - Nested page
- `child_database` - Database view

## Extracting Text from Blocks

Most blocks have a `rich_text` array:

```json
{
  "type": "paragraph",
  "paragraph": {
    "rich_text": [
      {
        "type": "text",
        "text": {
          "content": "Text content"
        },
        "plain_text": "Text content"
      }
    ]
  }
}
```

## Pagination

Notion API uses cursor-based pagination:

```json
{
  "object": "list",
  "results": [...],
  "next_cursor": "abc123",
  "has_more": true
}
```

To get next page, use `start_cursor` parameter with the `next_cursor` value.

## Rate Limits

- 3 requests per second per integration
- If you exceed the rate limit, you'll get a `429` status code
- The response includes a `Retry-After` header with seconds to wait

## Comment Links

Direct links to comments in Notion follow this pattern:

```
https://www.notion.so/{page_id}?p={discussion_id}&pm=c
```

Where:
- `page_id` - The page ID without dashes
- `discussion_id` - The discussion thread ID without dashes
- `pm=c` - Parameter indicating comment/discussion mode

Example:
```
https://www.notion.so/2f542374e1fe80e9a480d59873e7241c?p=2fc42374e1fe8070&pm=c
```

## Common Errors

### 404 - object_not_found

The integration doesn't have access to the page/block:

```json
{
  "object": "error",
  "status": 404,
  "code": "object_not_found",
  "message": "Could not find block with ID: ..."
}
```

**Solution:** Share the page with your integration in Notion.

### 401 - unauthorized

Invalid API key or missing authorization:

```json
{
  "object": "error",
  "status": 401,
  "code": "unauthorized",
  "message": "API token is invalid."
}
```

**Solution:** Check your `NOTION_API_KEY` is correct.

### 400 - validation_error

Invalid request parameters:

```json
{
  "object": "error",
  "status": 400,
  "code": "validation_error",
  "message": "body failed validation..."
}
```

**Solution:** Check your request body matches the API schema.

## Integration Setup

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the "Internal Integration Token"
4. Export the key in your shell:
   ```bash
   export NOTION_API_KEY=ntn_...
   # Add to your shell profile (~/.zshrc, ~/.bashrc) for persistence
   ```
5. Share pages with your integration:
   - Open the page in Notion
   - Click `•••` → "Connections"
   - Add your integration

## Disabling Notion MCP Server

If you previously had the Notion MCP server enabled, disable it to avoid conflicts:

1. Check `~/.config/claude/claude_desktop_config.json`
2. Remove any `notion` entries from `mcpServers`
3. Or if it's a plugin, remove from enabled plugins in `~/.claude/settings.json`

The skill uses direct API calls instead of MCP for more control and flexibility.
