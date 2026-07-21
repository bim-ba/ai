# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""CI check: a PR that changes shipped plugin CONTENT must move the marketplace version.

Binds to:  the `version-bump` job in `.github/workflows/ci.yml`, on `pull_request` only.
Decides:   whether the diff from the merge base to HEAD touches `plugins/**` - excluding the
           per-plugin version manifests themselves - while the `version` in
           `.claude-plugin/marketplace.json` stands still. If it does, the PR fails.
Why:       an installed plugin's cache is keyed by version
           (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`), so content merged
           without a bump ships nowhere: it sits on `main` looking merged while every
           installation keeps serving the old copy. `b5805bc` and `56d1814` each edited plugin
           content, each left the version alone, and each passed CI green; `f24be8d` is the
           cleanup release that finally shipped them. `CONTRIBUTING.md` states the rule; until
           now nothing enforced it.

Why the existing suite cannot catch this:
    `tests/test_drift_log_check.py::test_every_shipped_plugin_version_matches_the_marketplace`
    compares the three declared version numbers to EACH OTHER, so three agreeing STALE numbers
    pass it green. That test is about PARITY between manifests; this check is about MOVEMENT
    across a diff, and neither implies the other. So this file reads only `marketplace.json`
    and leaves parity where it already works.

Exit codes:
    0  no shipped content changed, or the version moved forward - the PR is shippable
    1  shipped content changed and the version did not move forward - the defect
    2  the git context needed for a verdict is unavailable - LOUD, never a pass

Never skips (this inverts hook rule 5 on purpose):
    A plugin HOOK swallows its errors and exits 0, because a broken hook must not block a
    session. A CI check is the opposite instrument: one that no-ops when it cannot find a merge
    base is exactly the silent-death failure this repo already shipped once - the `echo`-based
    Stop hook that was a no-op for 24 days (see `plugins/core/hooks/drift_log_check.py`). So
    every unknown here exits 2 with the reason on stderr: an unresolvable base ref, a shallow
    clone with no common ancestor, a missing or unparseable manifest at either end, no `git` on
    PATH. Deciding WHEN the check runs is the workflow's `if:` condition, visible in the run
    graph - never this script's silent shrug.

Strict about direction, not just movement:
    The written rule is "the version changed", but the only correct change is UPWARD. A version
    that moves backward lands content in a cache directory an earlier release already created,
    which is the same ship-nowhere failure wearing a different hat. The comparison is therefore
    `>`, not `!=`, and a version that will not parse as dotted integers is exit 2 rather than a
    guess.

Kill-criterion:
    Delete this file the day the plugin loader stops keying its cache by version - a content
    hash, or a `main`-tracking install mode - because the failure it guards then cannot happen
    and the check is pure friction. Also delete it if the release flow moves to a bot that bumps
    the version on merge, which makes the human omission unreachable. Not: "it fires too often"
    - every firing so far has been a real defect.

Test:
    uv run --no-project python tests/version_bump_check.py --base <base-sha> --head <head-sha>
    # -> exit 1 for --base c29f7a0 --head b5805bc (plugin content, no bump)
    # -> exit 0 for --base 24beba5 --head 9296ec4 (plugin content, 0.2.2 -> 0.2.3)
    # The detector is exercised against synthetic repos where the defect IS genuinely present:
    # tests/test_version_bump_check.py
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

MARKETPLACE = ".claude-plugin/marketplace.json"
PLUGIN_DIR = "plugins"


class Undecidable(Exception):
    """The git context needed for a verdict is unavailable. Always exit 2, never a pass."""


def git(repo, *args):
    """Run a git command in `repo` and return stdout. Any failure becomes `Undecidable`."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo)] + list(args), capture_output=True, text=True, check=False
        )
    except OSError as exc:  # git absent from PATH
        raise Undecidable("cannot run git: " + str(exc)) from exc
    if done.returncode != 0:
        detail = done.stderr.strip() or done.stdout.strip() or "no output"
        raise Undecidable("`git " + " ".join(args) + "` failed: " + detail)
    return done.stdout


def is_version_manifest(path):
    """True for `plugins/<name>/.claude-plugin/plugin.json` and nothing else.

    Example: 'plugins/core/.claude-plugin/plugin.json' -> True;
             'plugins/core/hooks/drift_log_check.py'   -> False.
    """
    parts = path.split("/")
    return (
        len(parts) == 4
        and parts[0] == PLUGIN_DIR
        and parts[2] == ".claude-plugin"
        and parts[3] == "plugin.json"
    )


def is_shipped_content(path):
    """True for a path whose change reaches users only through a version bump."""
    return path.split("/")[0] == PLUGIN_DIR and not is_version_manifest(path)


def changed_paths(repo, base, head):
    """Every path differing between two revisions, renames split into old + new."""
    out = git(repo, "diff", "--name-only", "--no-renames", base, head)
    return [line for line in out.splitlines() if line.strip()]


def declared_version(repo, rev):
    """The marketplace `version` string as of `rev`."""
    raw = git(repo, "show", rev + ":" + MARKETPLACE)
    try:
        value = json.loads(raw)["version"]
    except (ValueError, KeyError, TypeError) as exc:
        raise Undecidable(
            "cannot read a version from " + MARKETPLACE + " at " + rev + ": " + str(exc)
        ) from exc
    return value


def as_ordinal(version, where):
    """'0.2.10' -> (0, 2, 10), so 0.2.10 sorts above 0.2.9. Anything else is Undecidable."""
    parts = str(version).split(".")
    if not parts or not all(part.isdigit() for part in parts):
        raise Undecidable("version " + repr(version) + " at " + where + " is not dotted integers")
    return tuple(int(part) for part in parts)


def decide(repo, base_ref, head_ref):
    """Return (exit_code, report_lines). Raises Undecidable rather than guessing."""
    head = git(repo, "rev-parse", "--verify", head_ref).strip()
    base = git(repo, "merge-base", base_ref, head).strip()
    content = sorted(path for path in changed_paths(repo, base, head) if is_shipped_content(path))
    before = declared_version(repo, base)
    after = declared_version(repo, head)
    moved = as_ordinal(after, head) > as_ordinal(before, "the merge base")

    context = [
        "merge base : " + base,
        "head       : " + head,
        "version    : " + str(before) + " -> " + str(after),
        "content    : " + str(len(content)) + " changed file(s) under " + PLUGIN_DIR + "/",
    ]
    if not content:
        return 0, context + ["OK: no shipped plugin content changed, no bump required."]
    if moved:
        return 0, context + ["OK: plugin content changed and the version moved forward."]
    return 1, context + [
        "FAIL: plugin content changed but the version did not move forward.",
        "An installed plugin's cache is keyed by version, so this content ships NOWHERE.",
        "Bump all three in the same PR: " + MARKETPLACE + ", plugins/core/.claude-plugin/",
        "plugin.json, plugins/data/.claude-plugin/plugin.json (they must agree).",
        "Changed content:",
    ] + ["  " + path for path in content]


def main(argv=None):
    """Print the verdict and return the exit code. A pass goes to stdout, a failure to stderr."""
    parser = argparse.ArgumentParser(
        description="Fail a PR that ships plugin content without a version bump."
    )
    parser.add_argument(
        "--base", default="origin/main", help="base ref of the PR (default: origin/main)"
    )
    parser.add_argument("--head", default="HEAD", help="head ref of the PR (default: HEAD)")
    parser.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parents[1]),
        help="repository to inspect (default: the repo this script lives in)",
    )
    args = parser.parse_args(argv)
    code, lines = decide(args.repo, args.base, args.head)
    stream = sys.stdout if code == 0 else sys.stderr
    for line in lines:
        print("version-bump check: " + line, file=stream)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Undecidable as exc:
        print("version-bump check: CANNOT DECIDE - " + str(exc), file=sys.stderr)
        print(
            "version-bump check: failing on purpose. A check that skips when it cannot see the "
            "git context is how a guard dies silently; fix the checkout (fetch-depth: 0) or the "
            "refs, do not ignore this.",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as exc:  # keep exit 1 meaning exactly one thing: the defect
        print(
            "version-bump check: CANNOT DECIDE - unexpected "
            + type(exc).__name__
            + ": "
            + str(exc),
            file=sys.stderr,
        )
        sys.exit(2)
