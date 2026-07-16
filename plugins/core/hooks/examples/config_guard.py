"""PreToolUse(Write|Edit) hook -> warn before weakening a guardrail config or hardcoding a secret.

Two authoring-time checks, both non-blocking (additionalContext nudge; never blocks the write):
  A. config-protection: the target path is a guardrail/security config (pre-commit, gitleaks,
     .mcp.json, .claude/settings.json) -> remind not to weaken secret/lint protections and never
     to paste real secrets into a tracked file (use the .example placeholder variant).
  B. secret-at-authoring: the content being written contains a high-confidence hardcoded secret
     (GitLab PAT, GitHub PAT, AWS key, or a `secret/token/password = "literal"` assignment that is
     not a placeholder/env-ref) -> flag it BEFORE a commit-time scanner (e.g. gitleaks) catches it.

Deliberately high-signal, low-false-positive: raw hex/base64 blobs are NOT flagged (many codebases
legitimately contain hashes/ids); bare internal hostnames are NOT flagged (docs reference them
constantly). The designated secret stores (.mcp.json / .env*) are exempt from the content scan -
that is where secrets legitimately live - but still get the path-protection reminder.
Rule source: the no-hardcoded-credentials convention (do not hardcode org/tenant ids, tokens, hosts).
This source stays pure ASCII. Only GENERIC secret shapes are matched - no real token is embedded here.

Test (run from this examples directory):
    printf '{"tool_name":"Write","tool_input":{"file_path":"x.py","content":"token = \\"glpat-abcdefghij1234567890\\""}}' | PYTHONPATH=. python3 -m config_guard
    printf '{"tool_name":"Edit","tool_input":{"file_path":".pre-commit-config.yaml","new_string":"  - id: gitleaks"}}' | PYTHONPATH=. python3 -m config_guard
    printf '{"tool_name":"Write","tool_input":{"file_path":"x.py","content":"token = os.environ[\\"GL_PAT\\"]"}}' | PYTHONPATH=. python3 -m config_guard   # no output
"""
from __future__ import annotations

import os
import re

from utils import emit_additional_context, in_project, read_payload, run, tool_input, written_text

# A. Guardrail-config paths (matched on basename, or substring for the pre-commit family).
_GUARDRAIL_BASENAMES = {
    ".pre-commit-config.yaml",
    ".gitleaks.toml",
    ".secrets.baseline",
    ".mcp.json",
    "settings.json",            # only under .claude/ (checked below)
}
_GUARDRAIL_SUBSTRINGS = ("pre-commit", "gitleaks")

# B. Content scanned only for the WRITE/EDIT text; the designated secret stores (.mcp.json / .env*)
# legitimately hold secrets -> skipped by _is_secret_store below.

# High-confidence secret signatures, GENERIC shapes only (low FP by construction).
_SIGNATURES = (
    ("GitLab PAT (glpat-...)", re.compile(r"glpat-[A-Za-z0-9_\-]{20,}")),
    ("GitHub PAT (ghp_...)", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("GitHub fine-grained PAT (github_pat_...)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key (AKIA...)", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)
_ASSIGN = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret)\b"
    r"\s*[:=]\s*"
    # group 2 = quoted value (>=8); group 3 = unquoted bareword (>=20, no space/quote/paren) so an env or
    # YAML/TOML hardcode like `token: glpatXXXX...` is caught, while `secret = func()` / short refs are not.
    r"""(?:['"]([^'"\s]{8,})['"]|([^\s'"#()]{20,}))"""
)
# A matched assignment value that looks like one of these is a placeholder/reference, not a real secret.
_PLACEHOLDER_HINT = re.compile(
    r"(?i)(redacted|example|changeme|placeholder|your[_-]|xxx+|dummy|sample|<[^>]*>|\$\{|os\.environ|getenv|vault|secretref)"
)


def _is_guardrail_config(file_path: str) -> bool:
    norm = file_path.replace("\\", "/")
    base = os.path.basename(norm)
    if base == "settings.json":
        return "/.claude/" in norm or norm.startswith(".claude/")
    if base in _GUARDRAIL_BASENAMES:
        return True
    return any(s in base for s in _GUARDRAIL_SUBSTRINGS)


def _is_secret_store(file_path: str) -> bool:
    # Exact secret-store files only - a loose startswith would wrongly exempt e.g. `.env-notes.md`
    # or `.mcp.json.bak` from the content scan.
    base = os.path.basename(file_path)
    return base == ".mcp.json" or base == ".env" or base.startswith(".env.")


def _scan_secrets(text: str):
    """label -> up to 5 sample line numbers for each high-confidence secret class found."""
    found = {}

    def add(label, lineno):
        lns = found.setdefault(label, [])
        if len(lns) < 5 and lineno not in lns:
            lns.append(lineno)

    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pattern in _SIGNATURES:
            if pattern.search(line):
                add(label, lineno)
        m = _ASSIGN.search(line)
        if m:
            # Judge only the matched VALUE, not the whole line - a co-occurring word like `# sample`
            # must not cancel a real hardcoded secret.
            val = m.group(2) or m.group(3) or ""
            if not _PLACEHOLDER_HINT.search(val):
                add("hardcoded %s literal" % m.group(1).lower(), lineno)
    return found


def main() -> None:
    payload = read_payload()
    t = tool_input(payload)
    tool_name = payload.get("tool_name", "")
    file_path = str(t.get("file_path") or "")
    if not file_path or not in_project(file_path):
        return

    parts = []
    if _is_guardrail_config(file_path):
        parts.append(
            "editing a guardrail config (%s) - do NOT weaken pre-commit/gitleaks/lint protections, "
            "and never commit a real secret here; put placeholders in the tracked file and real values "
            "in the gitignored/.example variant" % os.path.basename(file_path)
        )

    if not _is_secret_store(file_path):
        for label, lns in _scan_secrets(written_text(tool_name, t)).items():
            parts.append("%s at line(s) %s" % (label, ",".join(map(str, lns))))

    if not parts:
        return
    emit_additional_context(
        "PreToolUse",
        "Security guard (no-hardcoded-credentials convention): "
        + "; ".join(parts)
        + ". Use an env var / secret manager / .mcp.json reference, never a hardcoded org-id/tenant-id/token/host. "
        "A secret that reaches a commit must be rotated. Line numbers are relative to the text being written.",
    )


if __name__ == "__main__":
    run(main)
