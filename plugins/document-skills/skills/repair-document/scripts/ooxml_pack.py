#!/usr/bin/env python3
"""Part of repair-document. Safe unpack, in-order repack and a measured word ledger for .docx/.pptx.

Local, stdlib only. Never overwrites, never deletes, never modifies the input.

  ooxml_pack.py unpack SRC DIR                     extract SRC into a new, empty-or-absent DIR (zip-slip checked)
  ooxml_pack.py repack SRC DIR OUT [--skip PART..] write OUT from SRC's member list and order, reading
                                                   each member from DIR; --skip leaves a part out on purpose
  ooxml_pack.py ledger INPUT OUTPUT [--json]       words equal / rewritten / added / removed, body and notes separately
"""
import difflib, json, os, re, sys, zipfile
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
try:
    import patterns
except ModuleNotFoundError:
    sys.exit("needs shared/patterns.py from the document-skills plugin root; run this script from the installed plugin")


def fail(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def check_names(z):
    for n in z.namelist():
        p = Path(n)
        if n.startswith("/") or p.is_absolute() or ".." in n.split("/"):
            fail("unsafe member path: " + n)


def unpack(src, dest):
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        fail("exists and not empty, not overwriting: " + str(dest))
    with patterns.open_zip(src) as z:
        check_names(z)
        z.extractall(dest)
    print(f"unpacked {src} -> {dest}")


def repack(src, unpacked, out, skip):
    out = Path(out)
    if out.exists():
        fail("exists, not overwriting: " + str(out))
    tmp = out.with_name(out.name + ".tmp")
    with patterns.open_zip(src) as a, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        check_names(a)
        for info in a.infolist():  # input order keeps [Content_Types].xml first
            if info.filename in skip or info.is_dir():
                continue
            z.writestr(info, (Path(unpacked) / info.filename).read_bytes())
    os.replace(tmp, out)
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(out) as b:
        want = [n for n in a.namelist() if n not in skip and not n.endswith("/")]
        if want != b.namelist():
            fail("member list differs from the input after repack", 1)
    print(f"wrote {out} ({len(want)} members, input order)")


def texts(path):
    """Return {'body': [strings], 'notes': [strings]} from a .docx or .pptx."""
    out = {"body": [], "notes": []}
    with patterns.open_zip(path) as z:
        check_names(z)
        for n in sorted(z.namelist()):
            if re.fullmatch(r"word/(document|footnotes|endnotes|header\d*|footer\d*)\.xml", n):
                key, para, run = "body", r"<w:p[ >].*?</w:p>", r"<w:t(?:\s[^>]*)?>(.*?)</w:t>"
            elif re.fullmatch(r"ppt/slides/slide\d+\.xml", n):
                key, para, run = "body", r"<a:p>.*?</a:p>|<a:p .*?</a:p>", r"<a:t>(.*?)</a:t>"
            elif re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n):
                key, para, run = "notes", r"<a:p>.*?</a:p>|<a:p .*?</a:p>", r"<a:t>(.*?)</a:t>"
            else:
                continue
            x = z.read(n).decode("utf8", "replace")
            for p in re.findall(para, x, re.S):
                t = unescape("".join(re.findall(run, p, re.S))).strip()
                if t:
                    out[key].append(t)
    return out


def ledger(a, b):
    ta, tb = texts(a), texts(b)
    res = {}
    for key in ("body", "notes"):
        wa = [w for s in ta[key] for w in s.split()]
        wb = [w for s in tb[key] for w in s.split()]
        eq = rew = add = rem = 0
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
            if op == "equal":
                eq += i2 - i1
            elif op == "replace":
                rew += min(i2 - i1, j2 - j1)       # words that took the place of old ones
                add += max(0, (j2 - j1) - (i2 - i1))  # extra words beyond them
            elif op == "insert":
                add += j2 - j1
            elif op == "delete":
                rem += i2 - i1
            if op == "replace":
                rem += max(0, (i2 - i1) - (j2 - j1))
        res[key] = {"input_words": len(wa), "output_words": len(wb), "equal": eq, "rewritten": rew, "added": add, "removed": rem}
    return res


def main():
    a = sys.argv[1:]
    if len(a) < 3:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "unpack" and len(a) == 3:
        unpack(a[1], a[2])
    elif cmd == "repack" and len(a) >= 4:
        skip = set(a[a.index("--skip") + 1:]) if "--skip" in a else set()
        repack(a[1], a[2], a[3], skip)
    elif cmd == "ledger" and len(a) >= 3:
        r = ledger(a[1], a[2])
        if "--json" in a:
            print(json.dumps(r, indent=2))
        else:
            for k, v in r.items():
                print(f"{k}: input {v['input_words']} words, output {v['output_words']}; "
                      f"kept {v['equal']}, rewritten {v['rewritten']}, added {v['added']}, removed {v['removed']}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    patterns.guard(main)
