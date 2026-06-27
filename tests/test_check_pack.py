# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Tests for the npm-pack tarball-contents check (skips cleanly where npm is absent)."""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "packages" / "ai-opencode" / "scripts" / "check-pack.py"


@unittest.skipIf(shutil.which("npm") is None, "npm not available")
class CheckPack(unittest.TestCase):
    def test_pack_includes_synced_assets(self):
        r = subprocess.run(
            [sys.executable, str(CHECK), "--repo-root", str(REPO)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("pack OK", r.stdout)


if __name__ == "__main__":
    unittest.main()
