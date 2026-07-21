# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Behavior gate for the CI version-bump check.

Every case builds a throwaway git repository in which the answer is known, then runs
`version_bump_check.py` as a SUBPROCESS - the same interface `.github/workflows/ci.yml` uses -
and asserts on its exit code and its output. Asserting on the exit code is the point: the thing
being prevented is a check that runs and decides nothing.

Per `behaviour-protocol.md`, a check is not validated by a green run on the current state, so
the defect is genuinely present in the fixtures below (content edited, version left alone), and
in the two real commits named in the script's docstring (`b5805bc`, `56d1814`), which were
validated by hand against this repo's own history.

The cases are load-bearing against specific mutations of the check:
  - exclude nothing from `plugins/**`     -> test_only_touching_version_manifests_passes RED
  - compare with `!=` instead of `>`      -> test_a_backward_version_is_still_a_failure RED
  - degrade an unknown git context to 0   -> the three `cannot_decide` tests RED
  - report the verdict only on stdout     -> test_a_failure_explains_itself_on_stderr RED
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECK = HERE / "version_bump_check.py"

BASE_VERSION = "0.1.0"


def git(repo, *args):
    """Run git in `repo` with identity + signing pinned, so the fixture works on any machine."""
    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, "fixture git failed: git " + " ".join(args) + "\n" + done.stderr
    return done.stdout.strip()


def write(repo, rel, text):
    target = Path(repo) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def marketplace(version):
    return json.dumps({"name": "ai", "version": version, "plugins": []}, indent=2) + "\n"


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message, "--allow-empty")
    return git(repo, "rev-parse", "HEAD")


