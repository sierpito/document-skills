#!/usr/bin/env python3
"""Part of repair-document. Read-only inventory of machine-generation signals in a .pptx or .docx, with counts.

This is the "detect" pass as a script: it reports, it never changes anything and writes nothing. Local, stdlib
only. Reads raw XML with regexes (no serializer). Pair it with ooxml_fix.py (repair) and review-ai-content (score).

Usage: ooxml_inspect.py FILE [--json]
Exit code: 0 ok, 2 refused or bad input.
"""
import json, re, sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import patterns
    import ooxml_layout as layout
    import ooxml_fonts as fonts
    import mdtable
except ModuleNotFoundError:
    sys.exit("needs shared/patterns.py from the document-skills plugin root; run this script from the installed plugin")

BULLETS = "•●▪◦‣∙"
ZERO_WIDTH = "​‌‍⁠﻿"
FAKE_FAMILY = re.compile(r"\s(Bold|Italic|Bold Italic)$")


class Pkg:
    def __init__(self, path):
        z = patterns.open_zip(path)
        self.parts = {i.filename: z.read(i.filename) for i in z.infolist() if not i.is_dir()}
        self.kind = "pptx" if "ppt/presentation.xml" in self.parts else "docx" if "word/document.xml" in self.parts else None
        if not self.kind:
            sys.exit("not a .pptx or .docx package")

    def get(self, name):
        b = self.parts.get(name)
        return b.decode("utf8", "replace") if b is not None else ""

    def match(self, pattern):
        return sorted(n for n in self.parts if re.fullmatch(pattern, n))

    def join(self, pattern):
        return "\n".join(self.get(n) for n in self.match(pattern))


def text_nodes(x, tag):
    return [unescape(t) for t in re.findall(r"<%s(?:\s[^>]*)?>(.*?)</%s>" % (tag, tag), x, re.S)]


def paragraphs(x, p):
    return re.findall(r"<%s>.*?</%s>|<%s\s[^>]*>.*?</%s>" % (p, p, p, p), x, re.S)


