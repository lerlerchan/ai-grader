#!/usr/bin/env bash
# Syntax-check any Python file just written or edited.
# CLAUDE_TOOL_INPUT_FILE_PATH is set by Claude Code on Write/Edit.

FILE="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"

if [[ -z "$FILE" ]]; then
  exit 0
fi

if [[ "$FILE" != *.py ]]; then
  exit 0
fi

if ! python3 -m py_compile "$FILE" 2>&1; then
  echo "HOOK: Syntax error in $FILE — fix before continuing." >&2
  exit 1
fi

echo "HOOK: $FILE syntax OK"
exit 0
