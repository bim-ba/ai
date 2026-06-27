"""Presence + minimal-shape checks for repo-health files (no YAML dep)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestRepoHealth(unittest.TestCase):
    def test_security_exists(self):
        self.assertTrue((ROOT / "SECURITY.md").read_text(encoding="utf-8").strip())

    def test_contributing_exists(self):
        self.assertTrue((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").strip())

    def test_dependabot_two_ecosystems(self):
        txt = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("github-actions", txt)
        self.assertIn("npm", txt)
        self.assertNotIn("pip", txt)  # Python side is stdlib-only, no deps to bump


if __name__ == "__main__":
    unittest.main()
