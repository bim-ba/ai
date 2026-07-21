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
PLUGIN_ROOT = REPO / "plugins" / "core"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
HOOK = HOOKS_DIR / "behaviour_protocol.py"
PROTOCOL = HOOKS_DIR / "behaviour-protocol.md"
MANIFEST = HOOKS_DIR / "hooks.json"


def manifest_command():
    """The SessionStart command string exactly as the harness would run it."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["hooks"]["SessionStart"][0]["hooks"][0][
        "command"
    ]


def load_tests(loader, tests, ignore):
    """Run the module's doctests too - otherwise the `Test:` example rots unexecuted."""
    import doctest
    import importlib.util

    spec = importlib.util.spec_from_file_location("behaviour_protocol", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests.addTests(doctest.DocTestSuite(module))
    return tests


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

    def test_emitted_context_fits_the_additionalContext_cap(self):
        """`additionalContext` is capped at 10,000 chars (hooks-authoring-standard.md section 6).

        Over the cap the harness TRUNCATES, and `test_emits_the_protocol_byte_for_byte` keeps
        passing - it compares stdout to the file, not to what the model receives. So growth past the
        ceiling has to fail here or it lands as silently missing rules. Headroom is deliberate: the
        red test must arrive while there is still room to edit, not at the cliff.
        """
        self.assertLess(len(emitted_context()), 9000)

    def test_empty_protocol_is_a_failure_not_an_empty_protocol(self):
        """A zero-byte source must WARN, not emit "".

        `read_text` succeeds on an empty file, so without an explicit check a truncated cache write
        emits nothing and says nothing - the exact silence this hook is designed to prevent.
        """
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp)
            shutil.copy(HOOK, sandbox / "behaviour_protocol.py")
            (sandbox / "behaviour-protocol.md").write_text("   \n\n", encoding="utf-8")
            context = emitted_context(hook_path=sandbox / "behaviour_protocol.py")
        self.assertIn("WARNING", context)
        self.assertNotEqual(context.strip(), "")

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
        command = manifest_command()
        self.assertIn("behaviour_protocol.py", command)
        self.assertNotIn("python -c", command)
        self.assertNotIn("json.dumps", command)
        # rule 3 names this explicitly: `uv run` WITHOUT `--no-project` resolves the surrounding
        # project's environment and can install packages mid-session.
        self.assertIn("--no-project", command)

    def test_the_manifest_command_actually_runs(self):
        """Execute the manifest's own command string. Substring checks cannot see a dead hook.

        This is the assertion that would have caught the 24-day no-op, and it is the only test here
        that exercises the real launcher (`uv run`), the real `${CLAUDE_PLUGIN_ROOT}` expansion and
        the real path. Without it a manifest of `true # behaviour_protocol.py` passes every other
        test in this file while injecting nothing, forever.
        """
        done = subprocess.run(
            manifest_command(),
            shell=True,
            input="{}",
            capture_output=True,
            text=True,
            timeout=120,
            cwd=tempfile.gettempdir(),  # the harness does not run hooks from the plugin directory
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)},
        )
        self.assertEqual(done.returncode, 0, "manifest command failed: " + done.stderr[:400])
        payload = json.loads(done.stdout)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertEqual(
            payload["hookSpecificOutput"]["additionalContext"],
            PROTOCOL.read_text(encoding="utf-8"),
        )

    def test_a_read_error_that_is_not_a_missing_file_still_warns(self):
        """Kills the plausible narrowing `except Exception` -> `except FileNotFoundError`.

        Every other failure test removes the file, so a narrowed except passes them all. An
        unreadable-but-present file is the case that separates them.
        """
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp)
            shutil.copy(HOOK, sandbox / "behaviour_protocol.py")
            blocked = sandbox / "behaviour-protocol.md"
            blocked.write_text("x" * 2000, encoding="utf-8")
            blocked.chmod(0o000)
            try:
                blocked.read_text(encoding="utf-8")
                self.skipTest("this user can read a 0o000 file (root?); the mutation is untestable")
            except PermissionError:
                pass
            context = emitted_context(hook_path=sandbox / "behaviour_protocol.py")
            blocked.chmod(0o600)
        self.assertIn("WARNING", context)

    def test_resolves_through_a_symlinked_module(self):
        """Kills dropping `.resolve()`.

        Symlinking the DIRECTORY is not the discriminating case - `with_name` alone still lands on
        the protocol through the link. The case that separates them is a symlink to the MODULE from
        a directory that has no protocol beside it: without `.resolve()`, `__file__` is the link and
        the lookup happens in the wrong directory.
        """
        with tempfile.TemporaryDirectory() as tmp:
            real, elsewhere = Path(tmp) / "real", Path(tmp) / "elsewhere"
            real.mkdir()
            elsewhere.mkdir()
            shutil.copy(HOOK, real / "behaviour_protocol.py")
            shutil.copy(PROTOCOL, real / "behaviour-protocol.md")
            (elsewhere / "behaviour_protocol.py").symlink_to(real / "behaviour_protocol.py")
            self.assertEqual(
                emitted_context(hook_path=elsewhere / "behaviour_protocol.py"),
                PROTOCOL.read_text(encoding="utf-8"),
            )

    def test_the_error_swallowing_wrapper_is_present(self):
        """Structural check - rule 5's last-resort guard has no reachable failing path to test."""
        source = HOOK.read_text(encoding="utf-8")
        self.assertIn("except Exception:", source)
        self.assertIn("pass", source)

    def test_the_verification_gate_keeps_its_cited_name(self):
        """A rule's title is a citation anchor, so renaming it is a breaking change.

        `Plan-Act-Reflect verification gate` is cited in this repo's plans, in x5's `CLAUDE.md`, and
        in ~12 dated drift-log and audit entries that must not be rewritten - so a rename orphans
        every one of them, each still readable and none resolvable. Splitting the bullet nearly did
        exactly that, because the surviving title describes only the first of the three parts and
        that mismatch reads like an invitation to rename. This assertion is the guard; a comment in
        the protocol itself would be injected into every session and cost tokens forever.
        """
        self.assertIn(
            "**Plan-Act-Reflect verification gate.**", PROTOCOL.read_text(encoding="utf-8")
        )

    def test_protocol_is_ascii(self):
        """Rule 6 of the authoring standard - hook output is injected as plain text."""
        text = PROTOCOL.read_text(encoding="utf-8")
        offenders = sorted({ch for ch in text if ord(ch) > 126})
        self.assertEqual(
            offenders, [], "non-ASCII in injected hook text: " + repr(offenders)
        )


if __name__ == "__main__":
    unittest.main()
