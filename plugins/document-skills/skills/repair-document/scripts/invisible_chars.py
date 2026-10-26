#!/usr/bin/env python3
"""Part of repair-document. Finds and removes invisible Unicode artifacts and lookalike letters.

Local, stdlib only, no network. Default mode is inspect (read-only). `--clean --out PATH` writes a new
file and refuses to overwrite one; the input is never modified. Reads .txt .md .html .docx .pptx.
Usage: invisible_chars.py FILE [--clean --out PATH] [--keep-nbsp-like] [--json]
"""
import json, re, sys, unicodedata, zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
try:
    from patterns import DISCLOSURE  # noqa: E402
    import patterns
    import mdtable
except ModuleNotFoundError:
    sys.exit("needs shared/patterns.py from the document-skills plugin root; run this script from the installed plugin")

NOTES = []  # printed after the table: disclosure sentences that held invisible characters

ZW = {0x200B, 0x2060, 0xFEFF, 0x180E}          # zero-width space, word joiner, BOM, Mongolian vowel sep
JOINERS = {0x200C, 0x200D}                      # keep next to emoji or non-Latin script
SOFT = {0x00AD}
BIDI = {0x200E, 0x200F, 0x061C, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}
TAGS = set(range(0xE0000, 0xE0080))
VARSEL = set(range(0xFE00, 0xFE0E)) | set(range(0xE0100, 0xE01F0))  # FE0E/FE0F (text / emoji style) are kept
SPACES = {0x1680, *range(0x2000, 0x200B), 0x205F, 0x3000}         # become a plain space
KEEP_SPACES = {0x00A0, 0x202F}                                    # meaningful (units, French); report only
LATIN_LOOK = {  # Cyrillic/Greek lookalikes -> Latin, used only inside words that mix in Latin letters
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k", "м": "m", "т": "t", "і": "i", "ј": "j", "ѕ": "s",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "ο": "o", "ν": "v", "Α": "A", "Β": "B", "Ε": "E", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "Ζ": "Z",
}
CONF = {"zero-width": "confirmed", "tag character": "confirmed", "bidi control": "probable",
        "soft hyphen": "informational", "variation selector": "probable", "typographic space": "probable",
        "joiner (kept)": "informational", "homoglyph": "probable", "nbsp-like (kept)": "informational"}
WORD = re.compile(r"[^\W\d_]+", re.U)
EMOJI_OR_NONLATIN = re.compile(r"[֐-ࣿऀ-෿฀-໿぀-鿿\U0001F300-\U0001FAFF☀-➿]")


def has_rtl(s):
    return any(unicodedata.bidirectional(c) in ("R", "AL") for c in s)


def fix_text(s, counts):
    before = sum(counts.values())
    res = _fix_text(s, counts)
    if sum(counts.values()) != before and DISCLOSURE.search(s):
        NOTES.append("a sentence that discloses AI use contained invisible characters: " + re.sub(r"\s+", " ", s)[:90])
    return res


def _fix_text(s, counts):
    rtl = has_rtl(s)
    out = []
    for i, ch in enumerate(s):
        o = ord(ch)
        if o in ZW:
            counts["zero-width"] += 1; continue
        if o in TAGS:
            counts["tag character"] += 1; continue
        if o in SOFT:
            counts["soft hyphen"] += 1; continue
        if o in BIDI and not rtl:
            counts["bidi control"] += 1; continue
        if o in VARSEL:
            counts["variation selector"] += 1; continue
        if o in JOINERS:
            near = s[max(0, i - 1):i] + s[i + 1:i + 2]
            if EMOJI_OR_NONLATIN.search(near) or rtl:
                counts["joiner (kept)"] += 1; out.append(ch); continue
            counts["zero-width"] += 1; continue
        if o in SPACES:
            counts["typographic space"] += 1; out.append(" "); continue
        if o in KEEP_SPACES:
            counts["nbsp-like (kept)"] += 1
        out.append(ch)
    s = "".join(out)

    def deglyph(m):
        w = m.group(0)
        if any(c in LATIN_LOOK for c in w) and re.search(r"[A-Za-z]", w):
            counts["homoglyph"] += sum(c in LATIN_LOOK for c in w)
            return "".join(LATIN_LOOK.get(c, c) for c in w)
        return w
    return WORD.sub(deglyph, s)


def process(path, clean, out_path):
    counts = Counter()
    ext = path.suffix.lower()
    if ext in (".txt", ".md", ".markdown", ".html", ".htm"):
        raw = path.read_text(encoding="utf8", errors="replace")
        protected = re.compile(r"(```.*?```|`[^`\n]+`|https?://\S+|<(?:script|style)\b.*?</(?:script|style)>)", re.S)
        parts = protected.split(raw)
        html = path.suffix.lower() in (".html", ".htm")
        tag = re.compile(r"(<[^>]*>)")
        def fix_part(p):
            if not html:
                return fix_text(p, counts)
            return "".join(x if x.startswith("<") else fix_text(x, counts) for x in tag.split(p))  # never inside tags
        res = [p if i % 2 else fix_part(p) for i, p in enumerate(parts)]
        if clean:
            out_path.write_text("".join(res), encoding="utf8")
    elif ext in (".docx", ".pptx"):
        zin = patterns.open_zip(path)
        seg = re.compile(r"(<(?:w:t|a:t|dc:\w+|cp:\w+)(?:\s[^>]*)?>)([^<]*)(?=</)")
        tmp = out_path.with_name(out_path.name + ".tmp") if clean else None
        zout = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) if clean else None
        for info in zin.infolist():  # input order, so [Content_Types].xml stays first
            data = zin.read(info.filename)
            if info.filename.endswith((".xml", ".rels")) and re.match(r"(word|ppt|docProps)/", info.filename):
                x = data.decode("utf8", "replace")
                x2 = seg.sub(lambda m: m.group(1) + fix_text(m.group(2), counts), x)
                data = x2.encode("utf8")
            if clean:
                zout.writestr(info, data)
        if clean:
            zout.close()
            tmp.replace(out_path)
    else:
        sys.exit("unsupported file type: " + ext)
    if counts.get("nbsp-like (kept)"):
        counts["nbsp-like (kept)"] = 1  # "present", not one row per occurrence
    return counts


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"):
        sys.exit(__doc__)
    path = Path(a[0])
    clean = "--clean" in a
    out_path = Path(a[a.index("--out") + 1]) if "--out" in a else None
    if clean:
        if out_path is None:
            sys.exit("--clean needs --out PATH")
        if out_path.exists():
            sys.exit("exists, not overwriting: " + str(out_path))
        if out_path.resolve() == path.resolve():
            sys.exit("--out must differ from the input")
    counts = process(path, clean, out_path)
    rows = [{"class": k, "count": v, "confidence": CONF[k]} for k, v in counts.items() if v]
    if "--json" in a:
        print(json.dumps({"file": str(path), "mode": "clean" if clean else "inspect", "found": rows, "notes": NOTES}, indent=2))
        return
    print(f"{'cleaned' if clean else 'inspect'}: {path}")
    print("\n".join(mdtable.format_table([["Class", "Count", "Confidence"]] + [
        [r["class"], str(r["count"]), r["confidence"]] for r in rows])))
    print("none found" if not rows else f"total: {sum(r['count'] for r in rows)}")
    for n in NOTES:
        print("note: " + n + " - the disclosure itself is kept; check it still reads as written")


if __name__ == "__main__":
    patterns.guard(main)
