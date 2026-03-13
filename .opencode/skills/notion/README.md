# Notion Skill for Claude Code

Complete Notion document management via API. Search, read, write, update, delete, and analyze content.

## Quick Setup

```bash
# 1. Clone or copy skill to ~/.claude/skills/notion
cd ~/.claude/skills/notion

# 2. Run bootstrap script (installs dependencies in isolated venv)
./scripts/bootstrap

# 3. Configure API key
echo "NOTION_API_KEY=secret_..." > ~/.envs/notion.env

# 4. Share integration with your Notion pages
# In Notion: Page → ••• → Connections → Add your integration

# 5. Test it
scripts/search_pages.py "test"
```

## Environment Management

The skill uses an isolated Python virtual environment (`.venv/`) to avoid dependency conflicts.

### First Time Setup
```bash
./scripts/bootstrap
```

This will:
- Create `.venv/` virtual environment
- Install `requests` library
- Verify installation
- Check for API key configuration

### How It Works

**Scripts automatically detect and use the virtual environment:**
- `notion_utils.py` adds `.venv/site-packages` to `sys.path`
- No manual activation needed when running scripts directly
- Dependencies persist across sessions

### Manual Usage

If you prefer to activate the venv manually:
```bash
source .venv/bin/activate
python3 scripts/read_page.py <page-id>
deactivate
```

Or use the wrapper:
```bash
scripts/run read_page.py <page-id>
```

## Installation for Other Users

When sharing this skill:

**1. Share as Git repository:**
```bash
git clone https://github.com/yourusername/notion-skill
cd notion-skill
./scripts/bootstrap
```

**2. Each user needs their own:**
- Notion integration (create at notion.so/my-integrations)
- API key in `~/.envs/notion.env`
- Shared pages (add integration in Notion)

## Dependencies

- Python 3.8+
- `requests>=2.31.0` (installed by bootstrap script)

Dependencies are isolated in `.venv/` and don't affect system Python or other skills.

## Files

```
notion/
├── scripts/
│   ├── bootstrap          # Setup script (run once)
│   ├── run               # Wrapper to run scripts with venv
│   ├── notion_utils.py   # Shared utilities (auto-loads venv)
│   └── *.py              # 15 command scripts
├── requirements.txt      # Python dependencies
├── SKILL.md             # Comprehensive documentation
├── QUICK_REFERENCE.md   # Quick command lookup
└── .venv/               # Virtual environment (created by bootstrap)
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'requests'"

Run the bootstrap script:
```bash
cd ~/.claude/skills/notion
./scripts/bootstrap
```

### Scripts still can't find requests

Check that venv exists:
```bash
ls -la .venv/
```

If missing, run bootstrap again. If venv exists but scripts fail, check Python version:
```bash
python3 --version  # Should be 3.8+
```

### API key issues

Verify configuration:
```bash
cat ~/.envs/notion.env  # Should show NOTION_API_KEY=secret_...
```

### Permission issues

Verify integration is shared with the page:
- Open page in Notion
- Click ••• (three dots)
- Connections → Should see your integration listed

## Best Practices for Skill Publishing

When publishing this skill for others:

1. **Include bootstrap script** - Auto-setup is critical
2. **Document setup clearly** - See "Quick Setup" above
3. **Don't commit .venv/** - Add to .gitignore
4. **Include requirements.txt** - Pin dependency versions
5. **Test on clean system** - Verify bootstrap works

## See Also

- `SKILL.md` - Full documentation for all 16 scripts
- `QUICK_REFERENCE.md` - "I want to..." command lookup
- `/tmp/notion_skill_improvement_plan.md` - Performance optimization plans
