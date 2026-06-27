# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Advisory opencode-backed skill-load matrix.

For each of the top free models (by OpenRouter weekly popularity) this runs
`opencode run --model <model>` so the model *genuinely loads* this repo's skills
through opencode, then asks the agent to list its loaded skills and validates that
every skill this repo ships is present (opencode built-ins like `customize-opencode`
are allowed extras).

Why opencode rather than a raw API call: a raw chat model has no access to the repo,
so it cannot truly "load" anything. Running through opencode is the faithful test of
what a model actually picks up when it backs the agent. (MCP servers and hooks are
intentionally not checked — the plugin doesn't load MCP in CI, and hooks are runtime
callbacks the model never sees.)

Pure functions (ground truth, model selection, ANSI strip, JSON-array extraction,
validation, summary formatting) are unit-tested offline; the opencode subprocess
calls are not.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models?order=top-weekly"
DEFAULT_N = 4
PROMPT = (
    "List the names of the skills available to you in this project. "
    'Reply with ONLY a JSON array of the bare skill names, e.g. ["alpha","beta"]. '
    "No prose, no code fences."
)
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def repo_skill_names(repo_root):
    """Ground truth: the set of skill directory names this repo ships.

    A skill is any directory under plugins/*/skills/ that contains a SKILL.md.
    """
    root = Path(repo_root)
    names = set()
    for skill_md in root.glob("plugins/*/skills/*/SKILL.md"):
        names.add(skill_md.parent.name)
    return names


def select_popular_free_chat_models(payload, n=DEFAULT_N):
    """Return up to n free *chat* model ids, preserving the payload's order.

    The payload is expected to be the `?order=top-weekly` response, already sorted
    server-side by popularity. We filter to models that are both:
      - free  (prompt and completion both priced at 0), and
      - chat-capable — `tools` in supported_parameters. Tool-calling is a reliable
        chat-model signal: it excludes classifiers/safety/embedding models, and it
        is what opencode needs to drive a model as an agent in the first place.
    """
    out = []
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        try:
            free = (float(pricing.get("prompt", 1)) == 0.0
                    and float(pricing.get("completion", 1)) == 0.0)
        except (TypeError, ValueError):
            free = False
        chat = "tools" in (m.get("supported_parameters") or [])
        if free and chat and m.get("id"):
            out.append(m["id"])
    return out[:n]


def strip_ansi(text):
    """Remove ANSI escape sequences (opencode colorizes its output)."""
    return _ANSI.sub("", text)


def extract_json_array(text):
    """Pull the first JSON array of strings out of arbitrary agent output.

    Tolerates surrounding prose, code fences, and trailing reminder lines. Returns
    a list of strings, or None if no parseable array is found.
    """
    t = strip_ansi(text).strip()
    try:
        v = json.loads(t)
        if isinstance(v, list):
            return [str(x) for x in v]
    except (ValueError, TypeError):
        pass
    start = t.find("[")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            if t[i] == "[":
                depth += 1
            elif t[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        v = json.loads(t[start:i + 1])
                        if isinstance(v, list):
                            return [str(x) for x in v]
                    except (ValueError, TypeError):
                        pass
                    break
        start = t.find("[", start + 1)
    return None


def validate_skills(reported, ground_truth):
    """Validate reported skill names against the repo ground truth.

    Pass iff every ground-truth skill is present (extras are allowed and reported
    separately). `reported` may be None when the agent produced no parseable array.
    """
    reported_set = set(reported or [])
    missing = sorted(ground_truth - reported_set)
    extra = sorted(reported_set - ground_truth)
    return {"ok": not missing and reported is not None, "missing": missing, "extra": extra}


def format_model_section(model_id, result, raw_output):
    """Render one model's detailed result as a Markdown block."""
    mark = "✅" if result["ok"] else "❌"
    lines = [f"### {mark} `{model_id}`", ""]
    if result["missing"]:
        lines.append(f"**Missing repo skills:** {', '.join(result['missing'])}")
    else:
        lines.append("All repo skills present.")
    if result["extra"]:
        lines.append(f"**Extra (built-ins / unexpected):** {', '.join(result['extra'])}")
    lines += [
        "",
        "<details><summary>parsed skills</summary>",
        "",
        "```json",
        json.dumps(result.get("reported"), indent=2, ensure_ascii=False),
        "```",
        "",
        "</details>",
        "",
        "<details><summary>raw agent output</summary>",
        "",
        "```",
        strip_ansi(raw_output).strip() or "(empty)",
        "```",
        "",
        "</details>",
        "",
    ]
    return "\n".join(lines)


def run_opencode(model_id, prompt=PROMPT, timeout=180):
    """Run a model through opencode in this repo; return (returncode, combined output)."""
    proc = subprocess.run(
        ["opencode", "run", "--model", f"openrouter/{model_id}", prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _http_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main():
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY not set — skipping skill-load matrix (advisory).")
        return 0
    repo_root = Path(__file__).resolve().parents[1]
    ground_truth = repo_skill_names(repo_root)
    if not ground_truth:
        print("could not resolve repo skills — advisory skip.", file=sys.stderr)
        return 1
    try:
        payload = _http_json(OPENROUTER_MODELS_URL)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"could not fetch model list: {e}", file=sys.stderr)
        return 1
    models = select_popular_free_chat_models(payload)
    if not models:
        print("no free chat models currently available — advisory skip.")
        return 0

    print(f"# opencode skill-load matrix\n")
    print(f"Ground truth — {len(ground_truth)} repo skills: "
          f"{', '.join(sorted(ground_truth))}\n")
    print(f"Probing {len(models)} free models (OpenRouter weekly-popularity order):\n")

    rows, sections = [], []
    for model_id in models:
        try:
            _, raw = run_opencode(model_id)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raw = f"opencode run failed: {e}"
        reported = extract_json_array(raw)
        result = validate_skills(reported, ground_truth)
        result["reported"] = reported
        mark = "✅" if result["ok"] else "❌"
        miss = "—" if not result["missing"] else f"{len(result['missing'])} missing"
        rows.append(f"| `{model_id}` | {mark} | {miss} |")
        sections.append(format_model_section(model_id, result, raw))

    print("| model | skills loaded | gaps |")
    print("|-------|---------------|------|")
    print("\n".join(rows))
    print("\n---\n")
    print("\n".join(sections))
    return 0  # advisory: per-model results never fail the build


if __name__ == "__main__":
    sys.exit(main())
