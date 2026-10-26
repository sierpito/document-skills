#!/usr/bin/env python3
"""Part of repair-document. Deterministic, diffable fixes for .pptx and .docx, with a count for each.

Local, stdlib only, no network. Works on the raw XML text (regex), never round-trips through an XML
serializer, so namespace prefixes stay as they were. The input is never modified; without --out it is a
dry run that only reports what would change. Never overwrites. Members keep the input's order.

Usage: ooxml_fix.py SRC [--out OUT] [flags] [--json]
  --round-sizes                  pptx: sz="2499" -> 2500 (values within 2 of a multiple of 100 only); spcPts of the
                                 same paragraph scale by the same ratio; other fractional sizes are reported
  --rename-font OLD NEW [--bold] rename a typeface in runs, theme and styles (pptx a:latin/ea/cs, docx w:rFonts);
                                 --bold adds bold to runs that used a fake "... Bold" family and lack it
  --normalize-fonts              every family named like 'X Bold'/'X Italic' becomes X with bold/italic set, and metric-compatible
                                 look-alikes (Arimo, Tinos, Carlito...) become the Office font; others are reported, not guessed
  --strip-embedded-fonts         remove embedded font lists, their relationships, parts and content type
  --bullets                      typed bullets (U+2022 and look-alikes) at paragraph start become real list formatting
  --props author=NAME[,date=today|YYYY-MM-DD]
                                 confirmed author into dc:creator / cp:lastModifiedBy; placeholder (2006, 2011) or
                                 future dates become today (or the given date); stray dc:identifier dropped;
                                 Slides / Notes / Words counters fixed from the file. No author flag, no author change.
  --allow-clipped                with --images: also convert freeforms whose picture is a PNG with transparency and whose outline is
                                 straight lines (a cut-out: the transparency already hides what the outline hides)
  --images                       pptx: a picture-filled rectangle freeform becomes a real p:pic (single-shape groups without
                                 rotation or flip, or ungrouped shapes, rotation kept); other freeforms are reported, not touched
  --contrast                     pptx: text runs with an explicit colour that fails WCAG against a known background are moved
                                 along their hue to 4.6:1 (3.0:1 for large text); unknown backgrounds are left alone
  --fit                          pptx: boxes with no slack for their text (estimated from Arial metrics) are widened ~12% into free space,
                                 a single-line title that still cannot fit gets wrapping switched off, short boxes grow into free space below
  --report-notes                 list speaker notes / comments that read as generator-facing (report only)
Exit code: 0 ok, 2 refused (usage, unsafe archive, output exists).
"""
import json, re, sys, zipfile
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import patterns
    import ooxml_layout as layout
    import ooxml_fonts as fonts
except ModuleNotFoundError:
    sys.exit("needs shared/patterns.py from the document-skills plugin root; run this script from the installed plugin")

BULLET_CHARS = "•●▪◦‣∙"
REL_FONT = re.compile(r'<Relationship\b[^>]*Type="[^"]*/font"[^>]*/>')
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NUM_ID = "9001"


