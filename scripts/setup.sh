#!/usr/bin/env bash
# One command to make a fresh clone usable from Claude Code, Kiro and Codex.
#
#     bash scripts/setup.sh                 # everything
#     bash scripts/setup.sh --no-submodules # skip cloning customer submodules
#     bash scripts/setup.sh --no-mcp        # skip writing MCP configs (they are per-user)
#
# What it does, and why each step exists:
#   1. customer submodules  -- empty folders otherwise, and MCP lookups find nothing
#   2. sync-skills.sh       -- .agents/skills (Codex), .kiro/skills + .kiro/steering/ops-rules.md
#                              (Kiro), .gemini/skills are GENERATED and git-ignored; without
#                              this those agents have no skills at all
#   3. sync-mcp.sh          -- MCP configs carry absolute paths, so each person generates
#                              their own (.mcp.json, .kiro/settings/mcp.json, ~/.codex/config.toml)
#   4. git hook             -- after every pull that touches skills, refresh the mirrors
#
# Safe to re-run.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

SUBMODULES=1; MCP=1
for a in "$@"; do
  case "$a" in
    --no-submodules) SUBMODULES=0 ;;
    --no-mcp) MCP=0 ;;
    -h|--help) sed -n 2,19p "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

if [[ $SUBMODULES -eq 1 ]]; then
  echo "[1/4] customer submodules"
  git submodule update --init --recursive || echo "  warning: some submodules failed (access?); continue, fix later"
else
  echo "[1/4] customer submodules: skipped"
fi

echo "[2/4] skills for Codex / Kiro / Gemini / OpenCode + ~/.claude/skills"
bash scripts/sync-skills.sh | tail -4

if [[ $MCP -eq 1 ]]; then
  echo "[3/4] MCP config (per-user, git-ignored)"
  bash scripts/sync-mcp.sh | grep -E "OK|SKIP|WARN" || true
else
  echo "[3/4] MCP config: skipped"
fi

echo "[4/4] git hook: refresh skill mirrors after pull"
git config core.hooksPath .githooks
echo "  core.hooksPath = .githooks"

echo
if [[ ! -f monthly-report/template/ICS_Compute_Deck_Template.pptx ]]; then
  echo "Optional, for customer decks/DOCX with the Example MSP Kit look:"
  echo "  python3 scripts/download_brand_assets.py"
fi
echo "Done. Restart Claude Code / Kiro / Codex so skills and MCP are picked up."
