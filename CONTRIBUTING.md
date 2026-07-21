# Contributing

Thanks for your interest in `ai`.

## Workflow

- Work on a feature branch; open a PR into `main` (the published trunk).
- **Any change under `plugins/` bumps the version — in the same PR as the content.**
  An installed plugin's cache is keyed by version (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`),
  so content merged without a bump ships nowhere: it sits on `main` looking merged while every
  installation keeps serving the old copy. Bump all three in step —
  `.claude-plugin/marketplace.json`, `plugins/core/.claude-plugin/plugin.json`,
  `plugins/data/.claude-plugin/plugin.json` — since `tests/test_drift_log_check.py`
  asserts they agree. Note what that test does NOT catch: it compares the three numbers to each
  other, not to whether the content moved, so three agreeing stale numbers pass green. `b5805bc`
  and `56d1814` both edited plugin content, both left the version alone, and both passed CI;
  `f24be8d` is the cleanup release that shipped them. Reviewers: a PR touching `plugins/` with no
  version change is incomplete, whatever CI says.
- `uv` is the only prerequisite for the Claude side — no `jq`/`yq`/`npx`. Extracted
  scripts are stdlib-only with a PEP-723 header.
- New skills follow `plugins/core/templates/skills-authoring-standard.md`.
- Specs and plans live under `docs/superpowers/`.

## Tests

```
uv run --no-project python -m unittest discover -s tests -t tests -p "test_*.py" -v
```
