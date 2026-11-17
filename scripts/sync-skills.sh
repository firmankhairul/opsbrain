#!/usr/bin/env bash
# Sync skills from the single source of truth to every mirror.
#
# Source of truth : .claude/skills/<name>/SKILL.md   (Claude Code native format)
# Mirrors         : .opencode/agents/<name>.md
#                   .kiro/skills/<name>/SKILL.md
#                   .gemini/skills/<name>/SKILL.md
#                   .agents/skills/<name>/SKILL.md   (Codex, project-local)
#                   ~/.claude/skills/<name>          (symlink, so global Claude
#                                                     sees the repo skills)
#
# Paths are derived from the repo location, so this is portable across machines.
# Run after adding, editing, OR REMOVING any skill.
#
# Stale mirror entries are pruned: a skill deleted from .claude/skills/ is
# removed from every mirror on the next run. Without this the mirrors drift —
# they were last seen holding 16/22/15/20 skills for the same 16 sources.
#
# Only skills owned by this repo are linked globally. Skills that merely live
# in ~/.claude/skills/ (installed separately) are never touched.
#
# MSOPS_NO_GLOBAL_SKILLS=1 (export it in your shell) skips the global symlinks
# entirely and removes the ones this repo made earlier. Use it when you want
# the repo skills to load only inside the repo, not in every Claude session.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SOURCE_DIR="$PROJECT_DIR/.claude/skills"

OPENCODE_DIR="$PROJECT_DIR/.opencode/agents"
KIRO_DIR="$PROJECT_DIR/.kiro/skills"
GEMINI_DIR="$PROJECT_DIR/.gemini/skills"
AGENTS_DIR="$PROJECT_DIR/.agents/skills"
GLOBAL_DIR="$HOME/.claude/skills"

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Source directory not found: $SOURCE_DIR"
    exit 1
fi

mkdir -p "$OPENCODE_DIR" "$KIRO_DIR" "$GEMINI_DIR" "$AGENTS_DIR" "$GLOBAL_DIR"

# Skills this repo owns, by directory name.
mapfile -t OWNED < <(find "$SOURCE_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

echo "Syncing ${#OWNED[@]} skills from: $SOURCE_DIR"
echo ""

# --- Validate against the Agent Skills spec (agentskills.io) ---------------
# Claude Code and Kiro both read this format; a skill that fails here is
# skipped by Kiro or matched poorly by Claude. Refuse to mirror a broken set.
"${PYTHON:-python3}" - "$SOURCE_DIR" <<'PY' || { echo "Skill validation failed — fix the errors above."; exit 1; }
import pathlib, re, sys, yaml
SPEC = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
CLAUDE_ONLY = {"when_to_use", "argument-hint", "arguments", "disable-model-invocation",
               "user-invocable", "disallowed-tools", "model", "effort", "context",
               "agent", "background", "paths", "shell", "hooks"}
errors = 0
for skill in sorted(pathlib.Path(sys.argv[1]).glob("*/SKILL.md")):
    d, text = skill.parent, skill.read_text()
    def err(msg):
        global errors; errors += 1; print(f"  ERROR  {d.name}: {msg}")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        err("frontmatter missing or not on line 1"); continue
    fm = yaml.safe_load(m.group(1)) or {}
    name, desc = fm.get("name", ""), str(fm.get("description", ""))
    if name != d.name: err(f"name '{name}' must equal folder name")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name or "") or len(name) > 64:
        err("name: lowercase letters, digits, single hyphens, max 64")
    if not 1 <= len(desc) <= 1024: err(f"description length {len(desc)} (1-1024)")
    if "use when" not in desc.lower(): err("description must say when to use it ('Use when ...')")
    extra = set(fm) - SPEC - CLAUDE_ONLY
    if extra: err(f"non-spec keys {sorted(extra)} — move them under metadata:")
    if any(not isinstance(v, str) for v in (fm.get("metadata") or {}).values()):
        err("metadata values must be strings (quote versions)")
    if len(text.splitlines()) > 500: err("SKILL.md over 500 lines — move detail to references/")
    for link in re.findall(r"\]\(((?:references|scripts|assets)/[^)#]+)\)", text):
        if not (d / link).exists(): err(f"broken link {link}")
    if "/home/" in text: err("absolute /home path")
sys.exit(1 if errors else 0)
PY
echo "  Validation passed (Agent Skills spec)."
echo ""

# --- Prune stale mirror entries -------------------------------------------
# A skill removed from the source must disappear from the mirrors too.
is_owned() { local n="$1"; for o in "${OWNED[@]}"; do [[ "$o" == "$n" ]] && return 0; done; return 1; }

