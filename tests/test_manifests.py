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
    "opencode.json",
    "packages/ai-opencode/package.json",
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

    def test_opencode_package_manifest(self):
        pkg = load("packages/ai-opencode/package.json")
        self.assertEqual(pkg["name"], "@bim-ba/ai-opencode")
        self.assertEqual(pkg["type"], "module")
        self.assertIn("opencode", pkg["engines"])
        self.assertEqual(pkg["publishConfig"]["access"], "public")

    def test_opencode_dogfood_config_points_at_real_paths(self):
        c = load("opencode.json")
        for instr in c["instructions"]:
            self.assertTrue((REPO / instr).is_file(), instr + " missing")
        for sp in c["skills"]["paths"]:
            self.assertTrue((REPO / sp).is_dir(), sp + " missing")


if __name__ == "__main__":
    unittest.main()
