# Notion Skill Bug Reports

## Bug 1: venv auto-bootstrap breaks `python3 -c` inline scripts

**Date**: 2026-03-16
**Severity**: Medium
**File**: `/Users/mike/.config/opencode/skills/notion/scripts/notion_utils.py`

**Description**: When running inline Python via `python3 -c "from notion_utils import ..."` from within the skill's `scripts/` directory, the auto-bootstrap logic in `notion_utils.py` intercepts the invocation and re-execs using `os.execv()` with `sys.argv`. For `-c` invocations, `sys.argv` is `['/path/to/python3', '-c', '<code>']`, but after re-exec under the venv python, the `-c` argument gets misinterpreted -- the venv python sees `Argument expected for the -c option` and exits.

**Root cause**: Lines 127-140 of `notion_utils.py` call `os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON)] + sys.argv)`. When the original invocation is `python3 -c "code"`, `sys.argv` is `['-c']` (the code string is consumed by the interpreter, not passed as an argv element). So the re-exec becomes `venv/python3 /path/to/python3 -c` -- wrong.

**Workaround**: Write standalone `.py` files instead of using `-c` inline scripts when importing from `notion_utils`.

**Suggested fix**: Detect `-c` mode (e.g., check if `sys.argv[0] == '-c'` or if the script path doesn't exist as a file) and skip the re-exec, or document that `notion_utils` must be imported from actual script files only.
