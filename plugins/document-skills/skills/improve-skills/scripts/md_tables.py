#!/usr/bin/env python3
"""Part of improve-skills. Check or fix the layout of Markdown tables so every column is aligned.

The standard (a lesson from the user's own editor): pad every cell to the widest cell in its column, one space either
side, and make the separator row as wide as the column: `| # | Item |` over `|---|------|`. An unpadded `|---|---|---|`
separator with ragged cells is wrong. Tables in fenced code blocks are left alone; a table with a row that has more
cells than its header is reported and not touched.

Usage: md_tables.py FILE_OR_FOLDER ... [--check | --fix]      (default: --check; folders are searched for *.md)
Exit code: 0 all tables aligned (or fixed), 1 --check found misaligned tables, 2 bad input.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
try:
    import mdtable
except ModuleNotFoundError:
    print("needs shared/mdtable.py from the document-skills plugin root; run this script from the installed plugin", file=sys.stderr)
    sys.exit(2)

SKIP = {".git", ".idea", "node_modules", "__pycache__", ".venv"}


def files(args):
    for a in args:
        p = Path(a)
        if p.is_dir():
            yield from sorted(f for f in p.rglob("*.md") if not SKIP & set(f.parts))
        elif p.is_file():
            yield p
        else:
            print(f"not found: {a}", file=sys.stderr)
            sys.exit(2)


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    fix = "--fix" in sys.argv
    if not a:
        print(__doc__, file=sys.stderr)
        return 2
    bad = changed = skipped_total = 0
    for f in files(a):
        text = f.read_text(encoding="utf8")
        new, done, skipped = mdtable.format_text(text)
        skipped_total += skipped
        if new != text:
            if fix:
                f.write_text(new, encoding="utf8")
                changed += 1
                print(f"fixed   {f}")
            else:
                bad += 1
                print(f"MISALIGNED  {f}")
    if skipped_total:
        print(f"{skipped_total} table(s) skipped (a row has more cells than its header)")
    print(f"{changed} file(s) fixed" if fix else f"{bad} file(s) with misaligned tables")
    return 0 if fix else (1 if bad else 0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
