#!/usr/bin/env python3
"""Part of repair-document. Render one slide of a .pptx to a PNG so it can be looked at (macOS Quick Look, no install).

Quick Look draws only the first slide, so a copy of the deck with the wanted slide moved first is rendered; the original is
never touched. Quick Look is a real previewer (it also shows what a viewer does with picture fills and missing fonts), but
it can be slow or give up on heavy decks: a timeout is reported as "no answer", which is not a pass.

A second renderer is used when LibreOffice is installed (it need not be on PATH: the macOS app is found), with poppler's
pdftoppm: the whole deck becomes a PDF once, so every slide renders quickly and heavy decks that stall Quick Look still
render. LibreOffice is also only a proxy for PowerPoint; say which renderer a PNG came from.

Usage: slide_preview.py FILE --slide N [--out DIR] [--size 1300] [--timeout 90] [--all] [--renderer auto|soffice|quicklook]
  --all renders every slide. auto = LibreOffice when available, else Quick Look. Output: DIR/<stem>-slideN.png (never
  overwrites; a number is added).
Exit code: 0 rendered, 1 no answer or no previewer, 2 bad input.
"""
import re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def reordered(src, slide_no, dest):
    with zipfile.ZipFile(src) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in n.split("/"):
                die("unsafe archive")
        pres = z.read("ppt/presentation.xml").decode("utf8")
        rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf8")
        m = re.search(r'Id="(\w+)"[^>]*Target="slides/slide%d\.xml"|Target="slides/slide%d\.xml"[^>]*Id="(\w+)"' % (slide_no, slide_no), rels)
        if not m:
            die(f"no slide {slide_no}")
        rid = m.group(1) or m.group(2)
        ids = re.findall(r"<p:sldId\b[^>]*/>", pres)
        mine = next((i for i in ids if f'r:id="{rid}"' in i), None)
        if not mine:
            die(f"slide {slide_no} is not in the slide list")
        new = pres if ids[0] == mine else pres.replace(mine, "", 1).replace(ids[0], mine + ids[0], 1)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            for info in z.infolist():
                out.writestr(info, new.encode("utf8") if info.filename == "ppt/presentation.xml" else z.read(info.filename))
        return len(ids)


MAC_SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
_PDFS = {}


def soffice_path():
    return shutil.which("soffice") or (MAC_SOFFICE if Path(MAC_SOFFICE).is_file() else None)


def render_soffice(src, slide_no, outdir, size, timeout):
    soffice, ppm = soffice_path(), shutil.which("pdftoppm")
    if not soffice or not ppm:
        return None
    key = str(src.resolve())
    if key not in _PDFS:
        tmp = Path(tempfile.mkdtemp())
        try:
            subprocess.run([soffice, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", str(tmp), str(src)],
                           capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"no answer from LibreOffice within {timeout}s: not a pass", file=sys.stderr)
            return None
        pdf = tmp / (src.stem + ".pdf")
        _PDFS[key] = pdf if pdf.is_file() else None
    pdf = _PDFS[key]
    if not pdf:
        print("LibreOffice produced no PDF", file=sys.stderr)
        return None
    base = Path(tempfile.mkdtemp()) / "s"
    done = subprocess.run([ppm, "-f", str(slide_no), "-l", str(slide_no), "-png", "-singlefile", "-scale-to-x", str(size), "-scale-to-y", "-1", str(pdf), str(base)],
                          capture_output=True, text=True)
    png = Path(str(base) + ".png")
    if done.returncode != 0 or not png.is_file():
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / f"{src.stem}-slide{slide_no}.png"
    n = 2
    while dest.exists():
        dest = outdir / f"{src.stem}-slide{slide_no}-{n}.png"
        n += 1
    shutil.copyfile(png, dest)
    return dest


def render(src, slide_no, outdir, size, timeout, renderer="auto"):
    if renderer in ("auto", "soffice"):
        png = render_soffice(src, slide_no, outdir, size, timeout)
        if png or renderer == "soffice":
            if not png:
                print("LibreOffice or pdftoppm is not available or gave no image", file=sys.stderr)
            return png
    return render_quicklook(src, slide_no, outdir, size, timeout)


def render_quicklook(src, slide_no, outdir, size, timeout):
    tmp = Path(tempfile.mkdtemp())
    first = tmp / f"{src.stem}-slide{slide_no}.pptx"
    reordered(src, slide_no, first)
    try:
        done = subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(tmp), str(first)], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        print("no previewer: qlmanage (macOS Quick Look) is not available; use LibreOffice (soffice --headless --convert-to pdf) and pdftoppm", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"no answer from Quick Look within {timeout}s for slide {slide_no}: investigate heavy images, not a pass", file=sys.stderr)
        return None
    png = tmp / (first.name + ".png")
    if done.returncode != 0 or not png.is_file():
        print(f"Quick Look produced no image for slide {slide_no}", file=sys.stderr)
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / f"{src.stem}-slide{slide_no}.png"
    n = 2
    while dest.exists():
        dest = outdir / f"{src.stem}-slide{slide_no}-{n}.png"
        n += 1
    shutil.copyfile(png, dest)
    return dest


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"):
        die(__doc__)
    src = Path(a[0])
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
    if src.suffix.lower() != ".pptx" or not src.is_file():
        die("needs an existing .pptx file")
    outdir = Path(opt("--out", "."))
    size, timeout = int(opt("--size", 1300)), int(opt("--timeout", 90))
    with zipfile.ZipFile(src) as z:
        count = len(re.findall(r"<p:sldId\b", z.read("ppt/presentation.xml").decode("utf8")))
    slides = range(1, count + 1) if "--all" in a else [int(opt("--slide", 1))]
    failed = 0
    for n in slides:
        png = render(src, n, outdir, size, timeout, opt("--renderer", "auto"))
        if png:
            print(png)
        else:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, zipfile.BadZipFile) as e:
        die(f"error: {e}")
