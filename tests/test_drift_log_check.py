# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Behavior gate for the Stop drift-log hook, and for plugin-version parity.

The hook this covers replaced an `echo` that was a silent no-op for 24 days: it wrote to a
channel that never reaches the model on `Stop`. Every case here asserts on the hook's actual
stdout, never on the fact that it ran, so that failure mode cannot return unnoticed.

The cases are chosen to be load-bearing against specific mutations of the hook:
  - drop the `is not False` guard      -> test_silent_when_stop_hook_active_absent goes RED
  - drop the None check on the payload -> equivalent mutant (see test_unreadable_input...)
  - emit `decision: block` instead     -> test_uses_the_non_error_channel goes RED
  - drop the once-per-turn guard       -> test_silent_when_already_reminded goes RED
  - change the required wording        -> test_uses_the_non_error_channel goes RED

`test_version_parity_detects_drift` exists because this suite's predecessor asserted version
parity with a helper that silently compared every plugin under the same key, so it passed on a
repo where a version HAD drifted. Per `behaviour-protocol.md`, a check is not validated by a
green run on the current state: the detector is therefore exercised against a synthetic tree in
which the defect is genuinely present.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "plugins" / "core" / "hooks" / "drift_log_check.py"


def invoke(stdin_text):
    """Run the hook with raw stdin and return its stripped stdout. Asserts the exit code is 0."""
    done = subprocess.run(
        [sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True, timeout=30
    )
    assert done.returncode == 0, "a hook must always exit 0, got " + str(done.returncode)
    return done.stdout.strip()


def plugin_versions(root):
    """Map plugin directory name -> declared version, for every plugin under `root`.

    Keyed on the plugin's own directory (`plugins/<name>/.claude-plugin/plugin.json`), taken
    relative to `root`. An absolute-path index would key every plugin identically and collapse
    the map to one entry, which is exactly how the previous version of this check went blind.
    """
    versions = {}
    for path in sorted(Path(root).glob("plugins/*/.claude-plugin/plugin.json")):
        name = path.relative_to(root).parts[1]
        versions[name] = json.loads(path.read_text(encoding="utf-8"))["version"]
    return versions


class DriftLogCheck(unittest.TestCase):
    def test_uses_the_non_error_channel(self):
        """A standing convention is not an error, so it must not render as one to the user.

        `decision: block` surfaces its reason as an error banner; `additionalContext` reaches
        the model without one. Firing every turn through the blocking channel would mean an
        error banner per turn for nothing going wrong.
        """
        parsed = json.loads(invoke(json.dumps({"stop_hook_active": False})))
        self.assertNotIn("decision", parsed)
        specific = parsed["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "Stop")
        self.assertIn("drift-log delta: none", specific["additionalContext"])
        self.assertIn("creating-drift-logs", specific["additionalContext"])

    def test_silent_when_already_reminded(self):
        """Once per turn: a turn already reminded must not be reminded again."""
        self.assertEqual(invoke(json.dumps({"stop_hook_active": True})), "")

    def test_silent_when_stop_hook_active_absent(self):
        """A harness that does not report the flag gets a no-op, not a reminder every turn."""
        for payload in ({}, {"cwd": "/tmp"}, {"stop_hook_active": None}):
            with self.subTest(payload=payload):
                self.assertEqual(invoke(json.dumps(payload)), "")

    def test_unreadable_input_never_emits(self):
        """A hook that cannot read its input must not act on defaults.

        Note: removing the explicit None/type checks is an EQUIVALENT mutant - the mandatory
        catch-all wrapper turns the resulting AttributeError into the same silence, on stdout,
        stderr and exit code alike. The checks are intent, not behavior.
        """
        for raw in ("not json", "", "[1, 2]", "null", '"a string"', "17"):
            with self.subTest(stdin=raw):
                self.assertEqual(invoke(raw), "")

    def test_holds_no_state(self):
        """Repeated identical invocations must give identical answers.

        The first design kept a marker file, which made the answer depend on history - and since
        its own reminder tells the agent to write a file, it changed what it measured.
        Statelessness is the property that fix relies on, so it is asserted, not assumed.
        """
        payload = json.dumps({"stop_hook_active": False})
        self.assertEqual(len({invoke(payload) for _ in range(3)}), 1)

    def test_wired_into_hooks_json_by_path_not_inline_logic(self):
        """The authoring standard forbids inline logic in the manifest (its opening paragraph)."""
        manifest = json.loads((REPO / "plugins/core/hooks/hooks.json").read_text())
        command = manifest["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertIn("drift_log_check.py", command)
        self.assertNotIn("echo ", command)
        # rule 3 names this: `uv run` without `--no-project` can install packages mid-session.
        self.assertIn("--no-project", command)

    def test_the_stop_manifest_command_actually_runs(self):
        """Substring checks cannot see a dead hook.

        `assertNotIn("echo ")` guards only the exact regression that already happened here; a
        manifest of `true # drift_log_check.py` satisfies every substring assertion above while
        injecting nothing, which is the shape of the 24-day no-op this file exists to prevent.
        Executing the command string is what actually closes that hole.
        """
        manifest = json.loads((REPO / "plugins/core/hooks/hooks.json").read_text())
        command = manifest["hooks"]["Stop"][0]["hooks"][0]["command"]
        # Substitute here rather than leaving it to the shell: the HARNESS expands this placeholder
        # before invoking, so this is the faithful reproduction - and `cmd.exe` does not grok ${VAR}.
        command = command.replace("${CLAUDE_PLUGIN_ROOT}", str(REPO / "plugins" / "core"))
        done = subprocess.run(
            command,
            shell=True,
            input=json.dumps({"stop_hook_active": False}),
            capture_output=True,
            text=True,
            timeout=120,
            cwd=tempfile.gettempdir(),
        )
        self.assertEqual(done.returncode, 0, "manifest command failed: " + done.stderr[:400])
        emitted = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual(emitted["hookEventName"], "Stop")
        self.assertIn("drift-log verdict", emitted["additionalContext"])


class PluginVersionParity(unittest.TestCase):
    def test_version_parity_detects_drift(self):
        """Exercise the detector where the defect is present, not only where it is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, version in (("core", "0.9.0"), ("data", "0.1.0")):
                target = root / "plugins" / name / ".claude-plugin"
                target.mkdir(parents=True)
                (target / "plugin.json").write_text(json.dumps({"version": version}))
            found = plugin_versions(root)
            self.assertEqual(found, {"core": "0.9.0", "data": "0.1.0"})
            self.assertEqual(len(set(found.values())), 2, "drift must be visible, not collapsed")

    def test_every_shipped_plugin_version_matches_the_marketplace(self):
        """A plugin's cache is keyed by version, so an edited plugin whose version did not move
        ships nowhere. This is what left `data` at 0.1.0 while its skills were being edited."""
        versions = plugin_versions(REPO)
        self.assertGreaterEqual(len(versions), 2, "expected at least core and data")
        marketplace = json.loads((REPO / ".claude-plugin/marketplace.json").read_text())["version"]
        self.assertEqual(
            set(versions.values()), {marketplace}, "versions disagree: " + repr(versions)
        )


if __name__ == "__main__":
    unittest.main()
