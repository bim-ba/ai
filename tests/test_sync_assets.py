# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Tests for the opencode-adapter asset-sync script (canonical → package, no duplication)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SYNC = REPO / "packages" / "ai-opencode" / "scripts" / "sync-assets.py"
SKILL_SOURCE_DIRS = [REPO / "plugins" / "core" / "skills", REPO / "plugins" / "data" / "skills"]
PROTOCOL_SOURCE = REPO / "plugins" / "core" / "hooks" / "behaviour-protocol.md"


def run_sync(package_root):
    return subprocess.run(
        [sys.executable, str(SYNC),
         "--repo-root", str(REPO),
         "--package-root", str(package_root)],
        capture_output=True, text=True)


def source_skill_names():
    names = set()
    for d in SKILL_SOURCE_DIRS:
        for p in d.iterdir():
            if (p / "SKILL.md").is_file():
                names.add(p.name)
    return names


class SyncAssets(unittest.TestCase):
    def test_copies_protocol_and_every_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_sync(tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            pkg = Path(tmp)
            # behaviour-protocol.md copied verbatim
            self.assertTrue((pkg / "behaviour-protocol.md").is_file())
            self.assertEqual((pkg / "behaviour-protocol.md").read_text(),
                             PROTOCOL_SOURCE.read_text())
            # every source skill landed as <skills>/<name>/SKILL.md
            copied = {p.name for p in (pkg / "skills").iterdir()
                      if (p / "SKILL.md").is_file()}
            self.assertEqual(copied, source_skill_names())
            # known anchors from each plugin
            self.assertTrue((pkg / "skills" / "setup" / "SKILL.md").is_file())
            self.assertTrue((pkg / "skills" / "clickhouse-query-best-practices" / "SKILL.md").is_file())

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_sync(tmp)
            first = sorted(p.relative_to(tmp).as_posix() for p in Path(tmp).rglob("*"))
            run_sync(tmp)
            second = sorted(p.relative_to(tmp).as_posix() for p in Path(tmp).rglob("*"))
            self.assertEqual(first, second)

    def test_writes_only_inside_package_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            sentinel_before = sorted(p.name for p in REPO.iterdir())
            run_sync(tmp)
            sentinel_after = sorted(p.name for p in REPO.iterdir())
            self.assertEqual(sentinel_before, sentinel_after)  # repo root untouched


if __name__ == "__main__":
    unittest.main()
