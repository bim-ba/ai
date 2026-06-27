# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Tests for verify.py post-checks under the `ai` brand, plus a bootstrap→verify roundtrip."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VERIFY = REPO / "plugins" / "core" / "skills" / "setup" / "scripts" / "verify.py"
BOOTSTRAP = REPO / "plugins" / "core" / "skills" / "setup" / "scripts" / "bootstrap.py"
PLUGIN_ROOT = REPO / "plugins" / "core"


def run_verify(project_root):
    return subprocess.run(
        [sys.executable, str(VERIFY), "--project-root", str(project_root)],
        capture_output=True, text=True)


def seed(project_root, settings):
    root = Path(project_root)
    (root / ".claude" / "drift-log" / "open").mkdir(parents=True)
    (root / ".claude" / "drift-log" / "applied").mkdir(parents=True)
    (root / ".claude" / "settings.json").write_text(json.dumps(settings))


class VerifyChecks(unittest.TestCase):
    def test_ok_with_ai_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed(tmp, {
                "extraKnownMarketplaces": {
                    "ai": {"source": {"source": "github", "repo": "bim-ba/ai"}}},
                "enabledPlugins": {"core@ai": True},
            })
            r = run_verify(tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("verify OK", r.stdout)

    def test_fails_when_only_spark_key_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed(tmp, {
                "extraKnownMarketplaces": {
                    "spark": {"source": {"source": "github", "repo": "bim-ba/ai"}}},
                "enabledPlugins": {"core@spark": True},
            })
            r = run_verify(tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("enabledPlugins.core@ai absent", r.stdout)
            self.assertIn("extraKnownMarketplaces.ai absent", r.stdout)

    def test_bootstrap_then_verify_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            br = subprocess.run(
                [sys.executable, str(BOOTSTRAP),
                 "--project-root", tmp, "--plugin-root", str(PLUGIN_ROOT),
                 "--with", "core,data"], capture_output=True, text=True)
            self.assertEqual(br.returncode, 0, br.stdout + br.stderr)
            r = run_verify(tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("verify OK", r.stdout)


if __name__ == "__main__":
    unittest.main()
