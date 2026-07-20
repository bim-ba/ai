"""PostToolUse(Write|Edit) hook -> flag file-artifact convention violations in just-written content.

Scans the content this op introduced (Write.content / Edit.new_string) for:
  - banned hard-unicode punctuation (em/en dash, horizontal-bar, minus-sign, almost-equal, section-sign, ellipsis, smart quotes, non-breaking space);
  - arrows and decorative emoji;
  - (Write to prose files .md/.mdx/.rst/.txt only) likely hard line-wraps (a manual mid-sentence newline); skipped for Edit fragments, which lack code-fence context.
Cyrillic and guillemets are allowed text and are never flagged. Skips files outside the project tree (transient /tmp scratch, git commit-message files). Emits a non-blocking PostToolUse nudge; it never blocks the write.
Rule source: the file-artifact convention "ASCII only (-> not arrows, - not em/en-dash, no section sign)" + "no hard line-wrapping in file artifacts".
This source stays pure ASCII: every banned char is referenced by its codepoint via chr(0x....), never as a literal glyph, so the hook never trips its own rule.

Test (run from this examples directory):
    printf '{"tool_name":"Write","tool_input":{"file_path":"x.md","content":"a \\u2014 b\\nrun \\u2192 now\\nok."}}' | PYTHONPATH=. python3 -m artifact_guard
    printf '{"tool_name":"Write","tool_input":{"file_path":"x.md","content":"Cyrillic and guillemets are fine."}}' | PYTHONPATH=. python3 -m artifact_guard   # no output
"""
from __future__ import annotations

from utils import emit_additional_context, in_project, read_payload, run, tool_input, written_text

# Banned punctuation: codepoint -> replacement hint. NOT a blanket non-ASCII ban -
# Cyrillic and guillemets (0x00AB/0x00BB) are allowed text and are deliberately absent.
BANNED = {
    chr(0x2014): "em-dash -> -",
    chr(0x2013): "en-dash -> -",
    chr(0x2015): "horizontal-bar -> -",
    chr(0x2212): "minus-sign -> -",
    chr(0x2248): "almost-equal -> ~",
    chr(0x00A7): "section-sign -> the word",
    chr(0x2026): "ellipsis -> ...",
    chr(0x2018): "smart-quote -> '",
    chr(0x2019): "smart-quote -> '",
    chr(0x201C): "smart-quote -> dquote",
    chr(0x201D): "smart-quote -> dquote",
    chr(0x00A0): "non-breaking-space -> space",
}
ARROW_RANGES = ((0x2190, 0x21FF),)
EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),  # symbols, pictographs, emoji
    (0x2600, 0x27BF),    # misc symbols + dingbats (checkmark, warning, ...)
    (0x2B00, 0x2BFF),    # misc symbols and arrows
    (0x2300, 0x23FF),    # misc technical (alarm clock, hourglass)
    (0xFE0F, 0xFE0F),    # variation selector-16
    (0x20E3, 0x20E3),    # combining keycap
)

PROSE_EXTS = (".md", ".mdx", ".rst", ".txt")
# Mid-sentence wrap is only flagged for plain prose lines (not lists/tables/headings/quotes/fences).
_STRUCT_PREFIXES = ("-", "*", "+", "#", ">", "|", "`", "~")
TERMINATORS = set(".!?:;)" + chr(0x00BB) + "\"'`|*]>")


def _in_ranges(ch: str, ranges) -> bool:
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in ranges)


def _scan_unicode(text: str):
    """label -> up to 5 sample line numbers, for each banned / arrow / emoji char class found."""
    found = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        for ch in line:
            label = BANNED.get(ch)
            if label is None and _in_ranges(ch, ARROW_RANGES):
                label = "arrow -> ->"
            if label is None and _in_ranges(ch, EMOJI_RANGES):
                label = "emoji (drop in files)"
            if label:
                lns = found.setdefault(label, [])
                if len(lns) < 5 and lineno not in lns:
                    lns.append(lineno)
    return found


def _is_struct(line: str) -> bool:
    """True for a markdown structural line (list/table/heading/quote/fence) - not plain prose."""
    s = line.lstrip()
    if not s:
        return True
    if s[0] in _STRUCT_PREFIXES:
        return True
    head = s.split(" ", 1)[0]
    return head[:-1].isdigit() and head[-1:] in (".", ")")  # ordered list "1." / "1)"


def _frontmatter_end(lines) -> int:
    """Index of the first line AFTER a leading YAML frontmatter block (`---` ... `---`), else 0.

    Frontmatter is a sequence of `key: value` lines, which the hard-wrap heuristic would otherwise read
    as run-on prose (a value with no terminator followed by a lowercase next key). Skip it entirely.
    """
    if not lines or lines[0].strip() != "---":
        return 0
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            return j + 1
    return 0


def _scan_hardwrap(text: str):
    """1-indexed line numbers of likely manual mid-sentence wraps in prose, outside code fences."""
    lines = text.splitlines()
    fenced = False
    hits = []
    for i in range(_frontmatter_end(lines), len(lines) - 1):
        s = lines[i].strip()
        if s.startswith("```") or s.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced or not s:
            continue
        if len(lines[i]) - len(lines[i].lstrip(" ")) >= 4:
            continue  # indented code/tree block, not flowing prose
        nxt = lines[i + 1].strip()
        if not nxt or not nxt[0].islower():
            continue
        if _is_struct(lines[i]) or _is_struct(lines[i + 1]):
            continue
        if s[-1] not in TERMINATORS:
            hits.append(i + 1)
            if len(hits) >= 5:
                break
    return hits


def main() -> None:
    payload = read_payload()
    if payload is None:
        return  # unreadable input: stay out of the way
    t = tool_input(payload)
    tool_name = payload.get("tool_name", "")
    file_path = str(t.get("file_path") or "")
    if file_path and not in_project(file_path):
        return
    content = written_text(tool_name, t)
    if not content:
        return
    parts = []
    for label, lns in _scan_unicode(content).items():
        parts.append("%s at line(s) %s" % (label, ",".join(map(str, lns))))
    # Hard-wrap is a whole-document property (needs code-fence context), so judge it only on
    # Write (full file). An Edit new_string is a fragment whose fence state is unknown -> skip.
    if tool_name == "Write" and file_path.lower().endswith(PROSE_EXTS):
        wrap = _scan_hardwrap(content)
        if wrap:
            parts.append("possible hard line-wrap (manual mid-sentence newline) at line(s) %s - verify" % ",".join(map(str, wrap)))
    if not parts:
        return
    emit_additional_context(
        "PostToolUse",
        "File-artifact lint (ASCII + no-hard-wrap convention): "
        + "; ".join(parts)
        + ". Fix with an Edit; keep Cyrillic text and guillemets. Line numbers are relative to the text just written.",
    )


if __name__ == "__main__":
    run(main)
