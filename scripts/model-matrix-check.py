# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Advisory free-model JSON-schema matrix probe.

NOTE: This primarily exercises OpenRouter and the selected models' structured-output
capability, not this repo's own logic. It is a cross-model capability/health smoke
aligned with the project's cross-agent ethos — advisory signal only, never a gate.

Self-healing: the free-model list is fetched live from OpenRouter and filtered, so it
cannot rot to a delisted model id (the failure mode that left a dead model in the old
smoke). Pure functions (select/validate) are unit-tested offline in tests/.
"""
import json
import os
import sys
import urllib.error
import urllib.request

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# A JSON-Schema subset used BOTH as the API response_format and for local validation.
PROBE_SCHEMA = {
    "type": "object",
    "required": ["project", "skills", "agent_targets"],
    "properties": {
        "project": {"type": "string"},
        "skills": {"type": "array"},
        "agent_targets": {"type": "array"},
    },
    "additionalProperties": False,
}

PROBE_PROMPT = (
    "Reply ONLY with JSON matching the schema. "
    "project: the string 'ai'. "
    "skills: a list of 2-3 example skill names. "
    "agent_targets: the list of AI agents this project targets."
)

_TYPE_MAP = {
    "object": dict,
    "string": str,
    "array": list,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


def select_free_structured_models(payload, n=4):
    """Return up to n model ids that are currently free and support structured outputs.

    free := pricing.prompt == 0 and pricing.completion == 0
    structured := 'structured_outputs' in supported_parameters
    Deterministic: sorted by id.
    """
    out = []
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        try:
            free = (float(pricing.get("prompt", 1)) == 0.0
                    and float(pricing.get("completion", 1)) == 0.0)
        except (TypeError, ValueError):
            free = False
        sp = m.get("supported_parameters") or []
        if free and "structured_outputs" in sp and m.get("id"):
            out.append(m["id"])
    out.sort()
    return out[:n]


def validate_against_schema(obj, schema):
    """Minimal JSON-Schema-subset validator. Returns a list of error strings ([] == valid).

    Supports top-level type, required keys, and per-property primitive types
    (object/string/array/number/integer/boolean). No nested validation beyond type.
    """
    errors = []
    top = schema.get("type")
    if top and not isinstance(obj, _TYPE_MAP.get(top, object)):
        errors.append(f"root: expected {top}, got {type(obj).__name__}")
        return errors
    if top == "object":
        for key in schema.get("required", []):
            if key not in obj:
                errors.append(f"missing required key: {key}")
        for key, spec in (schema.get("properties") or {}).items():
            if key in obj:
                want = spec.get("type")
                if want and not isinstance(obj[key], _TYPE_MAP.get(want, object)):
                    errors.append(f"{key}: expected {want}, got {type(obj[key]).__name__}")
    return errors


def _http_json(url, api_key=None, data=None, timeout=60):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url, data=body, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def probe_model(model_id, api_key, prompt=PROBE_PROMPT, schema=PROBE_SCHEMA):
    """Call one model with a strict json_schema response_format; return (ok, detail)."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "probe", "strict": True, "schema": schema},
        },
    }
    try:
        resp = _http_json(f"{OPENROUTER_BASE}/chat/completions",
                          api_key=api_key, data=payload, timeout=60)
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"request failed: {e}"
    try:
        content = resp["choices"][0]["message"]["content"]
        obj = json.loads(content)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        return False, f"unparseable response: {e}"
    errs = validate_against_schema(obj, schema)
    return (not errs), ("; ".join(errs) if errs else "valid")


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set — skipping model matrix (advisory).")
        return 0
    try:
        models = _http_json(f"{OPENROUTER_BASE}/models", timeout=30)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"could not fetch model list: {e}", file=sys.stderr)
        return 1  # total/internal failure; job is continue-on-error regardless
    selected = select_free_structured_models(models, n=4)
    if not selected:
        print("no free structured-output models currently available — advisory skip.")
        return 0
    print(f"Probing {len(selected)} free structured-output models:\n")
    print("| model | result |")
    print("|-------|--------|")
    for mid in selected:
        ok, detail = probe_model(mid, api_key)
        print(f"| `{mid}` | {'✓' if ok else '✗'} {detail} |")
    return 0  # advisory: per-model failures never fail the build


if __name__ == "__main__":
    sys.exit(main())
