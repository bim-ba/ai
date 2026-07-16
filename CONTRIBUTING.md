# Contributing

Thanks for your interest in `ai`.

## Workflow

- Work on a feature branch; open a PR into `main` (the published trunk).
- `uv` is the only prerequisite for the Claude side — no `jq`/`yq`/`npx`. Extracted
  scripts are stdlib-only with a PEP-723 header.
- New skills follow `plugins/core/templates/skills-authoring-standard.md`.
- Specs and plans live under `docs/superpowers/`.

## Tests

```
uv run --no-project python -m unittest discover -s tests -t tests -p "test_*.py" -v
```
