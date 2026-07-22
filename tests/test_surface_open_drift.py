# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Behavior gate for the SessionStart open-drift surfacer.

The hook exists because a rule telling the agent to "read open/" is the manual fix that already
failed three consecutive sessions on this repo; the structural fix is making the entries appear
in context on their own. So every case here asserts on the hook's actual stdout -- that it EMITS
the entries when they exist and stays SILENT when they do not -- because a surfacer that silently
emits nothing is the exact failure mode it was written to end.

Load-bearing against specific mutations:
  - drop the `if not entries: return` backstop    -> test_silent_when_open_empty goes RED
    (this backstop, not `is_dir()`, is what catches an empty open/; the `is_dir()` guard is a
    redundant early-out, since glob on a missing dir already yields no entries)
  - resolve project only from cwd, not payload    -> test_reads_project_from_payload_cwd RED
  - drop the payload `cwd` precedence over env     -> test_reads_project_from_payload_cwd RED
  - stop sorting by priority                       -> test_orders_high_priority_first (may) RED
  - remove the MAX_ENTRIES cap                     -> test_caps_the_list_and_stays_under_limit RED

The project directory is resolved from the payload `cwd` first, so each case passes an explicit
`cwd` and the silent cases run in a scratch tree with none of this repo's own open entries -- a
naive fallback to the process cwd would otherwise let the runner's own project leak into stdout.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "plugins" / "core" / "hooks" / "surface_open_drift.py"


def invoke(stdin_text, cwd=None, project_dir_env=None):
    """Run the hook with raw stdin; return stripped stdout. Asserts exit 0.

    Runs in a scratch cwd and with CLAUDE_PROJECT_DIR stripped unless a test sets one, so the
    resolver's fallbacks cannot pick up the test runner's own project.
    """
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir_env is not None:
        env["CLAUDE_PROJECT_DIR"] = project_dir_env
    done = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd or tempfile.gettempdir(),
        env=env,
    )
    assert done.returncode == 0, "a hook must always exit 0, got " + str(done.returncode)
    return done.stdout.strip()


def make_project(tmp, entries):
    """Create <tmp>/.claude/drift-log/open with one .md per (name, priority, diverged) triple."""
    open_dir = Path(tmp) / ".claude" / "drift-log" / "open"
    open_dir.mkdir(parents=True)
    for name, priority, diverged in entries:
        body = "---\ndate: 2026-01-01\npriority: {p}\n---\n\n## What diverged\n\n{d}\n".format(
            p=priority, d=diverged
        )
        (open_dir / name).write_text(body, encoding="utf-8")
    return str(tmp)


def context_of(stdout_text):
    return json.loads(stdout_text)["hookSpecificOutput"]["additionalContext"]


class SurfaceOpenDrift(unittest.TestCase):
    def test_emits_the_entries_via_the_non_error_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, [("2026-01-01-alpha.md", "HIGH", "alpha diverged here")])
            parsed = json.loads(invoke(json.dumps({"cwd": root})))
            self.assertNotIn("decision", parsed)  # a nudge is not an error banner
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "SessionStart")
            context = parsed["hookSpecificOutput"]["additionalContext"]
            self.assertIn("2026-01-01-alpha.md", context)
            self.assertIn("alpha diverged here", context)
            self.assertIn("reviewing-drift-logs", context)

    def test_silent_when_open_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".claude" / "drift-log" / "open").mkdir(parents=True)
            self.assertEqual(invoke(json.dumps({"cwd": tmp})), "")

    def test_silent_when_no_drift_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(invoke(json.dumps({"cwd": tmp})), "")

    def test_silent_on_unreadable_input(self):
        for raw in ("not json", "", "[1, 2]", "null", "17"):
            with self.subTest(stdin=raw):
                self.assertEqual(invoke(raw), "")

    def test_reads_project_from_payload_cwd_over_env(self):
        """Payload cwd wins; the env var is the fallback only."""
        with tempfile.TemporaryDirectory() as has, tempfile.TemporaryDirectory() as empty:
            root = make_project(has, [("2026-01-01-x.md", "MEDIUM", "x")])
            # cwd points at the populated project, env at an empty one -> cwd must win
            self.assertIn("2026-01-01-x.md", context_of(invoke(json.dumps({"cwd": root}),
                                                               project_dir_env=empty)))
            # no cwd in payload -> env fallback resolves the populated project
            self.assertIn("2026-01-01-x.md", context_of(invoke(json.dumps({}),
                                                               project_dir_env=root)))

    def test_orders_high_priority_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, [
                ("2026-01-01-low.md", "LOW", "low"),
                ("2026-01-01-high.md", "HIGH", "high"),
                ("2026-01-01-med.md", "MEDIUM", "med"),
            ])
            context = context_of(invoke(json.dumps({"cwd": root})))
            self.assertLess(context.index("2026-01-01-high.md"), context.index("2026-01-01-med.md"))
            self.assertLess(context.index("2026-01-01-med.md"), context.index("2026-01-01-low.md"))

    def test_caps_the_list_and_stays_under_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [("2026-01-%02d-e.md" % i, "MEDIUM", "d" * 300) for i in range(1, 26)]
            root = make_project(tmp, entries)
            context = context_of(invoke(json.dumps({"cwd": root})))
            self.assertLess(len(context), 10000, "additionalContext must stay under the 10k cap")
            self.assertIn("more in open/", context)  # the cap must announce what it dropped

    def test_wired_into_hooks_json_by_path(self):
        manifest = json.loads((REPO / "plugins/core/hooks/hooks.json").read_text())
        commands = [h["command"] for h in manifest["hooks"]["SessionStart"][0]["hooks"]]
        surfacer = [c for c in commands if "surface_open_drift.py" in c]
        self.assertEqual(len(surfacer), 1, "surfacer must be wired exactly once on SessionStart")
        self.assertIn("--no-project", surfacer[0])  # never install packages mid-session
        self.assertNotIn("echo ", surfacer[0])

    def test_manifest_command_runs_end_to_end(self):
        """Substring checks cannot see a dead hook -- execute the wired command string."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(tmp, [("2026-01-01-e2e.md", "HIGH", "end to end")])
            manifest = json.loads((REPO / "plugins/core/hooks/hooks.json").read_text())
            command = next(h["command"] for h in manifest["hooks"]["SessionStart"][0]["hooks"]
                           if "surface_open_drift.py" in h["command"])
            command = command.replace("${CLAUDE_PLUGIN_ROOT}", str(REPO / "plugins" / "core"))
            done = subprocess.run(
                command, shell=True, input=json.dumps({"cwd": root}),
                capture_output=True, text=True, timeout=120, cwd=tempfile.gettempdir(),
            )
            self.assertEqual(done.returncode, 0, "manifest command failed: " + done.stderr[:400])
            emitted = json.loads(done.stdout)["hookSpecificOutput"]
            self.assertEqual(emitted["hookEventName"], "SessionStart")
            self.assertIn("2026-01-01-e2e.md", emitted["additionalContext"])


if __name__ == "__main__":
    unittest.main()
