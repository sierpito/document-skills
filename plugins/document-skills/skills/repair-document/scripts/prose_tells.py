#!/usr/bin/env python3
"""Part of repair-document. Weighted lexical scan of prose for stock phrasing, for the edit-density report.

Read-only, stdlib only. Idea and rule families adapted from the unslop-text scanner. It flags wording
worth editing; it does not say who or what wrote the text, and a clean result proves nothing.
Skips front matter, fenced code, backticks, quoted text and lines containing `repair-ignore`.
Usage: prose_tells.py FILE [--json] [--max N]      (.md .txt .rst .html)
Exit code: number of HIGH findings.
"""
import json, re, sys
from pathlib import Path

H, M, L = 3, 2, 1
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
try:
    import patterns  # shared rules and helpers
except ModuleNotFoundError:
    sys.exit("needs shared/patterns.py from the document-skills plugin root; run this script from the installed plugin")


def load_rules():
    """Edit-scanner rules from shared/patterns.json (rules limited to speaker notes are skipped)."""
    return [r for r in patterns.load_rules("edit") if not r.get("where")]


def first_match(r, line, is_first, is_last):
    """First regex match of rule `r` on `line`. Edge rules (chat residue) only count in the first / last
    sentence of a paragraph, so only the first / last line of a paragraph is considered for them."""
    edge = r.get("edge")
    if not edge:
        return r["rx"].search(line), line
    sents = patterns.sentences(line)
    picked = []
    if edge in ("first", "either") and is_first and sents:
        picked.append(sents[0])
    if edge in ("last", "either") and is_last and sents:
        picked.append(sents[-1])
    for s in picked:
        m = r["rx"].search(s)
        if m:
            return m, s
    return None, line


def prose_lines(text):
    """Yield (lineno, line, scan_line) with code/front matter skipped and quoted text blanked."""
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    fence = None
    for n in range(i, len(lines)):
        ln = lines[n]
        m = re.match(r"\s*(```|~~~)", ln)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence:
            continue
        yield n + 1, ln


def main():
    a = [x for x in sys.argv[1:]]
    if not a or a[0].startswith("-"):
        sys.exit(__doc__)
    path = Path(a[0])
    if path.suffix.lower() in (".docx", ".pptx", ".pdf", ".zip", ".xlsx", ".odt"):
        sys.exit(f"{path.suffix} is not a text file: use review-ai-content/scripts/scan_signs.py to scan it")
    mx = int(a[a.index("--max") + 1]) if "--max" in a else 5
    raw = path.read_text(encoding="utf8", errors="replace")
    if path.suffix.lower() in (".html", ".htm"):
        blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # keeps line numbers equal to the file's
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", blank, raw, flags=re.S | re.I)
        raw = re.sub(r"<[^>]+>", blank, raw, flags=re.S)
    words = len(re.findall(r"\w+", raw))
    rules = load_rules()
    findings = []
    lines = list(prose_lines(raw))
    for k, (n, ln) in enumerate(lines):
        if "repair-ignore" in ln or not ln.strip():
            continue
        prev_blank = k == 0 or not lines[k - 1][1].strip() or lines[k - 1][0] != n - 1
        next_blank = k == len(lines) - 1 or not lines[k + 1][1].strip() or lines[k + 1][0] != n + 1
        quote_line = ln.lstrip().startswith(">")
        scan = patterns.blank_quotes(ln)
        for r in rules:
            if quote_line and not r["always"]:
                continue
            m, target = first_match(r, ln if r["always"] else scan, prev_blank, next_blank)
            if m:
                findings.append({"rule": r["id"], "weight": r["weight"], "line": n, "fix": r["fix"],
                                 "match": re.sub(r"\s+", " ", target[max(0, m.start() - 25):m.end() + 25]).strip()})
    score = sum(f["weight"] for f in findings)
    high = sum(f["weight"] == H for f in findings)
    med = sum(f["weight"] == M for f in findings)
    dens = round(1000 * score / words, 1) if words else 0.0
    if score == 0:
        verdict = "no tells found"
    elif high == 0 and med == 0:
        verdict = "minor tells only"
    elif high >= 3 or score >= 15 or (words >= 300 and dens >= 10):
        verdict = "many tells, worth an edit pass"
    elif high >= 1 or (score >= 6 and not (words >= 600 and dens < 2.0)):
        verdict = "some tells"
    else:
        verdict = "minor tells only"
    out = {"file": str(path), "words": words, "findings": len(findings), "edit_score": score,
           "density_per_1000_words": dens, "verdict": verdict, "high": high, "medium": med,
           "by_rule": {}}
    for f in findings:
        out["by_rule"].setdefault(f["rule"], []).append(f)
    if "--json" in a:
        print(json.dumps({**out, "by_rule": {k: v for k, v in out["by_rule"].items()}}, indent=2, ensure_ascii=False))
    else:
        print(f"{path}: {words} words, {len(findings)} findings, edit score {score}, density {dens}/1000, verdict: {verdict}")
        for name, fs in sorted(out["by_rule"].items(), key=lambda kv: -kv[1][0]["weight"]):
            print(f"\n[{ {3:'HIGH',2:'MED',1:'LOW'}[fs[0]['weight']] }] {name} x{len(fs)}  fix: {fs[0]['fix']}")
            for f in fs[:mx]:
                print(f"  line {f['line']}: {f['match']}")
        print("\nStructural tells (rhythm, rule of three, recap, saying little) need a manual read. A clean scan proves nothing.")
    sys.exit(min(high, 125))


if __name__ == "__main__":
    patterns.guard(main)
