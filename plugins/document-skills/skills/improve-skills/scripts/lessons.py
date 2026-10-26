#!/usr/bin/env python3
"""Part of improve-skills. Keep lessons and standing decisions in one Markdown file: list, add (no duplicates), check.

Standard library only; the file is plain Markdown you can edit by hand. Default location is chosen by the caller
(for example docs/improve-skills-lessons.md in the repository being improved).

  lessons.py list FILE
  lessons.py add FILE --kind lesson|decision --text "..." --evidence "..." [--area AREA]
  lessons.py check FILE
Exit code: 0 ok, 1 check found problems or the entry already exists, 2 bad input.
"""
import re, sys
from datetime import date
from pathlib import Path

HEAD = "# Lessons and standing decisions (improve-skills)\n\n## Standing decisions\n\n## Lessons\n"
SECTION = {"decision": "## Standing decisions", "lesson": "## Lessons"}


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def load(path):
    return path.read_text(encoding="utf8") if path.is_file() else HEAD


def entries(text):
    out = []
    for m in re.finditer(r"^- \*\*(.+?)\*\*(?: - evidence: (.*?))?(?: \(([^)]*)\))?$", text, re.M):
        out.append({"text": m.group(1), "evidence": m.group(2) or "", "meta": m.group(3) or ""})
    return out


def add(path, kind, text, evidence, area):
    body = load(path)
    if any(norm(e["text"]) == norm(text) for e in entries(body)):
        print("already recorded: " + text)
        return 1
    meta = ", ".join(x for x in (f"area: {area}" if area else "", date.today().isoformat()) if x)
    line = f"- **{text.strip()}** - evidence: {evidence.strip()} ({meta})"
    head = SECTION[kind]
    if head not in body:
        body = body.rstrip() + f"\n\n{head}\n"
    idx = body.index(head) + len(head)
    nxt = re.search(r"^## ", body[idx:], re.M)
    end = idx + nxt.start() if nxt else len(body)
    section = body[idx:end].rstrip("\n")
    body = body[:idx] + section + "\n" + line + "\n" + ("\n" + body[end:] if nxt else "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf8")
    print(f"added {kind}: {text}")
    return 0


def check(path):
    body = load(path)
    problems = []
    seen = {}
    for e in entries(body):
        if not e["evidence"].strip():
            problems.append("no evidence: " + e["text"][:60])
        k = norm(e["text"])
        if k in seen:
            problems.append("duplicate: " + e["text"][:60])
        seen[k] = 1
    for h in SECTION.values():
        if h not in body:
            problems.append("missing section " + h)
    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(entries(body))} entries, {len(problems)} problem(s)")
    return 1 if problems else 0


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("list", "add", "check"):
        die(__doc__)
    path = Path(a[1])
    opt = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else ""
    if a[0] == "list":
        print(load(path).rstrip())
        return 0
    if a[0] == "check":
        return check(path)
    kind, text, evidence = opt("--kind") or "lesson", opt("--text"), opt("--evidence")
    if kind not in SECTION or not text.strip() or not evidence.strip():
        die("add needs --text and --evidence (what happened that taught this), and --kind lesson|decision")
    return add(path, kind, text, evidence, opt("--area"))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as e:
        die(f"error: {e.strerror}: {e.filename}")
