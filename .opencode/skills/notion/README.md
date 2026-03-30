# Notion Skill for AI Agents

Complete Notion document management via API. Search, read, write, update, delete, and analyze content.

## Prerequisites

- **uv** — Python package manager ([install](https://docs.astral.sh/uv/))
- **op** — 1Password CLI ([install](https://developer.1password.com/docs/cli/get-started/)), authenticated with access to the `it-ops-helpers` vault

## Quick Setup

```bash
# 1. Run bootstrap to verify prerequisites and fetch API key
./scripts/bootstrap

# 2. Share the Notion integration with your pages
# In Notion: Page → ••• → Connections → Add "Notion Skill Integration"

# 3. Test it
uv run scripts/search_pages.py "test"
```

No venv or manual `pip install` needed — each script declares its dependencies
via PEP 723 inline metadata, and `uv run` resolves them automatically.

## API Key

The API key is fetched from 1Password and cached locally:

1. `NOTION_API_KEY` environment variable (if set)
2. Cached key in `.secrets/notion_api_key` (persists across sessions)
3. `op read "op://it-ops-helpers/NOTION_SKILL_INTEGRATION/credential"` (auto-cached)

## Running Scripts

```bash
uv run scripts/search_pages.py "query"
uv run scripts/read_page.py <page_id> --output markdown
uv run scripts/append_blocks.py <page_id> --markdown "## New Section"
```

Or use the wrapper: `scripts/run read_page.py <page_id>`

## Dependencies

- Python >=3.9
- `requests>=2.31.0` (resolved by `uv run` from PEP 723 metadata)

## Files

```
notion/
├── scripts/
│   ├── notion_utils.py   # Shared utilities (API calls, markdown, rate limiting)
│   ├── run               # Wrapper script (delegates to uv run)
│   ├── bootstrap         # Setup: verifies uv + op, fetches API key
│   └── *.py              # 19 entry-point scripts
├── tests/
│   └── integration/      # 45 integration tests against live Notion API
├── SKILL.md              # Agent-facing documentation (loaded by skill system)
├── QUICK_REFERENCE.md    # Quick command lookup
├── api-reference.md      # Notion API reference notes
└── .gitignore
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "ModuleNotFoundError: requests" | Run scripts via `uv run`, not `python3` directly |
| "1Password CLI (op) not found" | Install from https://developer.1password.com/docs/cli/get-started/ |
| "1Password lookup failed" | Sign in: `eval $(op signin)` |
| "Could not find page" (404) | Share page with the Notion integration in Notion UI |
| Stale cached key | Delete `.secrets/notion_api_key` — next run re-fetches |

## See Also

- `SKILL.md` — Full documentation loaded by agents
- `QUICK_REFERENCE.md` — Quick "I want to..." command lookup
