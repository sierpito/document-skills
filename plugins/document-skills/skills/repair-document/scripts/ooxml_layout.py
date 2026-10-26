"""Part of repair-document. Static geometry and colour helpers for .pptx slides (no rendering needed).

Imported by ooxml_inspect.py (report) and ooxml_fix.py (repair). Standard library only. Works on raw XML text.
Limits, on purpose: shapes inside groups, rotated shapes and placeholders without their own xfrm are skipped;
theme colours with luminance/tint/alpha modifiers and gradient or picture fills are treated as unknown, never guessed.
"""
import colorsys, re

EMU_IN = 914400
SCHEME_BG = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}


def luminance(hexcol):
    c = [int(hexcol[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(fg, bg):
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def darken(hexcol, bg, target=4.6):
    """Darken along the hue (HLS lightness) until contrast against bg reaches target; None if impossible."""
    r, g, b = [int(hexcol[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    fmt = lambda lt: "%02X%02X%02X" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, lt, s))
    if ratio(fmt(0.0), bg) < target:
        return None
    lo, hi = 0.0, l
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ratio(fmt(mid), bg) >= target else (lo, mid)
    return fmt(lo)


def theme_colors(theme_xml):
    out = {}
    m = re.search(r"<a:clrScheme\b.*?</a:clrScheme>", theme_xml, re.S)
    if not m:
        return out
    for name, body in re.findall(r"<a:(dk1|lt1|dk2|lt2|accent[1-6]|hlink|folHlink)>(.*?)</a:\1>", m.group(0), re.S):
        c = re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', body) or re.search(r'lastClr="([0-9A-Fa-f]{6})"', body)
        if c:
            out[name] = c.group(1).upper()
    return out


def clr_map(master_xml):
    m = re.search(r"<p:clrMap\b([^>]*)/>", master_xml)
    pairs = dict(re.findall(r'(\w+)="(\w+)"', m.group(1))) if m else {}
    return {k: v for k, v in pairs.items() if k in ("bg1", "tx1", "bg2", "tx2")}


def resolve(color_xml, theme, cmap):
    """Hex for a colour element body, or None when it uses modifiers or an unknown scheme colour."""
    if re.search(r"<a:(lumMod|lumOff|tint|shade|alpha|satMod|hueMod)\b", color_xml):
        return None
    m = re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', color_xml)
    if m:
        return m.group(1).upper()
    m = re.search(r'<a:schemeClr val="(\w+)"', color_xml)
    if m:
        v = m.group(1)
        v = cmap.get(v, SCHEME_BG.get(v, v))
        return theme.get(v)
    return None


def solid_fill(xml_part):
    """First top-level solidFill body in a spPr / bgPr / rPr fragment, else None."""
    m = re.search(r"<a:solidFill>(.*?)</a:solidFill>", xml_part, re.S)
    return m.group(1) if m else None


def slide_background(slide_xml, layout_xml, master_xml, theme, cmap):
    for x in (slide_xml, layout_xml, master_xml):
        m = re.search(r"<p:bg>(.*?)</p:bg>", x or "", re.S)
        if not m:
            continue
        fill = solid_fill(m.group(1))
        if fill is not None:
            return resolve(fill, theme, cmap)
        if re.search(r"<a:(gradFill|blipFill|pattFill)", m.group(1)):
            return None
        ref = re.search(r"<p:bgRef\b[^>]*>(.*?)</p:bgRef>", m.group(1), re.S)
        if ref:
            return resolve(ref.group(1), theme, cmap)
    return theme.get("lt1", "FFFFFF")


def top_level_shapes(slide_xml):
    """(shape_xml, rect or None, rot) for p:sp elements that are not inside a group; rect in EMU (x, y, cx, cy)."""
    out, depth = [], 0
    for tok in re.finditer(r"<p:grpSp>|</p:grpSp>|<p:sp>.*?</p:sp>", slide_xml, re.S):
        s = tok.group(0)
        if s == "<p:grpSp>":
            depth += 1
        elif s == "</p:grpSp>":
            depth -= 1
        elif depth == 0:
            m = re.search(r'<a:xfrm\b([^>]*)>\s*<a:off x="(-?\d+)" y="(-?\d+)"\s*/>\s*<a:ext cx="(\d+)" cy="(\d+)"', s)
            rot = re.search(r'rot="(-?\d+)"', m.group(1)) if m else None
            out.append((s, tuple(int(v) for v in m.groups()[1:]) if m else None, int(rot.group(1)) if rot else 0))
    return out


def shape_text(shape_xml):
    return " ".join(t.strip() for t in re.findall(r"<a:t>(.*?)</a:t>", shape_xml, re.S) if t.strip())


def geometry_findings(slide_xml, width, height):
    """Off-canvas text shapes and overlapping text boxes among ungrouped, unrotated shapes with their own xfrm."""
    boxes = [(shape_text(s), r) for s, r, rot in top_level_shapes(slide_xml) if r and rot == 0 and "<p:txBody>" in s and shape_text(s)]
    off, over = [], []
    tol = 0.02
    for text, (x, y, cx, cy) in boxes:
        if x < -tol * width or y < -tol * height or x + cx > width * (1 + tol) or y + cy > height * (1 + tol):
            off.append(text[:40])
    min_overlap = EMU_IN * 0.05
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ta, a), (tb, b) = boxes[i], boxes[j]
            w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
            h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            if w > min_overlap and h > min_overlap:
                over.append(f"{ta[:25]!r} / {tb[:25]!r}")
    return off, over


def _fill_kind(sp_xml, theme, cmap):
    """('solid', hex|None), ('image', None) or (None, None) for the shape's own fill."""
    if sp_xml.startswith("<p:pic"):
        return "image", None
    sp_pr = re.search(r"<p:spPr>(.*?)</p:spPr>", sp_xml, re.S)
    if not sp_pr:
        return None, None
    body = re.sub(r"<a:ln\b.*?</a:ln>", "", sp_pr.group(1), flags=re.S)
    if re.search(r"<a:(blipFill|gradFill|pattFill)", body):
        return "image", None
    fill = solid_fill(body)
    return ("solid", resolve(fill, theme, cmap)) if fill is not None else (None, None)


def contrast_runs(slide_xml, layout_xml, master_xml, theme, cmap):
    """Every text run with an explicit colour and a known background: (run_xml, fg, bg, need), plus a skipped count.
    Returns (runs, skipped).

    Behind a text box: the last earlier shape that covers most of it (a solid fill is used; a picture or gradient
    makes the background unknown and the box is skipped), else the slide background. Slides with groups that hold
    filled shapes or pictures are skipped entirely, because their extents are not resolved here."""
    page_bg = slide_background(slide_xml, layout_xml, master_xml, theme, cmap)
    # a group holding a filled shape or a picture can be what the text sits on; its extent is not resolved here
    grouped_images = any(re.search(r"<p:spPr>(?:(?!</p:spPr>).)*?<a:(solidFill|blipFill|gradFill)", g, re.S) or "<p:pic" in g
                         for g in re.findall(r"<p:grpSp>.*?</p:grpSp>", slide_xml, re.S))
    # z-order list of everything that can sit behind text, including top-level pictures
    items = []
    for m in re.finditer(r"<p:pic>.*?</p:pic>|<p:sp>.*?</p:sp>", re.sub(r"<p:grpSp>.*?</p:grpSp>", "", slide_xml, flags=re.S), re.S):
        s = m.group(0)
        mm = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"\s*/>\s*<a:ext cx="(\d+)" cy="(\d+)"', s)
        items.append((s, tuple(int(v) for v in mm.groups()) if mm else None))
    runs, skipped = [], 0
    for idx, (shape, rect) in enumerate(items):
        if not shape.startswith("<p:sp>") or "<p:txBody>" not in shape or not rect or not shape_text(shape):
            continue
        if grouped_images:
            skipped += 1
            continue
        bg, unknown = page_bg, False
        kind, hexcol = _fill_kind(shape, theme, cmap)
        if kind == "solid":
            bg = hexcol
        elif kind == "image":
            unknown = True
        else:
            x, y, cx, cy = rect
            area = max(cx * cy, 1)
            for other, orect in reversed(items[:idx]):
                if not orect:
                    continue
                ox, oy, ocx, ocy = orect
                w = min(x + cx, ox + ocx) - max(x, ox)
                h = min(y + cy, oy + ocy) - max(y, oy)
                if w > 0 and h > 0 and w * h >= 0.6 * area:
                    k, c = _fill_kind(other, theme, cmap)
                    if k == "solid":
                        bg = c
                        break
                    if k == "image":
                        unknown = True
                        break
        if unknown or not bg:
            skipped += 1
            continue
        for run in re.findall(r"<a:r>.*?</a:r>", shape, re.S):
            rpr = re.search(r"<a:rPr\b([^>]*)>(.*?)</a:rPr>", run, re.S)
            text = re.search(r"<a:t>(.*?)</a:t>", run, re.S)
            if not rpr or not text or not text.group(1).strip():
                continue
            fill = solid_fill(rpr.group(2))
            fg = resolve(fill, theme, cmap) if fill is not None else None
            if not fg:
                continue
            sz = re.search(r'\bsz="(\d+)"', rpr.group(1))
            size = int(sz.group(1)) if sz else 1800
            bold = re.search(r'\bb="(1|true)"', rpr.group(1)) is not None
            need = 3.0 if (size >= 1800 or (size >= 1400 and bold)) else 4.5
            runs.append((run, fg, bg, need))
    return runs, skipped


def contrast_findings(slide_xml, layout_xml, master_xml, theme, cmap):
    """Text runs whose explicit colour fails WCAG against what is behind them. Returns (fails, checked, skipped)."""
    runs, skipped = contrast_runs(slide_xml, layout_xml, master_xml, theme, cmap)
    fails = []
    for run, fg, bg, need in runs:
        r = ratio(fg, bg)
        if r < need:
            text = re.search(r"<a:t>(.*?)</a:t>", run, re.S).group(1)
            fails.append({"text": text[:30], "fg": fg, "bg": bg, "ratio": round(r, 2), "need": need, "run": run})
    return fails, len(runs), skipped


def adjust(hexcol, bg, target=4.6):
    """Move a colour along its hue until it reaches `target` contrast on bg: darker on a light bg, lighter on a dark one."""
    r, g, b = [int(hexcol[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    fmt = lambda lt: "%02X%02X%02X" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, lt, s))
    light_bg = luminance(bg) > 0.18
    end = 0.0 if light_bg else 1.0
    if ratio(fmt(end), bg) < target:
        return None
    lo, hi = (l, end)
    for _ in range(40):
        mid = (lo + hi) / 2
        if ratio(fmt(mid), bg) >= target:
            hi = mid
        else:
            lo = mid
    return fmt(hi)


def rel_target(parts, part, kind):
    """Resolved part name of the first relationship of type .../<kind> from `part`, using the package's parts dict."""
    import posixpath
    d, n = part.rsplit("/", 1)
    rels = parts.get(f"{d}/_rels/{n}.rels")
    if not rels:
        return None
    m = re.search(r'<Relationship\b[^>]*Type="[^"]*/%s"[^>]*>' % kind, rels.decode("utf8", "replace"))
    t = re.search(r'Target="([^"]+)"', m.group(0)) if m else None
    return posixpath.normpath(posixpath.join(d, t.group(1))) if t else None


def slide_context(parts, slide):
    """(layout_xml, master_xml, theme_colours, colour_map) for a slide, from the package's parts dict."""
    get = lambda n: parts[n].decode("utf8", "replace") if n and n in parts else ""
    lay = rel_target(parts, slide, "slideLayout")
    mas = rel_target(parts, lay, "slideMaster") if lay else None
    th = rel_target(parts, mas, "theme") if mas else None
    return get(lay), get(mas), theme_colors(get(th)), clr_map(get(mas))


# ---------------------------------------------------------------- text fit (estimated from font metrics, see ooxml_text.py)
def _fit_shapes(slide_xml):
    """Top-level, unrotated text shapes with their own transform: (shape_xml, (x, y, cx, cy), span in the slide xml)."""
    import ooxml_text as T
    out, depth = [], 0
    for tok in re.finditer(r"<p:grpSp>|</p:grpSp>|<p:sp>.*?</p:sp>", slide_xml, re.S):
        s = tok.group(0)
        if s == "<p:grpSp>":
            depth += 1
        elif s == "</p:grpSp>":
            depth -= 1
        elif depth == 0 and "<p:txBody>" in s and shape_text(s):
            m = re.search(r'<a:xfrm\b([^>]*)>\s*<a:off x="(-?\d+)" y="(-?\d+)"\s*/>\s*<a:ext cx="(\d+)" cy="(\d+)"', s)
            body = re.search(r"<a:bodyPr[^>]*>", s)
            if not m or re.search(r'rot="(?!0")', m.group(1)) or (body and 'wrap="none"' in body.group(0)):
                continue
            out.append((s, tuple(int(v) for v in m.groups()[1:]), tok.span()))
    return out


def fit_findings(slide_xml, slack_min=3.0):
    """Boxes whose text has no slack (it wraps, or breaks inside a word, if a renderer measures a hair wider) and boxes shorter
    than their text. Estimates from Arial metrics; confirm in a render."""
    import ooxml_text as T
    found = []
    for s, (x, y, cx, cy), _ in _fit_shapes(slide_xml):
        m = T.measure_shape(s, cx, cy)
        if not m["need_pt"]:
            continue
        text = shape_text(s)[:40]
        if m["slack_pct"] < slack_min or m["broke_inside_word"]:
            found.append({"kind": "no slack", "text": text, "need_pt": round(m["need_pt"], 1), "avail_pt": round(m["avail_pt"], 1),
                          "slack_pct": round(m["slack_pct"], 1), "rect": (x, y, cx, cy)})
        elif m["height_pt"] > m["box_h_pt"] * 1.05 and m["lines"] > 1:
            found.append({"kind": "short box", "text": text, "need_pt": round(m["height_pt"], 1), "avail_pt": round(m["box_h_pt"], 1),
                          "slack_pct": round(100 * (m["box_h_pt"] - m["height_pt"]) / m["box_h_pt"], 1), "rect": (x, y, cx, cy)})
    return found


def _bounds(items, idx, W, H):
    """Free room around shape idx: (left_limit, right_limit, bottom_limit) in EMU, from the other top-level shapes."""
    x, y, cx, cy = items[idx][1]
    margin, gap = 274320, 91440
    left, right, bottom = margin, W - margin, H - margin
    for j, (_, r, _) in enumerate(items):
        if j == idx:
            continue
        ox, oy, ocx, ocy = r
        vert = min(y + cy, oy + ocy) - max(y, oy) > 0
        horiz = min(x + cx, ox + ocx) - max(x, ox) > 0
        if vert and ox >= x + cx - 1:
            right = min(right, ox - gap)
        if vert and ox + ocx <= x + 1:
            left = max(left, ox + ocx + gap)
        if horiz and oy >= y + cy - 1:
            bottom = min(bottom, oy - gap)
    return left, right, bottom


def fit_fix(slide_xml, W, H):
    """Widen boxes with no slack by ~12% into free space (growing the side the text is aligned away from), switch wrapping off
    for a single-line title that still cannot fit, and heighten short boxes into free space below. Returns (xml, counts)."""
    import ooxml_text as T
    counts = {"boxes widened": 0, "wrapping switched off": 0, "boxes heightened": 0, "left (no room)": 0}
    items = [(s, r, span) for s, r, span in _fit_shapes(slide_xml)]
    # also let pictures and shapes without text count as neighbours
    others = []
    for m in re.finditer(r"<p:pic>.*?</p:pic>|<p:sp>.*?</p:sp>", re.sub(r"<p:grpSp>.*?</p:grpSp>", "", slide_xml, flags=re.S), re.S):
        mm = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"\s*/>\s*<a:ext cx="(\d+)" cy="(\d+)"', m.group(0))
        if mm and m.group(0) not in [i[0] for i in items]:
            others.append((m.group(0), tuple(int(v) for v in mm.groups()), None))
    depth = 0
    for tok in re.finditer(r"<p:grpSp>|</p:grpSp>|<p:grpSpPr>.*?</p:grpSpPr>", slide_xml, re.S):  # top-level groups are neighbours too
        s = tok.group(0)
        if s == "<p:grpSp>":
            depth += 1
        elif s == "</p:grpSp>":
            depth -= 1
        elif depth == 1:
            mm = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"\s*/>\s*<a:ext cx="(\d+)" cy="(\d+)"', s)
            if mm:
                others.append((s, tuple(int(v) for v in mm.groups()), None))
    allitems = items + others
    edits = []
    for idx, (s, (x, y, cx, cy), span) in enumerate(items):
        m = T.measure_shape(s, cx, cy)
        if not m["need_pt"]:
            continue
        lins, rins = m["insets_emu"]
        new_x, new_cx, new_cy, new_s = x, cx, cy, s
        left, right, bottom = _bounds(allitems, idx, W, H)
        if m["slack_pct"] < 3.0 or m["broke_inside_word"]:
            want = int(m["need_pt"] * 12700 * 1.12) + lins + rins
            algn = re.search(r'<a:pPr\b[^>]*\balgn="(\w+)"', s)
            a = algn.group(1) if algn else "l"
            grow = want - cx
            if a == "ctr":
                room = min(x - left, (right - (x + cx))) * 2
                grow = min(grow, max(room, 0))
                new_x, new_cx = x - grow // 2, cx + grow
            elif a == "r":
                grow = min(grow, max(x - left, 0))
                new_x, new_cx = x - grow, cx + grow
            else:
                grow = min(grow, max(right - (x + cx), 0))
                new_cx = cx + grow
            if grow > 0:
                counts["boxes widened"] += 1
            probe = T.measure_shape(s, new_cx, cy)
            if (probe["slack_pct"] < 3.0 or probe["broke_inside_word"]) and m["single_line_paras"] == 1 and len(T.parse_paragraphs(s)) == 1:
                new_s = re.sub(r"<a:bodyPr\b", '<a:bodyPr wrap="none"', new_s, count=1) if 'wrap=' not in new_s.split("</a:bodyPr>")[0].split("<a:bodyPr")[1] else new_s
                counts["wrapping switched off"] += 1
            elif probe["slack_pct"] < 0:
                counts["left (no room)"] += 1
        elif m["height_pt"] > m["box_h_pt"] * 1.05 and m["lines"] > 1:
            want_h = int(m["height_pt"] * 12700 * 1.03)
            room = bottom - (y + cy)
            if room > 0:
                new_cy = min(want_h, cy + room)
                counts["boxes heightened"] += 1
            if new_cy < want_h:
                counts["left (no room)"] += 1
        if (new_x, new_cx, new_cy) != (x, cx, cy) or new_s != s:
            new_s = re.sub(r'(<a:off x=")-?\d+(" y="-?\d+"\s*/>\s*<a:ext cx=")\d+(" cy=")\d+', lambda mm: f"{mm.group(1)}{new_x}{mm.group(2)}{new_cx}{mm.group(3)}{new_cy}", new_s, count=1)
            edits.append((span, new_s))
    for (a, b), new in sorted(edits, reverse=True):
        slide_xml = slide_xml[:a] + new + slide_xml[b:]
    return slide_xml, counts
