# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""E2E tests for the /setup bootstrap script — marketplace wiring under the `ai` brand."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "plugins" / "core" / "skills" / "setup" / "scripts" / "bootstrap.py"
PLUGIN_ROOT = REPO / "plugins" / "core"


def run_bootstrap(project_root, with_plugins="core"):
    return subprocess.run(
        [sys.executable, str(BOOTSTRAP),
         "--project-root", str(project_root),
         "--plugin-root", str(PLUGIN_ROOT),
         "--with", with_plugins],
        capture_output=True, text=True)


def load_settings(project_root):
    return json.loads((Path(project_root) / ".claude" / "settings.json").read_text(encoding="utf-8"))


class BootstrapWiring(unittest.TestCase):
    def test_enables_plugins_under_ai_marketplace(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_bootstrap(tmp, "core,data")
            self.assertEqual(r.returncode, 0, r.stderr)
            s = load_settings(tmp)
            self.assertIn("ai", s["extraKnownMarketplaces"])
            self.assertEqual(
                s["extraKnownMarketplaces"]["ai"],
                {"source": {"source": "github", "repo": "bim-ba/ai"}})
            self.assertIs(s["enabledPlugins"].get("core@ai"), True)
            self.assertIs(s["enabledPlugins"].get("data@ai"), True)

    def test_merge_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude = Path(tmp) / ".claude"
            claude.mkdir()
            (claude / "settings.json").write_text(json.dumps({
                "enabledPlugins": {"core@spark": True},
                "customKey": 123,
            }), encoding="utf-8")
            r = run_bootstrap(tmp, "core")
            self.assertEqual(r.returncode, 0, r.stderr)
            s = load_settings(tmp)
            self.assertIs(s["enabledPlugins"].get("core@spark"), True)  # stale key preserved
            self.assertIs(s["enabledPlugins"].get("core@ai"), True)     # new key added
            self.assertEqual(s["customKey"], 123)                       # unrelated key preserved

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_bootstrap(tmp, "core,data")
            first = load_settings(tmp)
            run_bootstrap(tmp, "core,data")
            second = load_settings(tmp)
            self.assertEqual(first, second)

    def test_agents_falls_back_to_copy_when_symlink_unavailable(self):
        # Force symlink creation to fail (as on Windows without privilege) and assert
        # bootstrap falls back to a regular-file AGENTS.md mirroring CLAUDE.md.
        #
        # We patch pathlib.Path.symlink_to (the exact call bootstrap makes) rather than
        # os.symlink: on Python 3.9/3.10 pathlib binds os.symlink via an internal accessor
        # captured at import, so patching os.symlink would not take effect. We run main()
        # in-process so the patch is visible (a subprocess would not see it).
        import contextlib
        import importlib.util
        import io
        import unittest.mock as mock

        spec = importlib.util.spec_from_file_location("bootstrap_fallback", BOOTSTRAP)
        bootstrap_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap_mod)

        with tempfile.TemporaryDirectory() as tmp:
            argv = ["bootstrap.py", "--project-root", tmp,
                    "--plugin-root", str(PLUGIN_ROOT), "--with", "core"]
            with mock.patch("pathlib.Path.symlink_to", side_effect=OSError("symlink not permitted")), \
                    mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = bootstrap_mod.main()
            self.assertEqual(rc, 0)
            agents = Path(tmp) / "AGENTS.md"
            claude = Path(tmp) / "CLAUDE.md"
            self.assertTrue(agents.is_file())          # exists as a real file
            self.assertFalse(agents.is_symlink())      # not a (broken) symlink
            self.assertEqual(agents.read_text(encoding="utf-8"),
                             claude.read_text(encoding="utf-8"))  # mirrors CLAUDE.md


if __name__ == "__main__":
    unittest.main()
