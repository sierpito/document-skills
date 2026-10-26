#!/usr/bin/env python3
"""Part of improve-skills. Check that an improvement plan has the agreed shape, so every iteration is comparable.

A plan is a Markdown file that starts with `# Improvement ... iteration N of M`, says `**Items: K**`, and has one table
whose rows are `| # | Item | Verdict |`. K must equal the number of rows; every verdict starts with `apply` or `skip`, and a
skip carries a reason after a colon (`skip: needs a machine with LibreOffice`). N must not exceed M, and M must be 5 or less.
The table must be aligned like an editor's reformat (md_tables.py --fix).

Usage: plan_check.py PLAN.md [--json]
Exit code: 0 plan is well formed, 1 problems found, 2 bad input.
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
try:
    import mdtable
except ModuleNotFoundError:
    mdtable = None


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def check(text):
    problems = []
    head = re.search(r"^# .*?iteration (\d+) of (\d+)", text, re.M | re.I)
    if not head:
        problems.append("first heading must contain 'iteration N of M'")
        n = m = 0
    else:
        n, m = int(head.group(1)), int(head.group(2))
        if m > 5:
            problems.append(f"M is {m}: a loop runs at most 5 iterations")
        if n > m:
            problems.append(f"iteration {n} is beyond the limit {m}")
    items = re.search(r"\*\*Items:\s*(\d+)\*\*", text)
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.strip().startswith("|") and len(cells) == 3 and re.fullmatch(r"\d+", cells[0]):
            rows.append(cells)
    if not items:
        problems.append("missing '**Items: K**'")
    elif int(items.group(1)) != len(rows):
        problems.append(f"says {items.group(1)} items but the table has {len(rows)} rows")
    applied = skipped = 0
    for num, item, verdict in rows:
        v = verdict.lower()
        if v.startswith("apply"):
            applied += 1
        elif v.startswith("skip"):
            skipped += 1
            if not re.match(r"skip\s*:\s*\S", v):
                problems.append(f"item {num}: a skip needs a reason ('skip: ...')")
        else:
            problems.append(f"item {num}: verdict must start with apply or skip")
        if len(item) < 20:
            problems.append(f"item {num}: describe the finding and the evidence, not just a title")
    if mdtable and not mdtable.is_formatted(text):
        problems.append("tables are not aligned: run md_tables.py --fix on the plan")
    nums = [int(r[0]) for r in rows]
    if nums != list(range(1, len(nums) + 1)):
        problems.append("item numbers must run 1..K in order")
    return {"iteration": n, "limit": m, "items": len(rows), "applied": applied, "skipped": skipped, "problems": problems}


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"):
        die(__doc__)
    path = Path(a[0])
    r = check(path.read_text(encoding="utf8"))
    if "--json" in a:
        print(json.dumps(r, indent=2))
    else:
        for p in r["problems"]:
            print("PROBLEM:", p)
        print(f"iteration {r['iteration']} of {r['limit']}: {r['items']} items, {r['applied']} apply, {r['skipped']} skip, "
              f"{len(r['problems'])} problem(s)")
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as e:
        die(f"error: {e.strerror}: {e.filename}")
