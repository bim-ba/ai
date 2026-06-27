# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Post-checks for ai /setup. Exits non-zero on any failure."""
import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True, type=Path)
    args = ap.parse_args()
    root = args.project_root.resolve()
    errors = []

    for d in (".claude/drift-log/open", ".claude/drift-log/applied"):
        if not (root / d).is_dir():
            errors.append("missing dir: " + d)

    settings_path = root / ".claude" / "settings.json"
    if not settings_path.exists():
        errors.append("missing .claude/settings.json")
    else:
        s = json.loads(settings_path.read_text())
        if "ai" not in s.get("extraKnownMarketplaces", {}):
            errors.append("settings.json: extraKnownMarketplaces.ai absent")
        if "core@ai" not in s.get("enabledPlugins", {}):
            errors.append("settings.json: enabledPlugins.core@ai absent")

    agents = root / "AGENTS.md"
    if agents.is_symlink() and str(agents.readlink()) != "CLAUDE.md":
        errors.append("AGENTS.md symlink points to {}, expected CLAUDE.md".format(agents.readlink()))

    if errors:
        print("verify FAILED:")
        for e in errors:
            print("  - " + e)
        return 1
    print("verify OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
