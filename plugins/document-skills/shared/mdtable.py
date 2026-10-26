"""Markdown table formatting shared by the scripts. Standard library only.

A table is formatted the way an editor's "reformat" does it: every column padded to its widest cell, one space of padding
either side, and a separator row whose dashes fill the column (`|---|-----|`, with `:` kept for alignment markers).
Cell width is display width, so wide (CJK) characters count twice and combining marks zero. Tables inside fenced code
blocks are left alone; a row with more cells than the header makes its table untouchable (reported, not guessed).
"""
import re
import unicodedata

SEPARATOR = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$")


def width(s):
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def split_row(line):
    """Cells of a table row; a pipe escaped as \\| stays inside its cell."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", body)]


def format_table(rows, aligns=None, indent=""):
    """Lines of an aligned table. rows[0] is the header; `aligns` holds 'l', 'r', 'c' or None per column."""
    cols = len(rows[0])
    rows = [r + [""] * (cols - len(r)) for r in rows]
    aligns = list(aligns or []) + [None] * (cols - len(aligns or []))
    ws = [max(1, max(width(r[i]) for r in rows)) for i in range(cols)]

    def line(r):
        out = []
        for i, c in enumerate(r):
            pad = ws[i] - width(c)
            out.append(" " + (" " * pad + c if aligns[i] == "r" else c + " " * pad if aligns[i] != "c" else
                              " " * (pad // 2) + c + " " * (pad - pad // 2)) + " ")
        return indent + "|" + "|".join(out) + "|"

    def sep():
        cells = []
        for i in range(cols):
            n = ws[i] + 2
            a = aligns[i]
            cells.append(":" + "-" * (n - 2) + ":" if a == "c" else ":" + "-" * (n - 1) if a == "l" and False else
                         "-" * (n - 1) + ":" if a == "r" else "-" * n)
        return indent + "|" + "|".join(cells) + "|"
    return [line(rows[0]), sep()] + [line(r) for r in rows[1:]]


def _aligns(sep_line):
    out = []
    for c in split_row(sep_line):
        out.append("c" if c.startswith(":") and c.endswith(":") else "r" if c.endswith(":") else "l" if c.startswith(":") else None)
    return out


def format_text(text):
    """Return (new_text, tables_formatted, tables_skipped). Idempotent."""
    lines = text.split("\n")
    out, i, fenced = [], 0, None
    done = skipped = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"\s*(```+|~~~+)", ln)
        if m:
            fenced = None if fenced and m.group(1).startswith(fenced[0]) else (fenced or m.group(1))
            out.append(ln)
            i += 1
            continue
        if fenced or "|" not in ln or i + 1 >= len(lines) or not SEPARATOR.match(lines[i + 1]):
            out.append(ln)
            i += 1
            continue
        j = i + 2
        while j < len(lines) and "|" in lines[j] and lines[j].strip():
            j += 1
        block = lines[i:j]
        rows = [split_row(block[0])] + [split_row(r) for r in block[2:]]
        header_cols = len(rows[0])
        if any(len(r) > header_cols for r in rows) or len(split_row(block[1])) != header_cols:
            skipped += 1
            out.extend(block)
        else:
            indent = re.match(r"\s*", block[0]).group(0)
            out.extend(format_table(rows, _aligns(block[1]), indent))
            done += 1
        i = j
    return "\n".join(out), done, skipped


def is_formatted(text):
    new, _, _ = format_text(text)
    return new == text
