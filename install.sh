#!/bin/sh
# Install the Claude Code slash command. Usage: ./install.sh [command-name]
set -e
NAME="${1:-move-to-opencode}"
DIR="$HOME/.claude/skills/$NAME"
mkdir -p "$DIR"
cp "$(dirname "$0")/move-to-opencode.py" "$DIR/move-to-opencode.py"
sed -e "s|__NAME__|$NAME|g" -e "s|__SCRIPT__|$DIR/move-to-opencode.py|g" \
  "$(dirname "$0")/SKILL.md.template" > "$DIR/SKILL.md"
echo "installed /$NAME -> $DIR"
