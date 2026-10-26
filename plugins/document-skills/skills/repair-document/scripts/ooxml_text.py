"""Part of repair-document. Estimate how much room text needs, without rendering. Standard library only.

Widths are the Helvetica / Arial advance widths (the AFM tables, 1000 units per em), regular and bold, scaled by a factor per
font family for the common non-Arial families. They are estimates: no kerning, no hinting, no ligatures. The use is to find
text boxes with no slack (text that fits only by luck and wraps, or breaks inside a word, in another renderer) and boxes
that are too short for their text, never to claim a pixel-exact layout.
"""
import re

_REG = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556,
        556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833,
        722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556,
        556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334,
        260, 334, 584]
_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556,
         556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833,
         722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611,
         556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389,
         280, 389, 584]
FAMILY_FACTOR = {  # relative to Arial; rough, from typical average character widths
    "times new roman": 0.90, "times": 0.90, "georgia": 1.07, "century gothic": 1.12, "verdana": 1.18, "tahoma": 1.02,
    "calibri": 0.90, "cambria": 0.97, "courier new": 1.08, "trebuchet ms": 1.0, "segoe ui": 0.98, "comic sans ms": 1.15,
    "impact": 0.85, "consolas": 1.0, "palatino linotype": 0.97, "garamond": 0.82, "aptos": 0.97, "aptos display": 0.97,
}
LINE_HEIGHT = 1.2  # of the font size, single spacing


def char_units(ch, bold):
    o = ord(ch)
    if 32 <= o <= 126:
        return (_BOLD if bold else _REG)[o - 32]
    if 0x2E80 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0x3040 <= o <= 0x30FF:
        return 1000
    if ch in "‘’":
        return 222 if not bold else 278
    if ch in "“”":
        return 333 if not bold else 500
    if ch in "–":
        return 556
    if ch in "—":
        return 1000
    return 600 if bold else 556


def width_pt(text, size_pt, bold=False, family=""):
    """Estimated width of `text` in points on one line."""
    f = FAMILY_FACTOR.get(family.lower(), 1.0)
    return sum(char_units(c, bold) for c in text) * size_pt * f / 1000.0


def words_of(runs):
    """Split [(text, size_pt, bold, family)] runs into words: [(word, trailing_space_width_pt, width_pt)]."""
    out, cur, cur_w = [], "", 0.0
    for text, size, bold, fam in runs:
        for ch in text:
            if ch == " ":
                if cur:
                    out.append([cur, width_pt(" ", size, bold, fam), cur_w])
                    cur, cur_w = "", 0.0
                elif out:
                    out[-1][1] += width_pt(" ", size, bold, fam)
            else:
                cur += ch
                cur_w += width_pt(ch, size, bold, fam)
    if cur:
        out.append([cur, 0.0, cur_w])
    return out


def wrap(runs, avail_pt):
    """Greedy word wrap. Returns (lines, longest_word_pt, widest_line_pt, broke_inside_word)."""
    words = words_of(runs)
    if not words:
        return 0, 0.0, 0.0, False
    lines, line_w, widest, longest, broke = 1, 0.0, 0.0, 0.0, False
    for word, space, w in words:
        longest = max(longest, w)
        if w > avail_pt:
            broke = True
        if line_w and line_w + w > avail_pt:
            widest = max(widest, line_w)
            lines += 1
            line_w = 0.0
        line_w += w + space
    widest = max(widest, line_w - (words[-1][1] if words else 0))
    return lines, longest, widest, broke


def parse_paragraphs(shape_xml):
    """[(runs, line_spacing_factor, space_before_pt)] for each paragraph of a shape, with sizes in points."""
    paras = []
    default = re.search(r'<a:defRPr\b[^>]*\bsz="(\d+)"', shape_xml)
    for p in re.findall(r"<a:p>.*?</a:p>|<a:p\s[^>]*>.*?</a:p>", shape_xml, re.S):
        runs = []
        for r in re.findall(r"<a:r>.*?</a:r>", p, re.S):
            rpr = re.search(r"<a:rPr\b([^>]*)", r)
            attrs = rpr.group(1) if rpr else ""
            sz = re.search(r'\bsz="(\d+)"', attrs)
            size = int(sz.group(1)) / 100 if sz else (int(default.group(1)) / 100 if default else 18.0)
            bold = re.search(r'\bb="(1|true)"', attrs) is not None
            fam = re.search(r'<a:latin typeface="([^"]*)"', r)
            t = re.search(r"<a:t>(.*?)</a:t>", r, re.S)
            if t:
                from html import unescape
                runs.append((unescape(t.group(1)), size, bold, fam.group(1) if fam else ""))
        pct = re.search(r"<a:lnSpc>\s*<a:spcPct val=\"(\d+)\"", p)
        pts = re.search(r"<a:lnSpc>\s*<a:spcPts val=\"(\d+)\"", p)
        paras.append((runs, int(pct.group(1)) / 100000 if pct else 1.0, int(pts.group(1)) / 100 if pts else None))
    return paras


def measure_shape(shape_xml, box_w_emu, box_h_emu):
    """Dict with the shape's estimated needs: required width for its widest unbreakable unit, line count, height."""
    ins = {k: int(v) for k, v in re.findall(r'\b([lr]Ins)="(\d+)"', re.search(r"<a:bodyPr[^>]*>", shape_xml).group(0))} if "<a:bodyPr" in shape_xml else {}
    tins = {k: int(v) for k, v in re.findall(r'\b([tb]Ins)="(\d+)"', re.search(r"<a:bodyPr[^>]*>", shape_xml).group(0))} if "<a:bodyPr" in shape_xml else {}
    left, right = ins.get("lIns", 91440), ins.get("rIns", 91440)
    top, bottom = tins.get("tIns", 45720), tins.get("bIns", 45720)
    avail = (box_w_emu - left - right) / 12700.0  # points
    need_single, tall, lines_total, broke = 0.0, 0.0, 0, False
    single_line_paras = 0
    for runs, spacing, fixed in parse_paragraphs(shape_xml):
        if not runs or not "".join(r[0] for r in runs).strip():
            continue
        lines, longest, widest, b = wrap(runs, avail)
        size = max(r[1] for r in runs)
        ws = words_of(runs)
        words_w = sum(w[2] + w[1] for w in ws) - (ws[-1][1] if ws else 0)
        if lines == 2 and words_w <= avail * 1.08 and len(ws) <= 8 and not b:
            lines = 1  # sized for one line (a title or label) and only a hair too wide: that is a box with no slack
        if lines == 1:
            single_line_paras += 1
            need_single = max(need_single, words_w)
        need_single = max(need_single, longest)
        broke = broke or b
        lh = fixed if fixed else size * LINE_HEIGHT * spacing
        tall += lines * lh
        lines_total += lines
    need_w = need_single
    return {"avail_pt": avail, "need_pt": need_w, "slack_pct": (100.0 * (avail - need_w) / avail) if avail > 0 and need_w else 100.0,
            "lines": lines_total, "height_pt": tall + (top + bottom) / 12700.0, "box_h_pt": box_h_emu / 12700.0,
            "broke_inside_word": broke, "insets_emu": (left, right), "single_line_paras": single_line_paras}
