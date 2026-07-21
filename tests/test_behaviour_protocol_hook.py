# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Behavior gate for the SessionStart hook that injects the agent behaviour protocol.

This hook had NO coverage at all until the inline `python -c` one-liner in `hooks.json` was
extracted into a module. That is worse than a vacuous assertion: the hook carries every baseline
rule the session runs under, so a silent failure removes all of them and nothing - not CI, not the
agent, not the user - can tell. The same repo already shipped a hook that was a no-op for 24 days.

Every case asserts on the hook's actual stdout. The cases are chosen to be load-bearing against
specific mutations:
  - emit only part of the file (a truncating read)   -> test_emits_the_protocol_byte_for_byte RED
  - swallow a read error into an empty emit          -> test_read_failure_emits_a_loud_warning RED
  - wrong `hookEventName`                            -> test_emits_the_documented_channel RED
  - resolve the .md from cwd instead of __file__     -> test_works_from_an_unrelated_cwd RED
  - regress the manifest back to inline `python -c`  -> test_wired_by_path_not_inline_logic RED

`test_the_byte_for_byte_assertion_is_not_vacuous` is the falsifiability run the authoring standard
requires: it re-runs the content assertion against a deliberately truncated copy of the protocol and
fails if that copy PASSES. Without it, "the emitted text equals the file" is satisfied by any hook
that reads the same file, including one that reads it wrongly in both places.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO / "plugins" / "core" / "hooks"
HOOK = HOOKS_DIR / "behaviour_protocol.py"
PROTOCOL = HOOKS_DIR / "behaviour-protocol.md"
MANIFEST = HOOKS_DIR / "hooks.json"


def invoke(hook_path=HOOK, cwd=None):
    """Run the hook on an empty payload and return its parsed stdout. Asserts exit 0."""
    done = subprocess.run(
        [sys.executable, str(hook_path)],
        input="{}",
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd) if cwd else None,
    )
    assert done.returncode == 0, "a hook must always exit 0, got " + str(done.returncode)
    return json.loads(done.stdout)


def emitted_context(hook_path=HOOK, cwd=None):
    return invoke(hook_path, cwd)["hookSpecificOutput"]["additionalContext"]


class BehaviourProtocolHookTests(unittest.TestCase):
    def test_emits_the_documented_channel(self):
        """`hookEventName` must be SessionStart or the harness drops the context on the floor."""
        out = invoke()
        self.assertIn("hookSpecificOutput", out)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_emits_the_protocol_byte_for_byte(self):
        """Equality, not `assertIn`: a substring check passes on a truncated read."""
        self.assertEqual(emitted_context(), PROTOCOL.read_text(encoding="utf-8"))

    def test_emitted_context_is_substantial(self):
        """Guards the degenerate pass where BOTH the file and the emit are empty."""
        self.assertGreater(len(emitted_context()), 1000)

    def test_works_from_an_unrelated_cwd(self):
        """The hook resolves its source via __file__; hooks.json passes no argument and no cwd."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                emitted_context(cwd=tmp), PROTOCOL.read_text(encoding="utf-8")
            )

    def test_read_failure_emits_a_loud_warning_not_silence(self):
        """The whole point of the deviation from rule 5: losing the protocol must be VISIBLE.

        A copy of the hook with no protocol beside it stands in for an unreadable source.
        """
        with tempfile.TemporaryDirectory() as tmp:
            orphan = Path(tmp) / "behaviour_protocol.py"
            shutil.copy(HOOK, orphan)
            context = emitted_context(hook_path=orphan)
        self.assertIn("WARNING", context)
        self.assertIn("WITHOUT its baseline conventions", context)

    def test_the_byte_for_byte_assertion_is_not_vacuous(self):
        """Falsifiability run: the content check must FAIL on a truncated protocol.

        The standard's own rule - a green run on the current state proves only that the check does
        not false-positive. Here the defect is manufactured: same hook, deliberately short source.
        """
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp)
            shutil.copy(HOOK, sandbox / "behaviour_protocol.py")
            (sandbox / "behaviour-protocol.md").write_text("truncated", encoding="utf-8")
            context = emitted_context(hook_path=sandbox / "behaviour_protocol.py")
        self.assertEqual(context, "truncated")
        self.assertNotEqual(
            context,
            PROTOCOL.read_text(encoding="utf-8"),
            "the content assertion is vacuous: a truncated protocol compared equal",
        )

    def test_wired_by_path_not_inline_logic(self):
        """The manifest points at the module; regressing to `python -c` is what this replaced."""
        command = json.loads(MANIFEST.read_text(encoding="utf-8"))["hooks"]["SessionStart"][0][
            "hooks"
        ][0]["command"]
        self.assertIn("behaviour_protocol.py", command)
        self.assertNotIn("python -c", command)
        self.assertNotIn("json.dumps", command)

    def test_protocol_is_ascii(self):
        """Rule 6 of the authoring standard - hook output is injected as plain text."""
        text = PROTOCOL.read_text(encoding="utf-8")
        offenders = sorted({ch for ch in text if ord(ch) > 126})
        self.assertEqual(
            offenders, [], "non-ASCII in injected hook text: " + repr(offenders)
        )


if __name__ == "__main__":
    unittest.main()