class Package:
    def __init__(self, path):
        with patterns.open_zip(path) as z:
            self.infos = z.infolist()
            self.parts = {i.filename: z.read(i.filename) for i in self.infos}
        self.skipped = []  # parts that are not UTF-8 text: left untouched and reported
        self.removed, self.added = set(), []
        self.kind = "pptx" if "ppt/presentation.xml" in self.parts else "docx" if "word/document.xml" in self.parts else None
        if not self.kind:
            sys.exit("not a .pptx or .docx package")

    def text(self, name):
        return self.parts[name].decode("utf8")

    def is_text(self, name):
        try:
            self.parts[name].decode("utf8")
            return True
        except UnicodeDecodeError:
            if name not in self.skipped:
                self.skipped.append(name)
            return False

    def get_text(self, name):
        return self.parts[name].decode("utf8") if name in self.parts else ""

    def put(self, name, s):
        if name not in self.parts:
            self.added.append(name)
        self.parts[name] = s.encode("utf8")

    def remove(self, name):
        if name in self.parts:
            self.removed.add(name)

    def names(self, pattern):
        return [n for n in self.parts if n not in self.removed and re.fullmatch(pattern, n) and self.is_text(n)]

    def write(self, out, src):
        tmp = out.with_name(out.name + ".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for info in self.infos:
                if info.filename in self.removed or info.is_dir():
                    continue
                z.writestr(info, self.parts[info.filename])
            for n in self.added:
                if n not in self.removed:
                    z.writestr(n, self.parts[n])
        tmp.replace(out)


# ---------------------------------------------------------------- fixes
def round_sizes(pkg, rep):
    changed = spc = other = 0
    for n in pkg.names(r"ppt/(slides/slide|slideLayouts/slideLayout|slideMasters/slideMaster)\d+\.xml"):
        x = pkg.text(n)

        def para(m):
            nonlocal changed, spc, other
            p, ratio = m.group(0), None

            def sz(mm):
                nonlocal changed, other, ratio
                v = int(mm.group(1))
                r = round(v / 100) * 100
                if v % 100 and abs(v - r) <= 2 and r > 0:
                    changed += 1
                    ratio = ratio or r / v
                    return f'sz="{r}"'
                if v % 50:
                    other += 1
                return mm.group(0)
            p = re.sub(r'\bsz="(\d+)"', sz, p)
            if ratio:
                def sp(mm):
                    nonlocal spc
                    spc += 1
                    return f'<a:spcPts val="{round(int(mm.group(1)) * ratio)}"'
                p = re.sub(r'<a:spcPts val="(\d+)"', sp, p)
            return p
        x2 = re.sub(r"<a:p>.*?</a:p>|<a:p\s[^>]*>.*?</a:p>", para, x, flags=re.S)
        if x2 != x:
            pkg.put(n, x2)
    rep["round-sizes"] = {"sizes rounded": changed, "spcPts scaled": spc, "other fractional sizes left": other}


def rename_font(pkg, old, new, bold, rep, italic=False):
    runs = renamed = bolded = italicised = missing_bold = 0
    o, nw = escape(old, quote=True), escape(new, quote=True)
    for n in pkg.names(r"(ppt|word)/.*\.xml"):
        if "/_rels/" in n:
            continue
        x = pkg.text(n)
        if old not in x and o not in x:
            continue
        before = x.count(f'"{o}"')
        if n.startswith("ppt/"):
            def run(m):
                nonlocal runs, bolded, italicised, missing_bold
                r = m.group(0)
                if f'typeface="{o}"' not in r:
                    return r
                runs += 1
                head = re.match(r"<a:r>\s*<a:rPr\b[^>]*>", r)
                if head:
                    tag, newtag = head.group(0), head.group(0)
                    if not re.search(r'\bb="(1|true)"', tag):
                        if bold:
                            newtag = (newtag[:-2].rstrip() + ' b="1"/>') if newtag.endswith("/>") else (newtag[:-1] + ' b="1">')
                            bolded += 1
                        else:
                            missing_bold += 1
                    if italic and not re.search(r'\bi="(1|true)"', tag):
                        newtag = (newtag[:-2].rstrip() + ' i="1"/>') if newtag.endswith("/>") else (newtag[:-1] + ' i="1">')
                        italicised += 1
                    if newtag != tag:
                        r = r.replace(tag, newtag, 1)
                return r
            x = re.sub(r"<a:r>.*?</a:r>", run, x, flags=re.S)
            x = x.replace(f'typeface="{o}"', f'typeface="{nw}"')
        else:
            def wrun(m):
                nonlocal runs, bolded, italicised, missing_bold
                r = m.group(0)
                if f'"{o}"' not in r:
                    return r
                runs += 1
                if not re.search(r"<w:b(/>|\s)", r):
                    if bold:
                        r2 = re.sub(r"(<w:rFonts\b[^>]*/>)", r"\1<w:b/>", r, count=1)
                        bolded += r2 != r
                        r = r2
                    else:
                        missing_bold += 1
                if italic and not re.search(r"<w:i(/>|\s)", r):
                    r2 = re.sub(r"(<w:rFonts\b[^>]*/>(?:<w:b/>)?)", r"\1<w:i/>", r, count=1)
                    italicised += r2 != r
                    r = r2
                return r
            x = re.sub(r"<w:r>.*?</w:r>|<w:r\s[^>]*>.*?</w:r>", wrun, x, flags=re.S)
            x = re.sub(r'(w:(?:ascii|hAnsi|cs|eastAsia)=")%s(")' % re.escape(o), r"\g<1>%s\2" % nw.replace("\\", "\\\\"), x)
            x = x.replace(f'w:name="{o}"', f'w:name="{nw}"')
        renamed += before - x.count(f'"{o}"')
        pkg.put(n, x)
    rep["rename-font"] = {"references renamed": renamed, "runs using the old family": runs,
                          "runs made bold": bolded, "runs made italic": italicised, "runs lacking bold (use --bold)": missing_bold}


def normalize_fonts(pkg, rep):
    """Apply fonts.target_for() to every family used in runs, styles and the theme; report what has no safe answer."""
    seen = {}
    for n in pkg.names(r"(ppt|word)/.*\.xml"):
        if "/_rels/" in n:
            continue
        x = pkg.text(n)
        for f in re.findall(r'<a:(?:latin|ea|cs|sym) typeface="([^"]+)"|w:(?:ascii|hAnsi|cs|eastAsia)="([^"]+)"', x):
            f = f[0] or f[1]
            seen[f] = seen.get(f, 0) + 1
    renamed, left = {}, {}
    for fam in seen:
        new, bold, italic, status = fonts.target_for(fam)
        if status == "renamed":
            renamed[fam] = (new, bold, italic)
        elif status == "no-safe-answer":
            left[fam] = seen[fam]
    refs = 0
    for fam, (new, bold, italic) in renamed.items():
        before = sum(pkg.text(n).count(f'"{escape(fam, quote=True)}"') for n in pkg.names(r"(ppt|word)/.*\.xml") if "/_rels/" not in n)
        rename_font(pkg, fam, new, bold, {}, italic=italic)
        refs += before
    rep["normalize-fonts"] = {"families renamed": len(renamed), "references updated": refs,
                              "left (no safe answer, decide by hand)": ", ".join(sorted(left)[:6]) or "none"}


def strip_embedded_fonts(pkg, rep):
    lists = rels = parts = 0
    for n in pkg.names(r"ppt/presentation\.xml"):
        x = pkg.text(n)
        x2, k = re.subn(r"<p:embeddedFontLst>.*?</p:embeddedFontLst>", "", x, flags=re.S)
        if k:
            lists += k
            pkg.put(n, x2)
    for n in pkg.names(r"word/fontTable\.xml"):
        x = pkg.text(n)
        x2, k = re.subn(r"<w:embed(?:Regular|Bold|Italic|BoldItalic)\b[^>]*/>", "", x)
        if k:
            lists += k
            pkg.put(n, x2)
    for n in pkg.names(r"(ppt|word)/_rels/(presentation|fontTable)\.xml\.rels"):
        x = pkg.text(n)
        base = n.split("/_rels/")[0]
        for m in REL_FONT.finditer(x):
            t = re.search(r'Target="([^"]+)"', m.group(0))
            if t:
                pkg.remove(f"{base}/{t.group(1)}".replace("//", "/"))
                parts += 1
        x2, k = REL_FONT.subn("", x)
        if k:
            rels += k
            pkg.put(n, x2)
    if lists or rels:
        x = pkg.text("[Content_Types].xml")
        x2 = re.sub(r'<Default\b[^>]*Extension="(?:fntdata|odttf)"[^>]*/>', "", x)
        x2 = re.sub(r'<Override\b[^>]*PartName="/(?:ppt|word)/fonts/[^"]*"[^>]*/>', "", x2)
        if x2 != x:
            pkg.put("[Content_Types].xml", x2)
    rep["strip-embedded-fonts"] = {"font lists/entries removed": lists, "relationships removed": rels, "font parts removed": parts}


def _first_text(p, tag):
    m = re.search(r"<%s(?:\s[^>]*)?>(.*?)</%s>" % (tag, tag), p, re.S)
    return m


def bullets_pptx(pkg):
    done = 0
    for n in pkg.names(r"ppt/(slides/slide|slideLayouts/slideLayout)\d+\.xml"):
        x = pkg.text(n)

        def para(m):
            nonlocal done
            p = m.group(0)
            t = _first_text(p, "a:t")
            if not t or not t.group(1).lstrip(" ").startswith(tuple(BULLET_CHARS)):
                return p
            if re.search(r"<a:bu(Char|AutoNum|None|Blip)\b", p):
                return p
            new_t = re.sub(r"^[ ]*[%s][  ]*" % BULLET_CHARS, "", t.group(1))
            p = p[:t.start(1)] + new_t + p[t.end(1):]
            bu = '<a:buChar char="\u2022"/>'
            hang = ' marL="285750" indent="-285750"'
            selfclosed = re.search(r"<a:pPr\b([^>]*)/>", p)
            opened = re.search(r"<a:pPr\b([^>]*)>", p)
            if selfclosed and (not opened or opened.start() == selfclosed.start() and opened.group(1).endswith("/")):
                attrs = selfclosed.group(1)
                p = p[:selfclosed.start()] + "<a:pPr%s%s>%s</a:pPr>" % (attrs, "" if "marL=" in attrs else hang, bu) + p[selfclosed.end():]
            elif opened:
                attrs = opened.group(1)
                p = p[:opened.start()] + "<a:pPr%s%s>" % (attrs, "" if "marL=" in attrs else hang) + p[opened.end():]
                end = p.index("</a:pPr>")
                later = re.search(r"<a:(?:tabLst|defRPr|extLst)\b", p[:end])
                at = later.start() if later else end
                p = p[:at] + bu + p[at:]
            else:
                p = re.sub(r"^(<a:p(?:\s[^>]*)?>)", lambda mm: mm.group(1) + "<a:pPr%s>%s</a:pPr>" % (hang, bu), p, count=1)
            done += 1
            return p
        x2 = re.sub(r"<a:p>.*?</a:p>|<a:p\s[^>]*>.*?</a:p>", para, x, flags=re.S)
        if x2 != x:
            pkg.put(n, x2)
    return done


NUMBERING_ABSTRACT = (
    '<w:abstractNum w:abstractNumId="%s"><w:multiLevelType w:val="hybridMultilevel"/>'
    '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
    '<w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>' % NUM_ID)
NUMBERING_NUM = '<w:num w:numId="%s"><w:abstractNumId w:val="%s"/></w:num>' % (NUM_ID, NUM_ID)


def ensure_numbering(pkg):
    wns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    if "word/numbering.xml" in pkg.parts and "word/numbering.xml" not in pkg.removed:
        x = pkg.text("word/numbering.xml")
        if f'w:numId="{NUM_ID}"' in x:
            return
        first_num = re.search(r"<w:num\b", x)
        x = (x[:first_num.start()] + NUMBERING_ABSTRACT + x[first_num.start():]) if first_num else x.replace("</w:numbering>", NUMBERING_ABSTRACT + "</w:numbering>")
        x = x.replace("</w:numbering>", NUMBERING_NUM + "</w:numbering>")
        pkg.put("word/numbering.xml", x)
        return
    pkg.put("word/numbering.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:numbering {wns}>'
            + NUMBERING_ABSTRACT + NUMBERING_NUM + "</w:numbering>")
    rels = pkg.text("word/_rels/document.xml.rels")
    rels = rels.replace("</Relationships>", f'<Relationship Id="rIdNum{NUM_ID}" Type="{NS_REL}/numbering" Target="numbering.xml"/></Relationships>')
    pkg.put("word/_rels/document.xml.rels", rels)
    ct = pkg.text("[Content_Types].xml")
    if "/word/numbering.xml" not in ct:
        ct = ct.replace("</Types>", '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>')
        pkg.put("[Content_Types].xml", ct)


def bullets_docx(pkg):
    x = pkg.text("word/document.xml")
    done = 0

    def para(m):
        nonlocal done
        p = m.group(0)
        if "<w:numPr>" in p:
            return p
        t = _first_text(p, "w:t")
        if not t or not unescape(t.group(1)).lstrip(" ").startswith(tuple(BULLET_CHARS)):
            return p
        rest = re.sub(r"^[ ]*[%s][  ]*" % BULLET_CHARS, "", t.group(1))
        if rest.strip():
            p = p[:t.start(1)] + rest + p[t.end(1):]
        else:  # the marker sat alone in its run: drop the run and a tab run after it
            p = re.sub(r"<w:r(?:\s[^>]*)?>(?:(?!</w:r>).)*?<w:t[^>]*>%s</w:t></w:r>(<w:r><w:tab/></w:r>)?" % re.escape(t.group(1)), "", p, count=1, flags=re.S)
        num = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="%s"/></w:numPr>' % NUM_ID
        if re.search(r"<w:pPr>", p):
            lead = re.match(r"(<w:p(?:\s[^>]*)?><w:pPr>)((?:<w:(?:pStyle|keepNext|keepLines|pageBreakBefore|framePr|widowControl)\b[^>]*/>)*)", p)
            p = p[:lead.end()] + num + p[lead.end():]
        elif re.search(r"<w:pPr/>", p):
            p = p.replace("<w:pPr/>", "<w:pPr>%s</w:pPr>" % num, 1)
        else:
            p = re.sub(r"^(<w:p(?:\s[^>]*)?>)", r"\1<w:pPr>%s</w:pPr>" % num, p, count=1)
        done += 1
        return p
    x2 = re.sub(r"<w:p>.*?</w:p>|<w:p\s[^>]*>.*?</w:p>", para, x, flags=re.S)
    if done:
        ensure_numbering(pkg)
        pkg.put("word/document.xml", x2)
    return done


def _rect_path(sp):
    """True when the shape's single path is its own bounding rectangle (so a picture needs no clipping)."""
    paths = re.findall(r"<a:path\b([^>]*)>(.*?)</a:path>", sp, re.S)
    if len(paths) != 1:
        return False
    attrs, body = paths[0]
    w, h = re.search(r'\bw="(\d+)"', attrs), re.search(r'\bh="(\d+)"', attrs)
    if not (w and h) or re.search(r"<a:(cubicBezTo|quadBezTo|arcTo)", body):
        return False
    w, h = int(w.group(1)), int(h.group(1))
    pts = {(int(a), int(b)) for a, b in re.findall(r'<a:pt x="(-?\d+)" y="(-?\d+)"', body)}
    return pts == {(0, 0), (w, 0), (w, h), (0, h)}


def _pic_from(sp, off, ext, xfrm_attrs):
    ident = re.search(r'<p:cNvPr\b[^>]*\bid="(\d+)"', sp)
    name = re.search(r'<p:cNvPr\b[^>]*\bname="([^"]*)"', sp)
    blip = re.search(r"<a:blip\b[^>]*/>|<a:blip\b[^>]*>.*?</a:blip>", sp, re.S)
    src = re.search(r"<a:srcRect\b[^>]*/>", sp)
    cid = ident.group(1) if ident else "0"
    cname = (name.group(1) if name else "Picture " + cid).replace("Freeform", "Picture")
    return ('<p:pic><p:nvPicPr><p:cNvPr id="%s" name="%s"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            '<p:blipFill>%s%s<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            '<p:spPr><a:xfrm%s><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
            % (cid, cname, blip.group(0), src.group(0) if src else "", xfrm_attrs, off[0], off[1], ext[0], ext[1]))


def _xfrm(sp):
    m = re.search(r"<a:xfrm\b([^>]*)>\s*<a:off x=\"(-?\d+)\" y=\"(-?\d+)\"\s*/>\s*<a:ext cx=\"(\d+)\" cy=\"(\d+)\"\s*/>", sp)
    return (m.group(1), (int(m.group(2)), int(m.group(3))), (int(m.group(4)), int(m.group(5)))) if m else None


def _has_alpha(pkg, slide, sp):
    """True when the shape's picture is a PNG with an alpha channel or tRNS chunk (a cut-out)."""
    import posixpath
    emb = re.search(r'<a:blip\b[^>]*r:embed="(\w+)"', sp)
    rels = pkg.get_text(slide.replace("slides/", "slides/_rels/") + ".rels")
    tgt = re.search(r'Id="%s"[^>]*Target="([^"]+)"|Target="([^"]+)"[^>]*Id="%s"' % ((emb.group(1),) * 2), rels) if emb else None
    if not tgt:
        return False
    name = posixpath.normpath(posixpath.join("ppt/slides", tgt.group(1) or tgt.group(2)))
    data = pkg.parts.get(name, b"")
    return data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 26 and (data[25] in (4, 6) or b"tRNS" in data[:4096])


def images(pkg, rep, allow_clipped=False):
    converted = left = clipped = 0
    for n in pkg.names(r"ppt/slides/slide\d+\.xml"):
        x = pkg.text(n)
        changed = False

        def convertible(sp):
            visible = re.sub(r"<a:ln\b[^>]*>\s*<a:noFill/>.*?</a:ln>", "", sp, flags=re.S)  # an outline that is switched off is nothing
            if not ("<a:custGeom" in sp and "<a:blipFill" in sp and not re.search(r"<a:(ln|solidFill|gradFill)\b", visible) and _xfrm(sp)):
                return False
            return _rect_path(sp) or (allow_clipped and not re.search(r"<a:(cubicBezTo|quadBezTo|arcTo)", sp) and _has_alpha(pkg, n, sp))

        def group(m):
            nonlocal converted, left, changed, clipped
            g = m.group(0)
            sps = re.findall(r"<p:sp>.*?</p:sp>", g, re.S)
            others = re.search(r"<p:(pic|cxnSp|graphicFrame)\b", g)
            gx = re.search(r"<p:grpSpPr>\s*<a:xfrm\b([^>]*)>\s*<a:off x=\"(-?\d+)\" y=\"(-?\d+)\"\s*/>\s*<a:ext cx=\"(\d+)\" cy=\"(\d+)\"\s*/>"
                           r"\s*<a:chOff x=\"(-?\d+)\" y=\"(-?\d+)\"\s*/>\s*<a:chExt cx=\"(\d+)\" cy=\"(\d+)\"", g)
            if len(sps) != 1 or others or not gx or not convertible(sps[0]):
                return g
            attrs = gx.group(1)
            if re.search(r'rot="(?!0")|flip[HV]="(?!false)', attrs):
                return g
            ox, oy, ex, ey, cx0, cy0, cex, cey = (int(v) for v in gx.groups()[1:])
            if not (cex and cey):
                return g
            _, (sx, sy), (sw, sh) = _xfrm(sps[0])
            off = (ox + round((sx - cx0) * ex / cex), oy + round((sy - cy0) * ey / cey))
            ext = (round(sw * ex / cex), round(sh * ey / cey))
            converted += 1
            clipped += not _rect_path(sps[0])
            changed = True
            return _pic_from(sps[0], off, ext, "")

        x2 = re.sub(r"<p:grpSp>(?:(?!<p:grpSp>).)*?</p:grpSp>", group, x, flags=re.S)

        def lone(m):
            nonlocal converted, left, changed, clipped
            sp = m.group(0)
            if "<a:blipFill" not in sp or "<a:custGeom" not in sp:
                return sp
            if not convertible(sp):
                left += 1
                return sp
            attrs, off, ext = _xfrm(sp)
            converted += 1
            clipped += not _rect_path(sp)
            changed = True
            return _pic_from(sp, off, ext, attrs)
        # ungrouped shapes only: skip any <p:sp> that sits inside a remaining group
        out, pos, depth_tokens = [], 0, re.finditer(r"<p:grpSp>|</p:grpSp>|<p:sp>.*?</p:sp>", x2, re.S)
        depth = 0
        for tok in depth_tokens:
            s = tok.group(0)
            if s == "<p:grpSp>":
                depth += 1
            elif s == "</p:grpSp>":
                depth -= 1
            elif depth == 0:
                out.append(x2[pos:tok.start()])
                out.append(lone(tok))
                pos = tok.end()
            elif "<a:blipFill" in s and "<a:custGeom" in s:
                left += 1
        out.append(x2[pos:])
        x3 = "".join(out)
        if changed:
            pkg.put(n, x3)
    rep["images"] = {"freeforms converted to p:pic": converted, "of which cut-outs with a non-rectangular outline": clipped, "freeforms left (not a plain rectangle, grouped with others, rotated group)": left}


def contrast(pkg, rep):
    fixed = left = 0
    for n in pkg.names(r"ppt/slides/slide\d+\.xml"):
        x = pkg.text(n)
        lx, mx, theme_c, cmap = layout.slide_context(pkg.parts, n)
        fails, _, _ = layout.contrast_findings(x, lx, mx, theme_c, cmap)
        for f in fails:
            target = 4.6 if f["need"] == 4.5 else 3.1
            new = layout.adjust(f["fg"], f["bg"], target)
            if not new or f["run"] not in x:
                left += 1
                continue
            run2 = re.sub(r'(<a:rPr\b[^>]*>\s*<a:solidFill>\s*<a:srgbClr val=")%s(")' % f["fg"], r"\g<1>%s\2" % new, f["run"], count=1, flags=re.I)
            if run2 == f["run"]:  # colour came from a theme entry, not a literal: not changed here
                left += 1
                continue
            x = x.replace(f["run"], run2, 1)
            fixed += 1
        if fails:
            pkg.put(n, x)
    rep["contrast"] = {"text runs recoloured": fixed, "failing runs left (theme colour or no solution)": left}


def fit(pkg, rep):
    total = {"boxes widened": 0, "wrapping switched off": 0, "boxes heightened": 0, "left (no room)": 0}
    sld = re.search(r'<p:sldSz cx="(\d+)" cy="(\d+)"', pkg.get_text("ppt/presentation.xml"))
    if not sld:
        rep["fit"] = {"skipped": "no slide size"}
        return
    W, H = int(sld.group(1)), int(sld.group(2))
    for n in pkg.names(r"ppt/slides/slide\d+\.xml"):
        x = pkg.text(n)
        x2, c = layout.fit_fix(x, W, H)
        for k, v in c.items():
            total[k] += v
        if x2 != x:
            pkg.put(n, x2)
    rep["fit"] = total


def props(pkg, spec, rep):
    kv = dict(p.split("=", 1) for p in spec.split(",") if "=" in p)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    want_date = kv.get("date")
    if want_date == "today":
        want_date = today
    elif want_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", want_date):
        want_date += "T00:00:00Z"
    out = {}
    if "docProps/core.xml" in pkg.parts:
        x = pkg.text("docProps/core.xml")
        if kv.get("author"):
            a = escape(kv["author"], quote=False)
            for tag in ("dc:creator", "cp:lastModifiedBy"):
                if re.search(r"<%s\b" % tag, x):
                    x = re.sub(r"<%s\b([^>]*)>.*?</%s>|<%s\b([^>]*)/>" % (tag, tag, tag),
                               lambda m: "<%s%s>%s</%s>" % (tag, m.group(1) or m.group(2) or "", a, tag), x, count=1, flags=re.S)
                else:
                    x = x.replace("</cp:coreProperties>", f"<{tag}>{a}</{tag}></cp:coreProperties>")
                out[tag] = kv["author"]

        def date(m):
            open_tag, tag, val = m.group(1), m.group(2), m.group(3)
            year = int(val[:4]) if val[:4].isdigit() else 0
            stale = year in (2006, 2011) or val > today
            if want_date or stale:
                out[tag] = want_date or today
                return f"{open_tag}{want_date or today}</{tag}>"
            return m.group(0)
        x = re.sub(r"(<(dcterms:(?:created|modified))\b[^>]*>)([^<]*)</\2>", date, x)
        x2 = re.sub(r"<dc:identifier>.*?</dc:identifier>|<dc:identifier\s*/>", "", x, flags=re.S)
        if x2 != x:
            out["dc:identifier"] = "removed"
        pkg.put("docProps/core.xml", x2)
    if "docProps/app.xml" in pkg.parts:
        x = pkg.text("docProps/app.xml")
        if pkg.kind == "pptx":
            counts = {"Slides": len(pkg.names(r"ppt/slides/slide\d+\.xml")), "Notes": len(pkg.names(r"ppt/notesSlides/notesSlide\d+\.xml"))}
            counts["Words"] = len(unescape(" ".join(re.findall(r"<a:t>(.*?)</a:t>", " ".join(
                pkg.text(n) for n in pkg.names(r"ppt/slides/slide\d+\.xml")), re.S))).split())
        else:
            counts = {"Words": len(unescape(" ".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", pkg.text("word/document.xml"), re.S))).split())}
        sld = re.search(r'<p:sldSz cx="(\d+)" cy="(\d+)"', pkg.get_text("ppt/presentation.xml")) if pkg.kind == "pptx" else None
        if sld:
            ratio = int(sld.group(1)) / int(sld.group(2))
            label = "Widescreen" if abs(ratio - 16 / 9) < 0.02 else "On-screen Show (4:3)" if abs(ratio - 4 / 3) < 0.02 else "Custom"
            cur = re.search(r"<PresentationFormat>([^<]*)<", x)
            wrong = cur and ((label == "Widescreen" and "4:3" in cur.group(1)) or (label.startswith("On-screen") and "Widescreen" in cur.group(1))
                             or (label == "Custom" and cur.group(1) not in ("Custom", "")))
            if wrong:
                x = x.replace(cur.group(0), f"<PresentationFormat>{label}</PresentationFormat>")
                out["PresentationFormat"] = f"{cur.group(1)} -> {label}"
        for tag, v in counts.items():
            if re.search(r"<%s>\d*</%s>" % (tag, tag), x):
                cur = re.search(r"<%s>(\d*)</%s>" % (tag, tag), x).group(1)
                if cur != str(v):
                    x = re.sub(r"<%s>\d*</%s>" % (tag, tag), "<%s>%d</%s>" % (tag, v, tag), x)
                    out[tag] = f"{cur or 'empty'} -> {v}"
        pkg.put("docProps/app.xml", x)
    rep["props"] = out or {"changed": "nothing (no placeholder dates, counters already right, no author given)"}


def report_notes(pkg, rep):
    rules = [r for r in patterns.load_rules("review") if r["kind"] in ("residue", "token")]
    found = []
    for n in sorted(pkg.names(r"ppt/notesSlides/notesSlide\d+\.xml|word/comments\.xml|ppt/comments/[^/]+\.xml")):
        for p in re.findall(r"<(?:a|w):p[ >].*?</(?:a|w):p>", pkg.text(n), re.S):
            t = unescape(re.sub(r"<[^>]+>", "", p)).strip()
            if t and any(r["rx"].search(t) for r in rules):
                found.append(f"{n}: {t[:80]}")
    rep["report-notes"] = {"generator-facing notes": len(found), "examples": found[:5]}


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"):
        sys.exit(__doc__)
    src = Path(a[0])
    out = Path(a[a.index("--out") + 1]) if "--out" in a else None
    if out and out.exists():
        sys.exit("exists, not overwriting: " + str(out))
    if out and out.resolve() == src.resolve():
        sys.exit("--out must differ from the input")
    pkg = Package(src)
    rep = {}
    if "--round-sizes" in a:
        if pkg.kind != "pptx":
            sys.exit("--round-sizes is for .pptx")
        round_sizes(pkg, rep)
    if "--rename-font" in a:
        i = a.index("--rename-font")
        rename_font(pkg, a[i + 1], a[i + 2], "--bold" in a, rep)
    if "--normalize-fonts" in a:
        normalize_fonts(pkg, rep)
    if "--strip-embedded-fonts" in a:
        strip_embedded_fonts(pkg, rep)
    if "--bullets" in a:
        n = bullets_pptx(pkg) if pkg.kind == "pptx" else bullets_docx(pkg)
        rep["bullets"] = {"typed bullets converted": n}
    if "--images" in a:
        if pkg.kind != "pptx":
            sys.exit("--images is for .pptx")
        images(pkg, rep, "--allow-clipped" in a)
    if "--fit" in a:
        if pkg.kind != "pptx":
            sys.exit("--fit is for .pptx")
        fit(pkg, rep)
    if "--contrast" in a:
        if pkg.kind != "pptx":
            sys.exit("--contrast is for .pptx")
        contrast(pkg, rep)
    if "--props" in a:
        props(pkg, a[a.index("--props") + 1], rep)
    if "--report-notes" in a:
        report_notes(pkg, rep)
    if pkg.skipped:
        rep["skipped"] = {"parts not in UTF-8, left untouched": len(pkg.skipped), "examples": pkg.skipped[:5]}
    if not rep or set(rep) == {"skipped"}:
        sys.exit("nothing to do: give at least one fix flag\n" + __doc__)
    if out:
        pkg.write(out, src)
    if "--json" in a:
        print(json.dumps({"file": str(src), "written": str(out) if out else None, "fixes": rep}, indent=2, ensure_ascii=False))
        return
    print(("wrote " + str(out)) if out else "dry run (no --out): nothing written")
    for k, v in rep.items():
        print(f"{k}: " + ", ".join(f"{kk}={vv}" for kk, vv in v.items()))


if __name__ == "__main__":
    patterns.guard(main)
