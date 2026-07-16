# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Validity + invariant checks for every shipped JSON config (the CI lint backbone)."""
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

JSON_FILES = [
    ".claude-plugin/marketplace.json",
    "plugins/core/.claude-plugin/plugin.json",
    "plugins/data/.claude-plugin/plugin.json",
    "plugins/core/hooks/hooks.json",
]


def load(rel):
    return json.loads((REPO / rel).read_text())


class Manifests(unittest.TestCase):
    def test_all_json_files_parse(self):
        for rel in JSON_FILES:
            with self.subTest(file=rel):
                self.assertTrue((REPO / rel).is_file(), rel + " missing")
                load(rel)  # raises on invalid JSON

    def test_marketplace_identity(self):
        m = load(".claude-plugin/marketplace.json")
        self.assertEqual(m["name"], "ai")
        names = {p["name"] for p in m["plugins"]}
        self.assertEqual(names, {"core", "data"})
        for p in m["plugins"]:
            self.assertTrue((REPO / p["source"]).is_dir(), p["source"] + " missing")


if __name__ == "__main__":
    unittest.main()
