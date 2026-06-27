# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Sync assets, then assert the would-be npm tarball for @bim-ba/ai-opencode contains
the bundled behaviour-protocol.md and at least one skills/<name>/SKILL.md. stdlib only."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True, type=Path)
    args = ap.parse_args()
    repo = args.repo_root.resolve()
    pkg = repo / "packages" / "ai-opencode"

    sync = pkg / "scripts" / "sync-assets.py"
    rc = subprocess.run([sys.executable, str(sync),
                         "--repo-root", str(repo), "--package-root", str(pkg)])
    if rc.returncode != 0:
        sys.stderr.write("check-pack: sync-assets failed\n")
        return 1

    out = subprocess.run(["npm", "pack", "--dry-run", "--json"],
                         cwd=str(pkg), capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write("check-pack: npm pack failed\n" + out.stderr)
        return 1

    # npm pack output may include non-JSON lines before the JSON array.
    # Find the start of the JSON array and parse from there.
    json_start = out.stdout.find('[')
    if json_start < 0:
        sys.stderr.write("check-pack: no JSON array in npm pack output\n")
        return 1
    entries = json.loads(out.stdout[json_start:])[0]["files"]
    paths = {f["path"] for f in entries}
    has_protocol = "behaviour-protocol.md" in paths
    has_skill = any(p.startswith("skills/") and p.endswith("/SKILL.md") for p in paths)
    if not has_protocol or not has_skill:
        sys.stderr.write(
            "check-pack: tarball missing assets (protocol={}, skill={})\n".format(has_protocol, has_skill))
        return 1

    print("pack OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
