"""Shared by review-ai-content/scripts/scan_signs.py and repair-document/scripts/prose_tells.py.

Loads shared/patterns.json and offers the small text helpers both scanners need, so the rules and the
quote/disclosure handling cannot drift apart. Standard library only.
"""
import json, re, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATTERNS = HERE / "patterns.json"

DISCLOSURE = re.compile(
    r"(ai[- ](generated|assisted)|generated (with|by) (ai|chatgpt|claude|gemini)|created with ai|"
    r"\bai\b[^.]{0,40}\b(was|were) used\b|\bused (ai|chatgpt|claude|gemini|copilot)\b)", re.I)
QUOTE = re.compile(r"[\"“][^\"”]{40,}[\"”]|[‘][^’]{40,}[’]")
STOPWORDS = frozenset("the and of to a in is that for it with as on was are be this by at from or an not have".split())
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def load_rules(use):
    """Rules whose `uses` contains `use` ('review' or 'edit'), each with a compiled `rx`."""
    rules = []
    for r in json.loads(PATTERNS.read_text(encoding="utf8"))["rules"]:
        if use in r["uses"]:
            rules.append({**r, "rx": re.compile(r["pattern"], re.I | re.M)})
    return rules


def sentences(text):
    return [s for s in SENT_SPLIT.split(text.strip()) if s]


def find(rule, text, first=True, last=True):
    """Matches of `rule` in `text`. A rule with edge=first/last/either only counts in the first / last
    sentence of the paragraph `text` (and only if that edge is allowed by `first` / `last`)."""
    edge = rule.get("edge")
    if not edge:
        return rule["rx"].findall(text)
    sents = sentences(text)
    if not sents:
        return []
    picked = []
    if edge in ("first", "either") and first:
        picked.append(sents[0])
    if edge in ("last", "either") and last:
        picked.append(sents[-1])
    out = []
    for s in picked:
        out += rule["rx"].findall(s)
    return out


def blank_quotes(s):
    """Blank backticked and double-quoted spans, keeping offsets."""
    s = re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), s)
    return re.sub(r"[\"“][^\"”]*[\"”]", lambda m: " " * len(m.group(0)), s)


def english_ratio(text):
    """Share of common English function words among words, or None when under 100 words."""
    toks = re.findall(r"[^\W\d_]+", text.lower())
    if len(toks) < 100:
        return None
    return sum(t in STOPWORDS for t in toks) / len(toks)


def looks_english(text, min_words=100):
    """True / False / None (too short to tell). Between 0.08 and 0.12 counts as uncertain: None."""
    r = english_ratio(text)
    if r is None or 0.08 <= r < 0.12:
        return None
    return r >= 0.12


MAX_TOTAL = 500 * 1024 * 1024   # uncompressed bytes in one archive
MAX_MEMBER = 200 * 1024 * 1024  # uncompressed bytes in one member


def open_zip(path):
    """Open a .docx/.pptx package, refusing unsafe member paths and zip bombs (oversized expansion)."""
    z = zipfile.ZipFile(path)
    total = 0
    for i in z.infolist():
        n = i.filename
        if n.startswith("/") or ".." in n.split("/"):
            sys.exit("refusing archive with unsafe member path: " + n)
        if i.file_size > MAX_MEMBER:
            sys.exit(f"refusing archive: member {n} expands to {i.file_size // (1024 * 1024)} MB (limit {MAX_MEMBER // (1024 * 1024)} MB)")
        total += i.file_size
    if total > MAX_TOTAL:
        sys.exit(f"refusing archive: expands to {total // (1024 * 1024)} MB (limit {MAX_TOTAL // (1024 * 1024)} MB)")
    return z


def guard(main):
    """Run main(); turn ordinary input mistakes into a one-line message and exit code 2 (no traceback)."""
    try:
        main()
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            sys.exit(2)
        raise
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError) as e:
        print(f"error: {e.strerror}: {e.filename}", file=sys.stderr)
        sys.exit(2)
    except zipfile.BadZipFile:
        print("error: not a valid zip package (.docx and .pptx files are zip archives)", file=sys.stderr)
        sys.exit(2)
    except UnicodeDecodeError as e:
        print(f"error: cannot decode text ({e.reason})", file=sys.stderr)
        sys.exit(2)
