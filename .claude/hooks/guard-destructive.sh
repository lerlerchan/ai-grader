#!/usr/bin/env bash
# Block destructive bash commands without explicit intent.
# Reads the command from CLAUDE_TOOL_INPUT_COMMAND env var (set by Claude Code).

CMD="${CLAUDE_TOOL_INPUT_COMMAND:-}"

danger_patterns=(
  "rm -rf"
  "rm -fr"
  "DROP TABLE"
  "DROP DATABASE"
  "git reset --hard"
  "git clean -f"
  "git push --force"
  "git push -f"
  "truncate"
  "> /dev/sd"
)

for pattern in "${danger_patterns[@]}"; do
  if echo "$CMD" | grep -qi "$pattern"; then
    echo "HOOK BLOCKED: Destructive pattern detected: '$pattern'" >&2
    echo "Review the command before proceeding." >&2
    exit 1
  fi
done

exit 0
