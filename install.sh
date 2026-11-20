#!/usr/bin/env bash
# Installs demo-vid-studio globally for Antigravity, Claude Code, and Gemini CLI on macOS / Linux.
# Usage: ./install.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_ROOT/skills/demo-vid-studio"

install_target() {
  local name="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  cp -R "$SKILL_SRC" "$dest"
  echo "[OK] Installed demo-vid-studio for $name -> $dest"
}

install_target "Antigravity" "$HOME/.gemini/config/skills/demo-vid-studio"
install_target "Claude Code" "$HOME/.claude/skills/demo-vid-studio"
install_target "Gemini CLI"  "$HOME/.gemini/skills/demo-vid-studio"

echo ""
echo "All set! Ask Antigravity or Claude Code: 'Record a demo video for this project'"