pruned=0
for base in "$KIRO_DIR" "$GEMINI_DIR" "$AGENTS_DIR"; do
    for e in "$base"/*; do
        # -e fails on a broken symlink, so test -L as well: mirrors accumulate
        # dangling links when a skill is removed from the source.
        [[ -e "$e" || -L "$e" ]] || continue
        n="$(basename "$e")"
        is_owned "$n" || { rm -rf "$e"; echo "  PRUNE  $n  ($(basename "$(dirname "$base")")/$(basename "$base"))"; pruned=$((pruned + 1)); }
    done
done
for f in "$OPENCODE_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    n="$(basename "$f" .md)"
    is_owned "$n" || { rm -f "$f"; echo "  PRUNE  $n  (opencode)"; pruned=$((pruned + 1)); }
done
# Global: only remove links that point back into THIS repo. Never touch
# independently installed skills.
for l in "$GLOBAL_DIR"/*; do
    [[ -L "$l" ]] || continue
    tgt="$(readlink -f "$l" 2>/dev/null || true)"
    [[ "$tgt" == "$SOURCE_DIR"/* ]] || continue
    n="$(basename "$l")"
    if [[ "${MSOPS_NO_GLOBAL_SKILLS:-0}" == "1" ]]; then
        rm -f "$l"; echo "  PRUNE  $n  (global, MSOPS_NO_GLOBAL_SKILLS=1)"; pruned=$((pruned + 1))
    else
        is_owned "$n" || { rm -f "$l"; echo "  PRUNE  $n  (global)"; pruned=$((pruned + 1)); }
    fi
done
[[ $pruned -gt 0 ]] && echo "" || true

count=0

for src in "$SOURCE_DIR"/*/SKILL.md; do
    [[ -e "$src" ]] || continue

    skill_dir="$(dirname "$src")"
    skill_name="$(basename "$skill_dir")"

    # Skip symlinked skills (third-party Claude plugins live under .agents/skills/).
    [[ -L "$skill_dir" ]] && continue

    # Prefer the frontmatter name when present; fall back to the directory name.
    fm_name="$(awk -F': *' '/^name:/{print $2; exit}' "$src" | tr -d '"' | tr -d "'" | xargs || true)"
    [[ -n "$fm_name" ]] && skill_name="$fm_name"

    # 1. OpenCode project agents (flat structure)
    cp --remove-destination "$src" "$OPENCODE_DIR/$skill_name.md"

    # 2. Kiro project skills (subfolder structure)
    mkdir -p "$KIRO_DIR/$skill_name"
    cp --remove-destination "$src" "$KIRO_DIR/$skill_name/SKILL.md"

    # 3. Gemini CLI project skills (subfolder structure)
    mkdir -p "$GEMINI_DIR/$skill_name"
    cp --remove-destination "$src" "$GEMINI_DIR/$skill_name/SKILL.md"

    # 4. Codex project skills (subfolder structure)
    mkdir -p "$AGENTS_DIR/$skill_name"
    cp --remove-destination "$src" "$AGENTS_DIR/$skill_name/SKILL.md"

    # 4b. Carry references/ along. A SKILL.md using progressive disclosure
    #     points at references/*.md; mirroring SKILL.md alone would leave
    #     those links dangling (every skill here does this).
    if [[ -d "$skill_dir/references" ]]; then
        for dest in "$KIRO_DIR/$skill_name" "$GEMINI_DIR/$skill_name" "$AGENTS_DIR/$skill_name"; do
            rm -rf "$dest/references"
            cp -r "$skill_dir/references" "$dest/references"
        done
    fi

    # 5. Global Claude skills — symlink to the repo dir so edits are live.
    #    Skip if a real directory is already there (separately installed skill).
    global_link="$GLOBAL_DIR/$skill_name"
    global_note="global"
    if [[ "${MSOPS_NO_GLOBAL_SKILLS:-0}" == "1" ]]; then
        global_note="global skipped (MSOPS_NO_GLOBAL_SKILLS=1)"
    elif [[ -e "$global_link" && ! -L "$global_link" ]]; then
        global_note="global SKIPPED (a real directory exists there)"
    else
        ln -sfn "$skill_dir" "$global_link"
    fi

    echo "  OK  $skill_name  → opencode, kiro, gemini, agents, $global_note"
    count=$((count + 1))
done

echo ""
echo "Done. $count skills synced."
echo ""

# Sync ops-rules.md to Kiro steering (agents that auto-load steering docs)
OPS_RULES="$PROJECT_DIR/ops-rules.md"
if [[ -f "$OPS_RULES" ]]; then
    KIRO_STEERING="$PROJECT_DIR/.kiro/steering"
    mkdir -p "$KIRO_STEERING"
    cp --remove-destination "$OPS_RULES" "$KIRO_STEERING/ops-rules.md"
    echo "[Kiro]  OK  .kiro/steering/ops-rules.md"
    echo "ops-rules.md synced. CLAUDE.md, AGENTS.md, GEMINI.md are managed directly in repo root."
fi
