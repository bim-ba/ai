# VHS tape — render with:  vhs .github/assets/demo.tape   (run from the repo root)
# Demos what `/setup` scaffolds. /setup runs inside Claude Code, so the tape shows
# the real commands as a transcript, then runs bootstrap.py (the engine /setup calls)
# in a throwaway dir so the scaffolding output is genuine and deterministic.
# The bootstrap invocation is wrapped in a short `setup` shim (defined off-camera)
# only to keep the long script path from wrapping on screen.

Output .github/assets/demo.gif

Set Theme "Catppuccin Mocha"
Set FontSize 20
Set Width 1240
Set Height 720
Set Padding 28
Set TypingSpeed 45ms

# --- hidden setup: remember repo, work in a clean temp dir, define shim, tidy prompt ---
Hide
Type "export REPO=$(pwd)" Enter
Type "cd $(mktemp -d)" Enter
Type `setup(){ uv run --no-project "$REPO/plugins/core/skills/setup/scripts/bootstrap.py" --project-root . --plugin-root "$REPO/plugins/core" --with "$1"; }` Enter
Type `PS1='\033[36m$ \033[0m'` Enter
Type "clear" Enter
Show

Sleep 800ms
Type "# 1. Add the marketplace in Claude Code:" Enter
Sleep 400ms
Type "#      /plugin marketplace add bim-ba/ai" Enter
Sleep 1s
Type "# 2. Scaffold your project:" Enter
Sleep 400ms
Type "#      /setup --with core,data" Enter
Sleep 1400ms
Type "# (/setup calls bootstrap.py — here's exactly what it creates)" Enter
Sleep 1200ms

Type "setup core,data" Enter
Sleep 2500ms

Type "find . -not -path '*/.git/*' -not -name '.' | sort" Enter
Sleep 3s

Type "# core agent behaviour + skills, wired and ready ✨" Enter
Sleep 2500ms
