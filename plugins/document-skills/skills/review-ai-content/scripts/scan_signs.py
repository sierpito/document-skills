#!/usr/bin/env python3
"""Part of review-ai-content. Counts AI-content signs in a document and estimates the AI-looking share.

Read-only: stdlib only, no network. Writes nothing unless --out is given (a new .md report; never
overwrites). A judgement from signals, not detector proof.

Usage: scan_signs.py FILE [--json] [--media] [--out REPORT.md]
  --media  also read image provenance markers in word/media and ppt/media (docx/pptx)
Rules and helpers come from ../../../shared/patterns.{json,py} (shared with repair-document/scripts/prose_tells.py).
"""
import json, re, statistics, subprocess, sys
from datetime import date
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
try:
    import patterns  # shared rules and helpers
    import mdtable
except ModuleNotFoundError:
    sys.exit("needs shared/patterns.py from the document-skills plugin root; run this script from the installed plugin")
from patterns import DISCLOSURE, QUOTE  # noqa: E402

KIND_SCORE = {"residue": 3, "token": 3, "glyph": 2, "format": 2, "tool": 0, "style": 1}
STRONG = {"residue", "token", "glyph", "format"}  # score by weight; style signs add 1 per distinct rule
TOOL_META = re.compile(r"(chatgpt|openai|claude|anthropic|gemini|copilot|midjourney)", re.I)
REF_HEAD = re.compile(
    r"^[\s#*_>]*(references?( list)?|bibliography|works cited|sources|literature|further reading|notes and references)[\s*_:.]*$", re.I)
QUOTE_STYLES = ("Quote", "BlockText", "IntenseQuote", "Block Text", "Intense Quote")
MEDIA_MARKERS = [  # (label, bytes) searched in image files
    ("C2PA/JUMBF manifest", b"c2pa"), ("C2PA/JUMBF manifest", b"jumb"),
    ("IPTC DigitalSourceType", b"DigitalSourceType"), ("trainedAlgorithmicMedia", b"trainedAlgorithmicMedia"),
    ("generation prompt chunk", b"parameters\x00"), ("generator stamp", b"Midjourney"),
    ("generator stamp", b"DALL"), ("generator stamp", b"Stable Diffusion"),
]
MEDIA_NAMES = re.compile(r"(chatgpt image|dall-?e|midjourney|gemini_generated|firefly|stable.?diffusion)", re.I)


def words(t):
    return len(re.findall(r"\w+", t))


def strip_xml(x):
    return unescape(re.sub(r"<[^>]+>", "", x))


def units_from_ooxml(z, pattern, para, run, skip_styles=()):
    out = []
    for name in sorted(n for n in z.namelist() if re.fullmatch(pattern, n)):
        x = z.read(name).decode("utf8", "replace")
        for k, p in enumerate(re.findall(para, x, re.S), 1):
            if skip_styles and re.search(r'<w:pStyle w:val="(%s)"' % "|".join(skip_styles), p):
                continue  # block quotes are someone else's wording
            p = re.sub(r"<a:fld\b.*?</a:fld>", "", p, flags=re.S)  # date and slide-number fields hold stale cached text ("1.7.2013", "‹#›")
            t = strip_xml("".join(re.findall(run, p, re.S)))
            if t.strip():
                out.append((f"{name} ¶{k}", t.strip()))
    return out