def inspect(pkg):
    rows = []

    def add(signal, value, note="", severity="info"):
        rows.append({"signal": signal, "value": value, "note": note, "severity": severity})

    core, app = pkg.get("docProps/core.xml"), pkg.get("docProps/app.xml")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # --- properties
    dates = re.findall(r"<dcterms:(created|modified)[^>]*>([^<]*)<", core)
    bad = [f"{k} {v[:10]}" for k, v in dates if v[:4] in ("2006", "2011") or v[:10] > today]
    add("placeholder or future dates", len(bad), ", ".join(bad), "high" if bad else "info")
    creator = re.search(r"<dc:creator[^>]*>([^<]*)<", core)
    add("author (dc:creator)", creator.group(1).strip() if creator and creator.group(1).strip() else "empty",
        "", "high" if not (creator and creator.group(1).strip()) else "info")
    lm = re.search(r"<cp:lastModifiedBy[^>]*>([^<]*)<", core)
    add("last modified by", lm.group(1).strip() if lm and lm.group(1).strip() else "empty")
    add("stray dc:identifier", int(bool(re.search(r"<dc:identifier>[^<]+<", core))), "", "medium")
    zero = [t for t in ("Words", "Slides", "Notes") if re.search(r"<%s>0<" % t, app)]
    add("app.xml counters at 0", len(zero), ", ".join(zero), "high" if zero else "info")
    have = {k: v for k, v in re.findall(r"<(Words|Slides|Notes)>(\d+)<", app)}
    if pkg.kind == "pptx":
        slide_xml = pkg.join(r"ppt/slides/slide\d+\.xml")
        real = {"Slides": len(pkg.match(r"ppt/slides/slide\d+\.xml")), "Notes": len(pkg.match(r"ppt/notesSlides/notesSlide\d+\.xml")),
                "Words": len(unescape(" ".join(re.findall(r"<a:t>(.*?)</a:t>", slide_xml, re.S))).split())}
    else:
        real = {"Words": len(unescape(" ".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", pkg.get("word/document.xml"), re.S))).split())}
    off = [f"{k} says {have[k]}, file has {v}" for k, v in real.items() if k in have and have[k] != "0" and have[k] != str(v)]
    add("app.xml counters disagree with the file (after an edit)", len(off), "; ".join(off) + (" -> ooxml_fix.py --props \"\"" if off else ""), "medium" if off else "info")
    add("sensitivity label (docMetadata/LabelInfo.xml)", int("docMetadata/LabelInfo.xml" in pkg.parts),
        "report only: removal needs an explicit ask for this file")
    add("thumbnail from an older render", int(any(n.startswith("docProps/thumbnail") for n in pkg.parts)))
    # --- text and fonts
    if pkg.kind == "pptx":
        body = pkg.join(r"ppt/slides/slide\d+\.xml")
        notes = pkg.join(r"ppt/notesSlides/notesSlide\d+\.xml")
        t_body, t_notes = text_nodes(body, "a:t"), text_nodes(notes, "a:t")
        runs_xml = body + pkg.join(r"ppt/slideLayouts/slideLayout\d+\.xml") + pkg.join(r"ppt/slideMasters/slideMaster\d+\.xml")
        faces = re.findall(r'<a:(?:latin|ea|cs) typeface="([^"]*)"', runs_xml)
        theme = pkg.get("ppt/theme/theme1.xml")
        theme_fonts = re.findall(r'<a:(?:majorFont|minorFont)>\s*<a:latin typeface="([^"]*)"', theme)
        add("slides", len(pkg.match(r"ppt/slides/slide\d+\.xml")))
        sizes = [int(s) for s in re.findall(r'\bsz="(\d+)"', runs_xml)]
        noise = sum(1 for s in sizes if s % 100 and abs(s - round(s / 100) * 100) <= 2)
        other = sum(1 for s in sizes if s % 50 and not (s % 100 and abs(s - round(s / 100) * 100) <= 2))
        add("fractional type sizes: rounding noise (sz within 2 of a multiple of 100)", noise, "ooxml_fix --round-sizes", "high" if noise else "info")
        add("fractional type sizes: other (left alone)", other)
        add("pictures as p:pic", len(re.findall(r"<p:pic>", body)))
        shapes = re.findall(r"<p:sp>.*?</p:sp>", re.sub(r"<p:bg>.*?</p:bg>", "", body, flags=re.S), re.S)
        cust = sum(1 for s in shapes if "<a:blipFill" in s and "<a:custGeom" in s)
        rect = sum(1 for s in shapes if "<a:blipFill" in s and "<a:custGeom" not in s)
        add("images as picture fill on a custom shape (invisible in many previewers)", cust, "convert to p:pic", "critical" if cust else "info")
        add("images as picture fill on a plain shape (valid; no crop or alt-text semantics of a picture)", rect)
        add("layout placeholders (p:ph)", len(re.findall(r"<p:ph\b", body)), "0 means every shape is absolutely positioned", "info")
        off_canvas, overlaps, fails, checked, skipped, tight, short = [], [], [], 0, 0, [], []
        sld0 = re.search(r'<p:sldSz cx="(\d+)" cy="(\d+)"', pkg.get("ppt/presentation.xml"))
        W, H = (int(sld0.group(1)), int(sld0.group(2))) if sld0 else (0, 0)
        for n in pkg.match(r"ppt/slides/slide\d+\.xml"):
            sx = pkg.get(n)
            if W:
                o, v = layout.geometry_findings(sx, W, H)
                off_canvas += [f"{n.split('/')[-1]}: {s}" for s in o]
                overlaps += [f"{n.split('/')[-1]}: {s}" for s in v]
            for f in layout.fit_findings(sx):
                (tight if f["kind"] == "no slack" else short).append(f"{n.split('/')[-1]}: {f['text'][:22]!r} {f['slack_pct']}%")
            lx, mx, theme_c, cmap = layout.slide_context(pkg.parts, n)
            fl, ch, sk = layout.contrast_findings(sx, lx, mx, theme_c, cmap)
            fails += [dict(f, slide=n.split("/")[-1]) for f in fl]
            checked += ch
            skipped += sk
        add("text boxes with no slack (they wrap or break mid-word when a renderer measures a hair wider)", len(tight),
            "; ".join(tight[:3]) + (f"; +{len(tight) - 3} more" if len(tight) > 3 else "") + (" -> ooxml_fix.py --fit (estimate from Arial metrics; confirm in a render)" if tight else ""),
            "high" if tight else "info")
        add("text boxes shorter than their text (estimate)", len(short), "; ".join(short[:3]) + (" -> ooxml_fix.py --fit" if short else ""), "medium" if short else "info")
        add("text boxes extending off the slide", len(off_canvas), "; ".join(off_canvas[:3]), "high" if off_canvas else "info")
        add("overlapping text boxes (static; confirm with a render)", len(overlaps), "; ".join(overlaps[:3]), "medium" if overlaps else "info")
        add("text runs failing contrast (explicit colours, known background)", len(fails),
            f"{checked} runs checked, {skipped} text boxes skipped (background unknown); " + "; ".join(
                f"{f['slide']} {f['text']!r} {f['fg']} on {f['bg']} = {f['ratio']} (needs {f['need']})" for f in fails[:2]) + (" -> ooxml_fix.py --contrast" if fails else ""),
            "high" if fails else "info")
        xs = set(re.findall(r'<a:off x="(-?\d+)"', body))
        add("distinct x-origins", len(xs), "many distinct values = built by a program; structural, report only")
        sld = re.search(r'<p:sldSz cx="(\d+)" cy="(\d+)"', pkg.get("ppt/presentation.xml"))
        fmt = re.search(r"<PresentationFormat>([^<]*)<", app)
        if sld and fmt:
            ratio = int(sld.group(1)) / int(sld.group(2))
            wide, std = "wide" in fmt.group(1).lower() or "16:9" in fmt.group(1), "4:3" in fmt.group(1)
            mismatch = (wide and abs(ratio - 16 / 9) > 0.02) or (std and abs(ratio - 4 / 3) > 0.02)
            add("PresentationFormat contradicts sldSz", int(bool(mismatch)), f"{fmt.group(1)} vs {sld.group(1)}x{sld.group(2)}", "medium")
        emb = len(re.findall(r"<p:embeddedFont>", pkg.get("ppt/presentation.xml")))
        add("embedded fonts", emb, "ooxml_fix --strip-embedded-fonts", "high" if emb else "info")
        bu_real = len(re.findall(r"<a:bu(?:Char|AutoNum)\b", body))
        bu_typed = sum(1 for p in paragraphs(body, "a:p") if (text_nodes(p, "a:t") or [""])[0].lstrip().startswith(tuple(BULLETS)))
        note_label = "speaker notes"
    else:
        doc = pkg.get("word/document.xml")
        body = doc
        t_body = text_nodes(doc, "w:t")
        comments = pkg.get("word/comments.xml")
        t_notes = text_nodes(comments, "w:t")
        faces = [f for tag in re.findall(r"<w:rFonts\b[^>]*>", pkg.join(r"word/(document|styles)\.xml"))
                 for f in re.findall(r'w:(?:ascii|hAnsi|cs|eastAsia)="([^"]*)"', tag)]
        theme = pkg.get("word/theme/theme1.xml")
        theme_fonts = re.findall(r'<a:(?:majorFont|minorFont)>\s*<a:latin typeface="([^"]*)"', theme)
        add("paragraphs", len(paragraphs(doc, "w:p")))
        rsids = set(re.findall(r'w:rsid\w*="([0-9A-Fa-f]+)"', doc))
        add("distinct revision save ids (rsid)", len(rsids), "0 or 1 = no editing history", "medium" if len(rsids) <= 1 else "info")
        add("comments", len(re.findall(r"<w:comment\b", comments)))
        add("tracked changes (w:ins / w:del)", len(re.findall(r"<w:(?:ins|del)\b", doc)))
        run_fmt = len(re.findall(r"<w:r(?:\s[^>]*)?>\s*<w:rPr>", doc))
        styled = len(re.findall(r"<w:pStyle\b", doc))
        add("runs with direct formatting", run_fmt, "")
        add("paragraphs with a paragraph style", styled, "far fewer than paragraphs = styles unused", "medium" if run_fmt > 20 and styled == 0 else "info")
        combos = {}
        for rpr in re.findall(r"<w:rPr>(.*?)</w:rPr>", doc, re.S):
            combos[rpr] = combos.get(rpr, 0) + 1
        add("direct-format combinations used 5+ times", sum(1 for c in combos.values() if c >= 5), "candidates for a style")
        no_alt = len(re.findall(r"<wp:docPr\b(?![^>]*\bdescr=\"[^\"]+\")[^>]*>", doc))
        add("images without alt text", no_alt, "", "medium" if no_alt else "info")
        emb = len(re.findall(r"<w:embed(?:Regular|Bold|Italic|BoldItalic)\b", pkg.get("word/fontTable.xml")))
        add("embedded fonts", emb, "ooxml_fix --strip-embedded-fonts", "high" if emb else "info")
        bu_real = len(re.findall(r"<w:numPr>", doc))
        bu_typed = sum(1 for p in paragraphs(doc, "w:p") if (text_nodes(p, "w:t") or [""])[0].lstrip().startswith(tuple(BULLETS)))
        note_label = "comments"
    # --- common text signals
    fake = sorted({f for f in faces if FAKE_FAMILY.search(f)})
    fixes = []
    for f in fake[:2]:
        new, bold, italic, _ = fonts.target_for(f)
        fixes.append(f'ooxml_fix.py FILE --out OUT --rename-font "{f}" "{new}" --bold' if bold else f'ooxml_fix.py FILE --out OUT --rename-font "{f}" "{new}"')
    add("fabricated font families (name ends in Bold/Italic)", len(fake), ", ".join(fake) + ((" -> run: " + "; ".join(fixes) + " (or --normalize-fonts)") if fake else ""), "critical" if fake else "info")
    used = {}
    for f in faces:
        used[f] = used.get(f, 0) + 1
    add("font families used", len(used), ", ".join(f"{k} x{v}" for k, v in sorted(used.items(), key=lambda kv: -kv[1])[:5]))
    unsafe = {}
    for f in faces:
        new, _, _, status = fonts.target_for(f)
        if status != "ok" and not (f in fake and status == "renamed"):
            unsafe[f] = (new, status)
    risky = sorted(f for f, (new, st) in unsafe.items() if st == "no-safe-answer")
    subs = sorted(f"{f} -> {new}" for f, (new, st) in unsafe.items() if st == "renamed")
    add("font families that do not ship with Office or macOS (a viewer substitutes another font)", len(risky) + len(subs),
        "; ".join(([f"metric-compatible swap: {', '.join(subs)}"] if subs else []) + ([f"no safe automatic answer: {', '.join(risky[:5])}"] if risky else [])),
        "high" if (risky or subs) else "info")
    if theme_fonts:
        stray = sorted(set(f for f in used if f not in theme_fonts and not f.startswith("+")))
        add("theme fonts", ", ".join(dict.fromkeys(theme_fonts)), f"{len(stray)} run/style families differ from the theme" if stray else "runs agree with the theme")
    add("typed bullets (should be list formatting)", bu_typed, "ooxml_fix --bullets", "medium" if bu_typed else "info")
    add("real list formatting", bu_real)
    alltext = " ".join(t_body)
    add("arrows used as punctuation", alltext.count("→") + alltext.count("⇒"))
    add("zero-width characters", sum(alltext.count(c) for c in ZERO_WIDTH), "scripts/invisible_chars.py", "high" if any(c in alltext for c in ZERO_WIDTH) else "info")
    residue = [r for r in patterns.load_rules("review") if r["kind"] in ("residue", "token")]
    flagged = [t for t in t_notes if any(r["rx"].search(t) for r in residue)]
    add(f"generator-facing {note_label}", len(flagged), (flagged[0][:70] if flagged else ""), "critical" if flagged else "info")
    # --- relationships
    ext = missing = 0
    for n in pkg.match(r".*\.rels"):
        base = n.replace("_rels/", "").rsplit(".rels", 1)[0]
        folder = base.rsplit("/", 1)[0] if "/" in base else ""
        for rel in re.findall(r"<Relationship\b[^>]*>", pkg.get(n)):
            tgt = re.search(r'Target="([^"]*)"', rel)
            if not tgt:
                continue
            if 'TargetMode="External"' in rel:
                ext += 1
                continue
            t = tgt.group(1)
            path = t.lstrip("/") if t.startswith("/") else str(Path(folder, t)) if folder else t
            parts = []
            for seg in path.split("/"):
                if seg == "..":
                    parts and parts.pop()
                elif seg and seg != ".":
                    parts.append(seg)
            if "/".join(parts) not in pkg.parts:
                missing += 1
    add("external relationship targets", ext, "images or links outside the file", "medium" if ext else "info")
    add("relationship targets that do not resolve", missing, "", "high" if missing else "info")
    return rows


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"):
        sys.exit(__doc__)
    path = Path(a[0])
    pkg = Pkg(path)
    rows = inspect(pkg)
    if "--json" in a:
        print(json.dumps({"file": str(path), "kind": pkg.kind, "signals": rows}, indent=2, ensure_ascii=False))
        return
    print(f"inspect ({pkg.kind}): {path}\n")
    print("\n".join(mdtable.format_table([["Signal", "Value", "Severity", "Note"]] + [
        [r["signal"], str(r["value"]), r["severity"], r["note"].replace("|", "\\|")] for r in rows])))
    hot = [r for r in rows if r["severity"] in ("critical", "high") and r["value"] not in (0, "info")]
    print(f"\n{len(hot)} critical/high signals. Read-only: nothing was changed.")


if __name__ == "__main__":
    patterns.guard(main)
