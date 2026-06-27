# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Copy the canonical `ai` assets (skills + behaviour-protocol) into the opencode
package so they ship in the npm tarball. Build artifact — output is git-ignored and
must never be hand-edited. Idempotent; writes only inside --package-root."""
import argparse
import shutil
import sys
from pathlib import Path

SKILL_SOURCE_RELS = ["plugins/core/skills", "plugins/data/skills"]
PROTOCOL_SOURCE_REL = "plugins/core/hooks/behaviour-protocol.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--package-root", required=True, type=Path)
    args = ap.parse_args()
    repo = args.repo_root.resolve()
    pkg = args.package_root.resolve()
    pkg.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(repo / PROTOCOL_SOURCE_REL, pkg / "behaviour-protocol.md")

    skills_dst = pkg / "skills"
    if skills_dst.exists():
        shutil.rmtree(skills_dst)
    skills_dst.mkdir(parents=True)
    for src_rel in SKILL_SOURCE_RELS:
        src = repo / src_rel
        for skill_dir in sorted(p for p in src.iterdir() if (p / "SKILL.md").is_file()):
            shutil.copytree(skill_dir, skills_dst / skill_dir.name)

    print("synced assets to {}".format(pkg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