def load(path):
    """Return (units, meta_text, rich, zip_or_None); units = [(where, text)]."""
    ext = path.suffix.lower()
    if ext in (".md", ".txt", ".markdown"):
        raw = path.read_text(encoding="utf8", errors="replace")
        raw = re.sub(r"\A---\n.*?\n---\n", "", raw, flags=re.S)
        raw = re.sub(r"```.*?```", "", raw, flags=re.S)
        raw = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith(">"))
        paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
        return [(f"para {i+1}", p) for i, p in enumerate(paras)], "", False, None
    if ext in (".html", ".htm"):
        raw = path.read_text(encoding="utf8", errors="replace")
        meta = " ".join(re.findall(r"<meta[^>]*generator[^>]*>|<!--.*?-->", raw, re.S))
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
        body = re.sub(r"<blockquote[^>]*>.*?</blockquote>", "", body, flags=re.S | re.I)
        parts = re.findall(r"<(?:p|li|h[1-6]|td|th)[^>]*>(.*?)</(?:p|li|h[1-6]|td|th)>", body, re.S | re.I)
        return [(f"block {i+1}", strip_xml(p).strip()) for i, p in enumerate(parts) if strip_xml(p).strip()], meta, True, None
    if ext in (".docx", ".pptx"):
        z = patterns.open_zip(path)
        names = z.namelist()
        meta = " ".join(z.read(n).decode("utf8", "replace")
                        for n in ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml") if n in names)
        if ext == ".docx":
            u = units_from_ooxml(z, r"word/(document|footnotes|endnotes|header\d*|footer\d*|comments)\.xml",
                                 r"<w:p[ >].*?</w:p>", r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", QUOTE_STYLES)
        else:
            u = units_from_ooxml(z, r"ppt/(slides/slide\d+|notesSlides/notesSlide\d+|comments/[^/]+)\.xml",
                                 r"<a:p>.*?</a:p>|<a:p .*?</a:p>", r"<a:t>(.*?)</a:t>")
        return u, meta, True, z
    if ext == ".pdf":
        try:
            txt = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            sys.exit("cannot read PDF text (pdftotext missing or failed); scanned PDFs need OCR")
        if not txt.strip():
            sys.exit("PDF has no text layer; OCR needed, nothing to scan")
        paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
        return [(f"block {i+1}", p) for i, p in enumerate(paras)], "", False, None
    sys.exit(f"unsupported file type: {ext}")


def drop_references(units):
    out, skipping = [], False
    for where, text in units:
        if REF_HEAD.match(text):
            skipping = True
            continue
        if not skipping:
            out.append((where, text))
    return out, skipping


TOOL_FIELDS = re.compile(
    r"<(Application|AppVersion|Producer|Generator|dc:description|cp:keywords|dc:subject)\b[^>]*>([^<]*)</\1>", re.I)
TOOL_STRICT = re.compile(
    r"(chatgpt|\bgpt-?\d\w*|openai|anthropic|copilot|midjourney|dall-?e|stable diffusion|"
    r"claude[ -](?:ai|code|opus|sonnet|haiku|\d)|gemini[ -](?:ai|advanced|pro|flash|ultra|\d))", re.I)


def meta_signs(meta):
    found = []
    if re.search(r"<dcterms:(created|modified)[^>]*>(2006|2011)-", meta):
        found.append("placeholder date (2006/2011)")
    if re.search(r"<(Words|Slides)>0<", meta):
        found.append("Words/Slides counter is 0")
    if re.search(r"<dc:creator\s*/>|<dc:creator></dc:creator>", meta):
        found.append("empty author")
    hit = None
    for field, value in TOOL_FIELDS.findall(meta):
        m = TOOL_META.search(value)  # fields a tool writes: any tool name counts
        if m:
            hit = m.group(1).lower()
            break
    if not hit:
        for value in re.findall(r"<(?:dc:creator|cp:lastModifiedBy)\b[^>]*>([^<]*)<", meta):
            m = TOOL_STRICT.search(value)  # people's names (Claude, Gemini) are not tools
            if m:
                hit = m.group(1).lower()
                break
    if not hit and re.search(r"<meta[^>]*generator", meta, re.I):
        m = TOOL_META.search(meta)
        hit = m.group(1).lower() if m else None
    if hit:
        found.append(f"AI tool name in metadata ({hit})")
    return found


def media_signs(z):
    found = []
    for n in z.namelist():
        if not re.match(r"(word|ppt)/media/", n):
            continue
        if MEDIA_NAMES.search(n):
            found.append((f"image filename suggests a generator ({n})", n))
        data = z.read(n)
        seen = set()
        for label, marker in MEDIA_MARKERS:
            if label not in seen and marker in data:
                seen.add(label)
                found.append((f"image provenance: {label}", n))
    return found


def part_of(where):
    if "notesSlide" in where:
        return "notes"
    if where.startswith("ppt/slides"):
        return "slides"
    if "comments" in where:
        return "comments"
    if where.startswith("word/") and not where.startswith("word/document"):
        return "headers/footnotes"
    return "body"


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def structure_signals(scored, cats, locs, is_pptx):
    """Document-level repetition signals. Repeated sentences also raise the score of the units that hold them."""
    seen = {}
    for idx, u in enumerate(scored):
        for s in u[3]:
            if words(s) >= 6:
                seen.setdefault(norm(s), set()).add(idx)
    rep = {k: v for k, v in seen.items() if len(v) >= 3}
    for k, idxs in rep.items():
        for idx in idxs:
            u = scored[idx]
            u[2] += 2
            u[5]["repeated sentence in 3+ units"] = u[5].get("repeated sentence in 3+ units", 0) + 1
            for i, s in enumerate(u[3]):
                if norm(s) == k:
                    u[4][i] = True
    if rep:
        cats["repeated sentence in 3+ units"] = sum(len(v) for v in rep.values())
        locs["repeated sentence in 3+ units"] = [scored[min(v)][0] for v in rep.values()][:2]
    if is_pptx:  # same label opening many slides ("What happens", "Why it fits")
        openers = {}
        for idx, u in enumerate(scored):
            w = u[1].split()
            if len(w) >= 2 and part_of(u[0]) == "slides":
                openers.setdefault(" ".join(w[:3]).lower().strip(".,:;"), []).append(idx)
        keys = [k for k, v in openers.items() if len(v) >= 4]
        if keys:
            cats["repeated unit opener (4+ slides)"] = len(keys)
            locs["repeated unit opener (4+ slides)"] = keys[:2]
        notes = [words(u[1]) for u in scored if part_of(u[0]) == "notes" and words(u[1]) >= 20]
        if len(notes) >= 5 and statistics.mean(notes) and statistics.pstdev(notes) / statistics.mean(notes) < 0.15:
            cats["uniform note length (spread under 15%)"] = 1
            locs["uniform note length (spread under 15%)"] = [f"{len(notes)} notes, mean {statistics.mean(notes):.0f} words, spread {100 * statistics.pstdev(notes) / statistics.mean(notes):.0f}%"]
    label_files = {u[0].split(" ¶")[0] for u in scored if part_of(u[0]) == "notes"
                   and re.match(r"^(Video|Sources?|Image source|Audience|Sources checked)\s*:", u[1], re.I)}
    if len(label_files) >= 3:  # notes written as a citation log, not for a presenter
        cats["citation-style labels in speaker notes (3+ notes)"] = len(label_files)
        locs["citation-style labels in speaker notes (3+ notes)"] = sorted(label_files)[:2]
    runs = 0
    first = None
    for u in scored:
        streak = 0
        for s in u[3]:
            streak = streak + 1 if words(s) <= 3 else 0
            if streak == 3:
                runs += 1
                u[5]["run of 3+ very short sentences"] = u[5].get("run of 3+ very short sentences", 0) + 1
                first = first or u[0]
    if runs:
        cats["run of 3+ very short sentences"] = runs
        locs["run of 3+ very short sentences"] = [first]


def score_unit(where, text, rules, rich, disclosed_tools, mentions):
    """Return (unit_score, sentences, per_sentence_hit_flags, counts) for one paragraph-sized unit."""
    sents = patterns.sentences(text) or [text]
    notes = "notesSlide" in where or "comments" in where
    disclosed = bool(DISCLOSURE.search(text))
    counts, flags = {}, [False] * len(sents)
    score, style_rules = 0, set()
    for r in rules:
        if r["where"] == "notes" and not notes:
            continue
        if r["id"] == "markdown-leakage" and not rich:
            continue
        total = 0
        for i, s in enumerate(sents):
            edge = r.get("edge")
            if edge:  # chat residue only counts in the unit's first / last sentence
                at_edge = (edge in ("first", "either") and i == 0) or (edge in ("last", "either") and i == len(sents) - 1)
                hits = r["rx"].findall(s) if at_edge else []
            else:
                hits = r["rx"].findall(s)
            if not hits:
                continue
            if r["kind"] == "tool":
                found = [h.lower() for h in hits]
                if disclosed or all(h in disclosed_tools for h in found):
                    continue
                for h in found:
                    mentions[h] = mentions.get(h, 0) + 1
                continue
            total += len(hits)
            flags[i] = True
        if total:
            counts[r["label"]] = total
            if r["kind"] in STRONG:
                score += KIND_SCORE[r["kind"]] * min(total, 2)
            elif r["kind"] == "style":
                style_rules.add(r["id"])
    score += len(style_rules)
    return score, sents, flags, counts


def main():
    args = sys.argv[1:]
    flags = {a for a in args if a.startswith("--")}
    out_path = None
    if "--out" in args:
        i = args.index("--out")
        out_path = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
        flags.discard("--out")
    files = [a for a in args if not a.startswith("--")]
    if len(files) != 1:
        sys.exit(__doc__)
    path = Path(files[0])
    if out_path and out_path.exists():
        sys.exit("exists, not overwriting: " + str(out_path))
    rules = patterns.load_rules("review")
    units, meta, rich, z = load(path)
    all_units = units  # disclosures are searched everywhere, including after the reference list
    units, had_refs = drop_references(units)
    tool_rx = next(r["rx"] for r in rules if r["kind"] == "tool")
    disclosed_tools = {m.lower() for _, t in all_units if DISCLOSURE.search(t) for m in tool_rx.findall(t)}
    mentions, cats, locs, scored = {}, {}, {}, []
    total_words = 0
    for where, text in units:
        text = QUOTE.sub(" ", text)  # long quoted passages are someone else's wording
        total_words += words(text)
        score, sents, hit_flags, counts = score_unit(where, text, rules, rich, disclosed_tools, mentions)
        for label, n in counts.items():
            cats[label] = cats.get(label, 0) + n
            locs.setdefault(label, [])
            if len(locs[label]) < 2:
                locs[label].append(where)
        scored.append([where, text, score, sents, hit_flags, counts])
    # document-level signals
    structure_signals(scored, cats, locs, path.suffix.lower() == ".pptx")
    sents_all = [s for u in scored for s in u[3] if words(s) > 2]
    if len(sents_all) >= 40:
        sd = statistics.pstdev(words(s) for s in sents_all)
        if sd < 4:
            cats["uniform sentence length (SD %.1f)" % sd] = 1
    for m in meta_signs(meta):
        cats["metadata: " + m] = cats.get("metadata: " + m, 0) + 1
    if "--media" in flags and z is not None:
        for label, where in media_signs(z):
            cats[label] = cats.get(label, 0) + 1
            locs.setdefault(label, []).append(where)
    joined = " ".join(u[1] for u in scored)
    if rich and re.search(r"[‘’]", joined) and re.search(r"['\"]", joined):
        cats["mixed straight/curly quotes"] = 1
    signs = sum(cats.values())

    def share(th, part=None):
        """Words in the sentences that carry a hit, counted for units scoring at least `th` (optionally one part)."""
        flagged = denom = 0
        for u in scored:
            if part and part_of(u[0]) != part:
                continue
            denom += words(u[1])
            if u[2] >= th:
                flagged += sum(words(s) for s, f in zip(u[3], u[4]) if f)
        return 100.0 * flagged / denom if denom else 0.0
    lo, est, hi = share(3), share(2), share(1)
    short = total_words < 300 or len(units) < 15
    prose = " ".join(u[1] for u in scored if words(u[1]) >= 6)  # headings, cells and labels skew the ratio
    ratio = patterns.english_ratio(prose)
    english = patterns.looks_english(prose)  # True / False / None
    lang_uncertain = ratio is not None and 0.08 <= ratio < 0.12
    conf = "low" if short else ("high" if total_words > 2000 and len(units) > 40 else "medium")
    if lang_uncertain and conf == "high":
        conf = "medium"
    parts = {}
    for u in scored:
        pt = parts.setdefault(part_of(u[0]), {"words": 0, "signs": 0})
        pt["words"] += words(u[1])
        pt["signs"] += sum(u[5].values())
    for name, pt in parts.items():
        pt["estimate_pct"] = round(share(2, name))
    disc = [t for _, t in all_units if DISCLOSURE.search(t)]
    result = {
        "file": str(path), "words": total_words, "units": len(units), "signs": signs,
        "per_1000_words": round(1000 * signs / total_words, 1) if total_words else 0,
        "categories": cats, "examples": locs, "mentioned_not_counted": mentions, "by_part": parts,
        "estimate_pct": round(est), "range_pct": [round(lo), round(hi)], "confidence": conf,
        "too_short_for_reliable_estimate": short, "english": english, "language_uncertain": lang_uncertain,
        "references_excluded": had_refs, "disclosure": disc[0][:200] if disc else None,
    }
    lines = mdtable.format_table([["Category", "Count", "Examples"]] + [
        [k, str(v), ", ".join(locs.get(k, [])[:2]) or "-"] for k, v in sorted(cats.items(), key=lambda kv: -kv[1])])
    summary = [
        f"AI SIGNS FOUND: {signs} in {total_words} words ({result['per_1000_words']} per 1000)",
        ("APPROX. AI-GENERATED/ASSISTED CONTENT: not estimated - the rules are English-only and this text does not look English"
         if english is False else
         f"APPROX. AI-GENERATED/ASSISTED CONTENT: ~{round(est)}% (range {round(lo)}-{round(hi)}%), confidence {conf}"
         + (" - too short for a reliable estimate" if short else "")),
        f"DISCLOSURE IN FILE: {result['disclosure'] or 'none'}",
    ]
    if mentions:
        summary.append("MENTIONED, NOT COUNTED: " + ", ".join(f"{k} x{v}" for k, v in sorted(mentions.items())))
    if lang_uncertain:
        summary.append("LANGUAGE: uncertain - the English-only rules may not fit this text")
    if len(parts) > 1:
        summary.append("BY PART: " + "; ".join(f"{k} {v['words']} words, {v['signs']} signs, ~{v['estimate_pct']}%"
                                              for k, v in sorted(parts.items(), key=lambda kv: -kv[1]["words"])))
    tail = ("A judgement from signals, not detector proof. The figure is a floor from lexical and structural signals: "
            "polished prose without them is invisible to it.")
    if path.suffix.lower() in (".pptx", ".docx"):
        tail += " For export fingerprints run repair-document/scripts/ooxml_inspect.py."
    if english is False:
        result["estimate_pct"] = result["range_pct"] = None
    if short or english is False or lang_uncertain:
        summary.append("Caution: short, templated or non-native writing raises false positives; "
                       "do not use this to accuse a person, ask the author.")
    if "--json" in flags:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n".join(lines) + "\n\n" + "\n".join(summary) + "\n" + tail)
    if out_path:
        out_path.write_text(
            f"# AI review: {path.name}\n\nDate: {date.today().isoformat()} · Tool: review-ai-content (scan_signs.py)\n\n"
            "## Signs by category\n\n" + "\n".join(lines) + "\n\n## Summary\n\n```\n" + "\n".join(summary) + "\n```\n\n"
            + tail + " Do not use it to accuse a person; ask the author.\n", encoding="utf8")
        print("wrote", out_path, file=sys.stderr)


if __name__ == "__main__":
    patterns.guard(main)
