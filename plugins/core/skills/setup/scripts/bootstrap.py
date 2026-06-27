# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Idempotent ai project scaffold. Creates missing artifacts, never overwrites."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def project_name(root):
    try:
        url = subprocess.check_output(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL, text=True).strip()
        if url:
            name = url.rstrip("/").split("/")[-1]
            return name[:-4] if name.endswith(".git") else name
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return root.name


def merge_settings(root, plugin_names, actions):
    path = root / ".claude" / "settings.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    changed = not path.exists()

    mkts = settings.setdefault("extraKnownMarketplaces", {})
    if "ai" not in mkts:
        mkts["ai"] = {"source": {"source": "github", "repo": "bim-ba/ai"}}
        changed = True

    plugins = settings.setdefault("enabledPlugins", {})
    for name in plugin_names:
        key = name + "@ai"
        if key not in plugins:
            plugins[key] = True
            changed = True

    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2) + "\n")
    actions.append(("PATCHED" if changed else "SKIPPED", ".claude/settings.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--plugin-root", required=True, type=Path)
    ap.add_argument("--with", dest="with_plugins", default="core",
                    help="comma-separated ai plugin names to enable (core is always included)")
    args = ap.parse_args()

    root = args.project_root.resolve()
    templates = args.plugin_root.resolve() / "templates"
    actions = []

    def mkdir(rel):
        p = root / rel
        actions.append(("SKIPPED" if p.is_dir() else "CREATED", rel + "/"))
        p.mkdir(parents=True, exist_ok=True)

    def copy(src_name, rel):
        dst = root / rel
        if dst.exists():
            actions.append(("SKIPPED", rel))
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(templates / src_name, dst)
        actions.append(("CREATED", rel))

    mkdir(".claude/drift-log/open")
    mkdir(".claude/drift-log/applied")
    copy("claudelintrc.json", ".claudelintrc.json")
    copy("claudelintignore", ".claudelintignore")
    copy("skills-authoring-standard.md", ".claude/skills/README.md")

    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        actions.append(("SKIPPED", "CLAUDE.md"))
    else:
        tmpl = (templates / "CLAUDE.md.tmpl").read_text(encoding="utf-8")
        claude_md.write_text(tmpl.replace("{{PROJECT_NAME}}", project_name(root)), encoding="utf-8")
        actions.append(("CREATED", "CLAUDE.md"))
        agents = root / "AGENTS.md"
        if agents.is_symlink():
            actions.append(("SKIPPED", "AGENTS.md (symlink exists)"))
        elif agents.exists():
            actions.append(("WARN", "AGENTS.md is a real file — left as-is"))
        else:
            try:
                agents.symlink_to("CLAUDE.md")
                actions.append(("CREATED", "AGENTS.md -> CLAUDE.md"))
            except OSError:
                # Windows without privilege/Developer Mode can't create symlinks —
                # fall back to a regular file mirroring CLAUDE.md (verify.py accepts a non-symlink AGENTS.md).
                shutil.copyfile(claude_md, agents)
                actions.append(("CREATED", "AGENTS.md (copy of CLAUDE.md — symlink unavailable)"))

    requested = [p.strip() for p in args.with_plugins.split(",") if p.strip()]
    plugin_names = []
    for name in ["core"] + requested:          # core always first
        if name not in plugin_names:
            plugin_names.append(name)
    merge_settings(root, plugin_names, actions)

    if shutil.which("claudelint") is None:
        print("note: claudelint not found — install it to lint your agent surface "
              "(config written anyway).")

    print("/setup complete")
    print("=" * 51)
    for status, label in actions:
        print(" {:<8} {}".format(status, label))
    print("=" * 51)
    return 0


if __name__ == "__main__":
    sys.exit(main())
