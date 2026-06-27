# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""E2E tests for the /setup bootstrap script — marketplace wiring under the `ai` brand."""
import json
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "plugins" / "core" / "skills" / "setup" / "scripts" / "bootstrap.py"
PLUGIN_ROOT = REPO / "plugins" / "core"


def run_bootstrap(project_root, with_plugins="core"):
    # Try to detect if mocking is active (for the symlink unavailability test).
    # If os.symlink is mocked, run bootstrap in-process so the mock is effective.
    import os
    import importlib.util
    import io

    if isinstance(os.symlink, unittest.mock.NonCallableMock):
        # os.symlink is mocked; run bootstrap in-process
        spec = importlib.util.spec_from_file_location("bootstrap", BOOTSTRAP)
        bootstrap_module = importlib.util.module_from_spec(spec)

        # Capture stdout/stderr
        old_argv = sys.argv
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        try:
            sys.argv = [
                "bootstrap.py",
                "--project-root", str(project_root),
                "--plugin-root", str(PLUGIN_ROOT),
                "--with", with_plugins
            ]
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            spec.loader.exec_module(bootstrap_module)
            returncode = bootstrap_module.main()
            stdout = sys.stdout.getvalue()
            stderr = sys.stderr.getvalue()
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        # Return a result object that mimics subprocess.CompletedProcess
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    else:
        # Normal subprocess execution
        return subprocess.run(
            [sys.executable, str(BOOTSTRAP),
             "--project-root", str(project_root),
             "--plugin-root", str(PLUGIN_ROOT),
             "--with", with_plugins],
            capture_output=True, text=True)


def load_settings(project_root):
    return json.loads((Path(project_root) / ".claude" / "settings.json").read_text())


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
            }))
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
        import os
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as tmp:
            # Simulate a platform where symlink creation is not permitted (e.g. Windows).
            with mock.patch.object(os, "symlink", side_effect=OSError("symlink not permitted")):
                r = run_bootstrap(tmp, "core")
            self.assertEqual(r.returncode, 0, r.stderr)
            agents = Path(tmp) / "AGENTS.md"
            claude = Path(tmp) / "CLAUDE.md"
            self.assertTrue(agents.is_file())          # exists as a real file
            self.assertFalse(agents.is_symlink())      # not a (broken) symlink
            self.assertEqual(agents.read_text(), claude.read_text())  # mirrors CLAUDE.md


if __name__ == "__main__":
    unittest.main()
