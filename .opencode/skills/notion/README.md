# Notion Skill for AI Agents

Complete Notion document management via API. Search, read, write, update, delete, and analyze content.

## Quick Setup

```bash
# 1. Configure API key
mkdir -p ~/.envs
echo "NOTION_API_KEY=ntn_..." > ~/.envs/notion.env

# 2. Share integration with your Notion pages
# In Notion: Page → ••• → Connections → Add your integration

# 3. Test it (auto-bootstraps on first run)
python3 .opencode/skills/notion/scripts/search_pages.py "test"
```

That's it. No manual `bootstrap` or `pip install` needed — scripts auto-detect
whether a virtual environment exists, create one if missing (using `uv` for
speed, or `pip` as fallback), install dependencies, and re-exec under the venv
Python. Subsequent runs skip bootstrap entirely.

## Environment Management

Scripts use an isolated `.venv/` inside the skill directory. This is created
and managed automatically.

| Scenario | What happens |
|----------|-------------|
| First run, no `.venv/` | Auto-creates venv, installs deps, re-execs |
| Subsequent runs | Detects venv, re-execs under venv Python |
| Deps missing | Delete `.venv/`, next run re-bootstraps |

### Manual usage (optional)

```bash
source .venv/bin/activate
python3 scripts/read_page.py <page-id>
deactivate
```

Or use the wrapper script:
```bash
scripts/run read_page.py <page-id>
```

## Installation for Other Users

1. Clone the repo containing this skill
2. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
3. Add API key to `~/.envs/notion.env`
4. Share pages with the integration in Notion
5. Run any script — auto-bootstrap handles the rest

## Dependencies

- Python 3.8+
- `requests>=2.31.0` (auto-installed by bootstrap)

## Files

```
notion/
├── scripts/
│   ├── notion_utils.py   # Shared utilities + auto-bootstrap
│   ├── run               # Optional wrapper script
│   ├── bootstrap          # Legacy setup script (still works)
│   └── *.py              # 15 command scripts
├── requirements.txt      # Python dependencies
├── SKILL.md             # Agent-facing documentation (loaded by skill system)
├── QUICK_REFERENCE.md   # Quick command lookup
└── .venv/               # Virtual environment (auto-created)
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'requests'"
Delete `.venv/` in the skill directory and run any script — it will re-bootstrap.

### API key issues
```bash
cat ~/.envs/notion.env  # Should show NOTION_API_KEY=ntn_...
```

### Permission issues
Open page in Notion → ••• → Connections → verify your integration is listed.

## See Also

- `SKILL.md` — Full documentation loaded by agents
- `QUICK_REFERENCE.md` — Quick "I want to..." command lookup
