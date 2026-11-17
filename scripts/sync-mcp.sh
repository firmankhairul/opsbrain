#!/usr/bin/env bash
# Generate MCP server configs for every supported AI platform from this checkout.
#
# All paths are derived from the repo location, so a teammate only needs to:
#     pip install -e .
#     bash scripts/sync-mcp.sh
# and every platform points at their own clone. These generated files carry
# machine-specific absolute paths and are git-ignored (see .gitignore); this
# script is the source of truth.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVER_PATH="$PROJECT_DIR/msops/server.py"

# Prefer the project venv interpreter when present, else system python3.
PY="python3"
[[ -x "$PROJECT_DIR/.venv/bin/python" ]] && PY="$PROJECT_DIR/.venv/bin/python"

echo "ms-ops MCP registration"
echo "  interpreter : $PY"
echo "  server      : $SERVER_PATH"
echo ""

export PROJECT_DIR SERVER_PATH PY

# 0. Claude Code — .mcp.json (project MCP: ms-ops + gitlab; AWS MCP comes from the aws-core plugin)
"$PY" - <<'EOF'
import json, os, pathlib
proj = os.environ["PROJECT_DIR"]
p = pathlib.Path(proj) / ".mcp.json"
data = json.loads(p.read_text()) if p.exists() else {}
servers = data.setdefault("mcpServers", {})
servers["ms-ops"] = {
    "type": "stdio",
    "command": os.environ["PY"],
    "args": [os.environ["SERVER_PATH"]],
    "env": {},
}
for stale_server in ("aws-api", "aws-documentation", "aws-mcp"):
    servers.pop(stale_server, None)
# AWS MCP comes from the aws-core plugin (enabled in .claude/settings.json);
# a second copy here only duplicates it.
servers.setdefault("gitlab", {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@zereight/mcp-gitlab"],
    "env": {
        "GITLAB_API_URL": "https://gitlab.com/api/v4",
        "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PAT}",
        "GITLAB_READ_ONLY_MODE": "true",
    },
})
p.write_text(json.dumps(data, indent=2) + "\n")
print("  [Claude Code] OK   .mcp.json")
EOF

# 1. Claude Code settings — keep for team settings; MCP lives in .mcp.json.
"$PY" - <<'EOF'
import json, os, pathlib
p = pathlib.Path(os.environ["PROJECT_DIR"]) / ".claude/settings.json"
p.parent.mkdir(parents=True, exist_ok=True)
data = json.loads(p.read_text()) if p.exists() else {}
# MCP registration is owned by .mcp.json — drop any stale duplicate here.
data.pop("mcpServers", None)
p.write_text(json.dumps(data, indent=2) + "\n")
print("  [Claude Code] OK   .claude/settings.json (mcp handled by .mcp.json)")
EOF

# 2. Kiro — .kiro/settings/mcp.json
"$PY" - <<'EOF'
import json, os, pathlib
p = pathlib.Path(os.environ["PROJECT_DIR"]) / ".kiro/settings/mcp.json"
p.parent.mkdir(parents=True, exist_ok=True)
data = json.loads(p.read_text()) if p.exists() else {}
data.setdefault("mcpServers", {})["ms-ops"] = {
    "command": os.environ["PY"], "args": [os.environ["SERVER_PATH"]],
}
p.write_text(json.dumps(data, indent=2) + "\n")
print("  [Kiro]        OK   .kiro/settings/mcp.json")
EOF

# 3. OpenCode — opencode.jsonc (preserves other servers already present)
"$PY" - <<'EOF'
import json, os, pathlib
p = pathlib.Path(os.environ["PROJECT_DIR"]) / "opencode.jsonc"
try:
    data = json.loads(p.read_text()) if p.exists() else {}
except json.JSONDecodeError:
    data = {}
data.setdefault("$schema", "https://opencode.ai/config.json")
mcp = data.setdefault("mcp", {})
mcp.setdefault("terraform", {"type": "local", "command": ["npx", "-y", "terraform-mcp-server"], "enabled": True})
mcp["ms-ops"] = {"type": "local", "command": [os.environ["PY"], os.environ["SERVER_PATH"]], "enabled": True}
p.write_text(json.dumps(data, indent=2) + "\n")
print("  [OpenCode]    OK   opencode.jsonc")
EOF

# 4. Codex — ~/.codex/config.toml (global, per-user). Codex reads TOML only;
#    the old ~/.codex/config.json was never loaded.
"$PY" - <<'EOF'
import json, os, pathlib, re
p = pathlib.Path(os.path.expanduser("~/.codex/config.toml"))
p.parent.mkdir(parents=True, exist_ok=True)
text = p.read_text() if p.exists() else ""
block = (
    "[mcp_servers.ms-ops]\n"
    f"command = {json.dumps(os.environ['PY'])}\n"
    f"args = [{json.dumps(os.environ['SERVER_PATH'])}]\n"
)
# Replace an existing [mcp_servers.ms-ops] table up to the next table header.
pattern = re.compile(r"^\[mcp_servers\.ms-ops\]\n(?:(?!\[).*\n?)*", re.M)
if pattern.search(text):
    text = pattern.sub(lambda _: block + "\n", text)
else:
    text = text.rstrip("\n") + "\n\n" + block
p.write_text(text)
print("  [Codex]       OK   ~/.codex/config.toml")
EOF

# 5. Gemini CLI — .gemini/settings.json
"$PY" - <<'EOF'
import json, os, pathlib
p = pathlib.Path(os.environ["PROJECT_DIR"]) / ".gemini/settings.json"
p.parent.mkdir(parents=True, exist_ok=True)
data = json.loads(p.read_text()) if p.exists() else {}
data.setdefault("mcpServers", {})["ms-ops"] = {
    "command": os.environ["PY"], "args": [os.environ["SERVER_PATH"]],
}
p.write_text(json.dumps(data, indent=2) + "\n")
print("  [Gemini CLI]  OK   .gemini/settings.json")
EOF

echo ""
echo "Done. Restart your AI agent to pick up the MCP servers."
echo "Note: AWS MCP is provided by the aws-core plugin; gitlab needs GITLAB_PAT."