def seed(repo):
    """A repo shaped like this one at its base commit. Returns the base sha."""
    git(repo, "init", "-q")
    write(repo, ".claude-plugin/marketplace.json", marketplace(BASE_VERSION))
    write(repo, "plugins/core/.claude-plugin/plugin.json", json.dumps({"version": BASE_VERSION}))
    write(repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\noriginal body\n")
    write(repo, "README.md", "# fixture\n")
    write(repo, "tests/test_demo.py", "# a test\n")
    return commit(repo, "base")


def run_check(repo, base, head="HEAD"):
    return subprocess.run(
        [sys.executable, str(CHECK), "--repo", str(repo), "--base", base, "--head", head],
        capture_output=True,
        text=True,
        timeout=120,
    )


class VersionBumpCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.base = seed(self.repo)

    def tearDown(self):
        self._tmp.cleanup()

    def test_plugin_content_without_a_bump_fails(self):
        """The defect itself: this is the shape of `b5805bc` and `56d1814`."""
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\nedited body\n")
        commit(self.repo, "edit a skill, touch no version")
        done = run_check(self.repo, self.base)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("plugins/core/skills/demo/SKILL.md", done.stderr)

    def test_plugin_content_with_a_bump_passes(self):
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\nedited body\n")
        write(self.repo, ".claude-plugin/marketplace.json", marketplace("0.1.1"))
        write(self.repo, "plugins/core/.claude-plugin/plugin.json", json.dumps({"version": "0.1.1"}))
        commit(self.repo, "edit a skill and bump")
        done = run_check(self.repo, self.base)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("0.1.0 -> 0.1.1", done.stdout)

    def test_only_touching_version_manifests_passes(self):
        """A release-only PR ships no content, so it has nothing to gate.

        The per-plugin `plugin.json` files are the version manifests, not shipped content;
        counting them as content would make every release commit fail itself.
        """
        write(self.repo, "plugins/core/.claude-plugin/plugin.json", json.dumps({"version": "0.1.1"}))
        commit(self.repo, "align the plugin manifest, no content")
        done = run_check(self.repo, self.base)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("0 changed file(s)", done.stdout)

    def test_touching_nothing_under_plugins_passes(self):
        """Docs / tests / CI changes ship through git, not through the plugin cache."""
        write(self.repo, "README.md", "# fixture\n\nmore prose\n")
        write(self.repo, "tests/test_demo.py", "# a better test\n")
        write(self.repo, ".github/workflows/ci.yml", "name: CI\n")
        commit(self.repo, "docs, tests and CI only")
        done = run_check(self.repo, self.base)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("no shipped plugin content changed", done.stdout)

    def test_a_backward_version_is_still_a_failure(self):
        """0.1.0 -> 0.0.9 "changed" the version into a cache directory that already exists."""
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\nedited body\n")
        write(self.repo, ".claude-plugin/marketplace.json", marketplace("0.0.9"))
        commit(self.repo, "edit a skill and move the version backward")
        done = run_check(self.repo, self.base)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_a_deleted_plugin_file_counts_as_content(self):
        """Removing a shipped file changes what users get exactly as much as editing one."""
        (self.repo / "plugins/core/skills/demo/SKILL.md").unlink()
        commit(self.repo, "delete a skill, touch no version")
        self.assertEqual(run_check(self.repo, self.base).returncode, 1)

    def test_reads_the_merge_base_not_the_base_tip(self):
        """A PR is judged on ITS diff, not on whatever main did meanwhile.

        Fixture: main moves ahead with an unrelated plugin edit + bump; the PR branch, forked
        before that, edits content without bumping. Diffing base TIP against head would show the
        version going 0.2.0 -> 0.1.0 and the main-side files as changes; the merge base is the
        only reference that isolates the PR.
        """
        fork = self.base
        write(self.repo, "plugins/core/skills/demo/other.md", "main moved on\n")
        write(self.repo, ".claude-plugin/marketplace.json", marketplace("0.2.0"))
        main_tip = commit(self.repo, "main advances and bumps")
        git(self.repo, "checkout", "-q", "-b", "pr", fork)
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\npr body\n")
        commit(self.repo, "pr edits content, no bump")
        done = run_check(self.repo, main_tip)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertNotIn("other.md", done.stderr)

    def test_judges_a_merge_commit_head_the_way_github_checks_it_out(self):
        """`actions/checkout` gives a pull_request job the refs/pull/N/merge commit, not the
        branch tip. Judged from the base tip, that merge commit must still carry the verdict."""
        fork = self.base
        git(self.repo, "checkout", "-q", "-b", "pr", fork)
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\npr body\n")
        commit(self.repo, "pr edits content, no bump")
        git(self.repo, "checkout", "-q", "main")
        write(self.repo, "README.md", "# fixture\n\nmain moved\n")
        main_tip = commit(self.repo, "main advances")
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge pr", "pr")
        done = run_check(self.repo, main_tip)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_a_failure_explains_itself_on_stderr(self):
        """A red job whose log does not name the file or the fix gets ignored or re-run."""
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\nedited body\n")
        commit(self.repo, "edit a skill")
        done = run_check(self.repo, self.base)
        self.assertEqual(done.returncode, 1)
        self.assertIn("ships NOWHERE", done.stderr)
        self.assertIn("marketplace.json", done.stderr)

    def test_a_pass_is_never_silent(self):
        """A green check that prints nothing is indistinguishable from one that never ran."""
        commit(self.repo, "empty")
        done = run_check(self.repo, self.base)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(done.stdout.strip(), "a passing check must say what it decided")


class CannotDecideIsLoud(unittest.TestCase):
    """Exit 2, never 0. A no-op on an unknown git context is the silent-death failure mode."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def assert_cannot_decide(self, done):
        self.assertEqual(done.returncode, 2, "stdout=" + done.stdout + " stderr=" + done.stderr)
        self.assertIn("CANNOT DECIDE", done.stderr)
        self.assertEqual(done.stdout.strip(), "")

    def test_unresolvable_base_ref_cannot_decide(self):
        """The default-fetch-depth case: `origin/main` simply is not there to diff against."""
        seed(self.repo)
        self.assert_cannot_decide(run_check(self.repo, "origin/main"))

    def test_no_common_ancestor_cannot_decide(self):
        """A shallow / grafted checkout: both refs resolve, `merge-base` still finds nothing."""
        seed(self.repo)
        git(self.repo, "checkout", "-q", "--orphan", "unrelated")
        write(self.repo, "README.md", "# unrelated root\n")
        stranger = commit(self.repo, "unrelated root")
        git(self.repo, "checkout", "-q", "main")
        self.assert_cannot_decide(run_check(self.repo, stranger))

    def test_not_a_git_repository_cannot_decide(self):
        self.assert_cannot_decide(run_check(self.repo, "HEAD~1"))

    def test_unparseable_manifest_cannot_decide(self):
        """A malformed manifest must not be read as "the version did not move"."""
        base = seed(self.repo)
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\nedited\n")
        write(self.repo, ".claude-plugin/marketplace.json", "{ not json")
        commit(self.repo, "break the manifest")
        self.assert_cannot_decide(run_check(self.repo, base))

    def test_missing_manifest_cannot_decide(self):
        base = seed(self.repo)
        (self.repo / ".claude-plugin/marketplace.json").unlink()
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\nedited\n")
        commit(self.repo, "remove the manifest")
        self.assert_cannot_decide(run_check(self.repo, base))

    def test_non_numeric_version_cannot_decide(self):
        """`>` on dotted integers is only defined for dotted integers; guessing is not allowed."""
        base = seed(self.repo)
        write(self.repo, "plugins/core/skills/demo/SKILL.md", "# demo\n\nedited\n")
        write(self.repo, ".claude-plugin/marketplace.json", marketplace("0.2.0-rc1"))
        commit(self.repo, "prerelease version")
        self.assert_cannot_decide(run_check(self.repo, base))


class WiredIntoCI(unittest.TestCase):
    def test_the_workflow_invokes_the_check_on_pull_request_with_full_history(self):
        """The three properties that make the check real, asserted where they are declared.

        A check nobody calls, called on a depth-1 checkout, or called on `push` where the merge
        base is HEAD itself, is a check that decides nothing. Substring assertions on YAML are
        weak, but the alternative - running Actions - is not available in this suite; the
        behavioral half is covered by every case above.
        """
        workflow = (HERE.parent / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests/version_bump_check.py", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("github.event_name == 'pull_request'", workflow)


if __name__ == "__main__":
    unittest.main()
