"""Regression tests for the document-skills scripts. Run: python3 -m unittest discover -s tests -v

Builds its own tiny fixtures in a temp folder; needs only the standard library.
"""
import json, re, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "document-skills"
SCAN = ROOT / "skills/review-ai-content/scripts/scan_signs.py"
TELLS = ROOT / "skills/repair-document/scripts/prose_tells.py"
INVIS = ROOT / "skills/repair-document/scripts/invisible_chars.py"
TOOLS = ROOT / "skills/repair-document/scripts/check_tools.py"
PACK = ROOT / "skills/repair-document/scripts/ooxml_pack.py"
VALIDATE = ROOT.parents[1] / "tools/validate_marketplace.py"
INSPECT = ROOT / "skills/repair-document/scripts/ooxml_inspect.py"
FIX = ROOT / "skills/repair-document/scripts/ooxml_fix.py"
SELFTEST = ROOT / "skills/generate-diagram/scripts/selftest.py"
LAYOUT = ROOT / "skills/repair-document/scripts/ooxml_layout.py"  # imported by inspect and fix
FONTS = ROOT / "skills/repair-document/scripts/ooxml_fonts.py"  # imported by inspect and fix
ACTIVITY = ROOT / "skills/improve-skills/scripts/recent_activity.py"
LESSONS = ROOT / "skills/improve-skills/scripts/lessons.py"
PLAN = ROOT / "skills/improve-skills/scripts/plan_check.py"
CHECKS = ROOT / "skills/improve-skills/scripts/run_checks.py"
MDTABLES = ROOT / "skills/improve-skills/scripts/md_tables.py"
FULL = ROOT / "skills/repair-document/scripts/full_repair.py"
TEXTM = ROOT / "skills/repair-document/scripts/ooxml_text.py"  # imported by ooxml_layout
PREVIEW = ROOT / "skills/repair-document/scripts/slide_preview.py"
DIAG = ROOT / "skills/generate-diagram/scripts/render_diagram.py"


def run(script, *args):
    return subprocess.run([sys.executable, "-I", str(script), *map(str, args)], capture_output=True, text=True)


def docx(path, paragraphs, core=""):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f'<w:document xmlns:w="w"><w:body>{body}</w:body></w:document>')
        z.writestr("docProps/core.xml", f"<cp:coreProperties>{core}</cp:coreProperties>")


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf8")
        return p


class SharedPatterns(Fixtures):
    def test_patterns_file_is_valid(self):
        import re
        data = json.loads((ROOT / "shared/patterns.json").read_text())
        for r in data["rules"]:
            re.compile(r["pattern"], re.I | re.M)
            self.assertIn(r["kind"], {"residue", "token", "tool", "glyph", "format", "style"})

    def test_both_scanners_flag_the_same_residue(self):
        f = self.write("a.md", "Certainly! Here's a summary.\n\nWe delve into it.\n")
        self.assertIn("sycophantic opener", run(SCAN, f).stdout)
        self.assertIn("sycophancy-opener", run(TELLS, f).stdout)


class ScanSigns(Fixtures):
    def test_clean_text_has_no_signs(self):
        f = self.write("c.md", "I bought three eggs on Tuesday. Two were cracked.\n")
        self.assertIn("AI SIGNS FOUND: 0", run(SCAN, f).stdout)

    def test_short_text_is_flagged_not_widened(self):
        out = run(SCAN, self.write("s.md", "Certainly! Here's a summary.\n")).stdout
        self.assertIn("too short for a reliable estimate", out)
        self.assertNotIn("range 0-100%", out)

    def test_everyday_email_is_not_residue(self):
        mail = ("Hi Anna, I cannot attend the meeting on Friday because I am travelling. Here's a thought: we "
                "could move it to Monday. Let me know if that works for you.\n")
        self.assertIn("AI SIGNS FOUND: 0", run(SCAN, self.write("mail.txt", mail)).stdout)

    def test_json_output_stays_valid_with_out(self):
        f = self.write("j.txt", "Plain words here.\n")
        done = run(SCAN, f, "--json", "--out", self.tmp / "r.md")
        json.loads(done.stdout)

    def test_ordinary_phrases_are_not_hollow_openers(self):
        out = run(SCAN, self.write("h.txt", "In this world nothing is certain. We sell in this market and in this age group.\n")).stdout
        self.assertIn("AI SIGNS FOUND: 0", out)
        self.assertIn("hollow opener", run(SCAN, self.write("h2.txt", "In today's fast-paced world, we all rush.\n")).stdout)

    def test_residue_counts_only_at_the_edges(self):
        self.assertIn("assistant offer", run(SCAN, self.write("e.txt", "The plan is ready. I hope this helps.\n")).stdout)
        mid = "The plan is ready. I hope this helps you decide, and the team agreed. Next we ship it.\n"
        self.assertIn("AI SIGNS FOUND: 0", run(SCAN, self.write("m.txt", mid)).stdout)

    def test_markdown_references_headings_are_recognised(self):
        for head in ("## References", "**References**", "## Literature", "Bibliography:"):
            f = self.write("r.md", f"My plain note about eggs.\n\n{head}\n\nSmith 2020. Furthermore, a comprehensive robust delve.\n")
            self.assertIn("AI SIGNS FOUND: 0", run(SCAN, f).stdout, head)

    def test_tool_name_topic_mention_is_reported_not_counted(self):
        out = run(SCAN, self.write("t.txt", "Since ChatGPT appeared, students write differently.\n")).stdout
        self.assertIn("AI SIGNS FOUND: 0", out)
        self.assertIn("MENTIONED, NOT COUNTED: chatgpt", out)

    def test_one_hit_flags_only_its_sentence(self):
        long = "Certainly! Here is the answer. " + "The cat sat on the mat and looked out of the window. " * 20
        out = run(SCAN, self.write("l.txt", long), "--json").stdout
        self.assertLess(json.loads(out)["estimate_pct"], 10)

    def test_docx_bullets_are_not_signs(self):
        d = self.tmp / "b.docx"
        docx(d, ["• first point", "• second point"])
        self.assertIn("AI SIGNS FOUND: 0", run(SCAN, d).stdout)

    def test_disclosure_after_references_is_found_and_tool_not_counted(self):
        d = self.tmp / "r.docx"
        docx(d, ["Body text about my week.", "References", "Smith (2020) Something.",
                 "AI (Claude) was used to help find sources."])
        out = run(SCAN, d).stdout
        self.assertIn("DISCLOSURE IN FILE: AI (Claude) was used", out)
        self.assertNotIn("AI tool name", out)

    def test_quoted_passage_is_not_scored(self):
        q = "“" + "Furthermore this comprehensive robust landscape delves into it " * 2 + "”"
        out = run(SCAN, self.write("q.md", f"He said {q} and left.\n")).stdout
        self.assertIn("AI SIGNS FOUND: 0", out)

    def test_out_report_is_written_and_never_overwritten(self):
        f = self.write("o.md", "Plain sentence here.\n")
        out = self.tmp / "report.md"
        self.assertEqual(run(SCAN, f, "--out", out).returncode, 0)
        self.assertIn("Summary", out.read_text())
        self.assertNotEqual(run(SCAN, f, "--out", out).returncode, 0)

    def test_media_marker_is_found(self):
        d = self.tmp / "m.pptx"
        with zipfile.ZipFile(d, "w") as z:
            z.writestr("ppt/slides/slide1.xml", "<a:p><a:r><a:t>Hello there</a:t></a:r></a:p>")
            z.writestr("ppt/media/image1.png", b"\x89PNG....parameters\x00prompt text")
        self.assertIn("generation prompt chunk", run(SCAN, d, "--media").stdout)


class ProseTells(Fixtures):
    def test_html_line_numbers_match_file(self):
        f = self.write("a.html", "<html>\n<body>\n<p>We delve in.</p>\n</body>\n</html>\n")
        self.assertIn("line 3", run(TELLS, f).stdout)

    def test_ignore_marker_and_code_are_skipped(self):
        f = self.write("i.md", "We delve in. repair-ignore\n\n```\ndelve\n```\n")
        self.assertIn("0 findings", run(TELLS, f).stdout)

    def test_email_is_clean_for_the_edit_scanner_too(self):
        mail = "Hi Anna, I cannot attend.\n\nHere's a thought: move it. Let me know if that works for you.\n"
        self.assertIn("0 findings", run(TELLS, self.write("mail.txt", mail)).stdout)

    def test_exit_code_is_high_count(self):
        f = self.write("h.md", "Certainly! Great question.\n")
        self.assertEqual(run(TELLS, f).returncode, 1)  # one finding per rule per line


class Invisible(Fixtures):
    def test_zero_width_found_and_cleaned_without_touching_code(self):
        f = self.write("z.md", "Hel​lo\n```\nco​de\n```\n")
        self.assertIn("zero-width", run(INVIS, f).stdout)
        out = self.tmp / "z.clean.md"
        self.assertEqual(run(INVIS, f, "--clean", "--out", out).returncode, 0)
        self.assertEqual(out.read_text(), "Hello\n```\nco​de\n```\n")
        self.assertNotEqual(run(INVIS, f, "--clean", "--out", out).returncode, 0)  # no overwrite

    def test_joiner_between_latin_letters_is_removed_but_emoji_kept(self):
        f = self.write("j.txt", "A‍B \U0001F468‍\U0001F469\n")
        out = run(INVIS, f).stdout
        self.assertRegex(out, r"\| zero-width\s+\| 1\s+\|")
        self.assertIn("joiner (kept)", out)

    def test_homoglyph_in_latin_word(self):
        f = self.write("h.txt", "wоrld\n")  # Cyrillic o
        self.assertIn("homoglyph", run(INVIS, f).stdout)

    def test_html_attributes_and_emoji_selector_are_left_alone(self):
        f = self.write("a.html", '<p title="a\u200bb">Hel\u200blo \u2764\ufe0f</p>')
        out = self.tmp / "a.clean.html"
        run(INVIS, f, "--clean", "--out", out)
        self.assertEqual(out.read_text(), '<p title="a\u200bb">Hello \u2764\ufe0f</p>')

    def test_docx_cleaning_keeps_member_order(self):
        d = self.tmp / "d.docx"
        docx(d, ["Hel​lo"])
        out = self.tmp / "d.clean.docx"
        self.assertEqual(run(INVIS, d, "--clean", "--out", out).returncode, 0)
        with zipfile.ZipFile(d) as a, zipfile.ZipFile(out) as b:
            self.assertEqual(a.namelist(), b.namelist())
            self.assertIn("Hello", b.read("word/document.xml").decode())


NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
WNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
CT = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="xml" ContentType="application/xml"/><Default Extension="%s" ContentType="application/x-fontdata"/></Types>')
CORE = ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
        '<dc:creator></dc:creator><dc:identifier>export-123</dc:identifier>'
        '<dcterms:created>2006-08-16T00:00:00Z</dcterms:created><dcterms:modified>2011-08-01T00:00:00Z</dcterms:modified>'
        '</cp:coreProperties>')


B = "\u2022"


def make_pptx(path):
    run = lambda txt, sz, font: (f'<a:r><a:rPr sz="{sz}"><a:latin typeface="{font}"/></a:rPr><a:t>{txt}</a:t></a:r>')
    slide = (f'<p:sld {NS}><p:cSld><p:spTree><p:sp><p:txBody>'
             f'<a:p><a:pPr><a:spcPts val="2499"/></a:pPr>{run("Heading", 2499, "Times New Roman Bold")}</a:p>'
             f'<a:p>{run(B + " first point", 1800, "Arial")}</a:p>'
             f'<a:p><a:pPr algn="l"/>{run(B + " second point", 1912, "Arial")}</a:p>'
             f'<a:p><a:pPr marL="0"><a:tabLst/></a:pPr>{run(B + " third point", 1800, "Arial")}</a:p>'
             '</p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
    notes = f'<p:notes {NS}><a:p><a:r><a:t>Source: user-provided photo, do not claim a date</a:t></a:r></a:p></p:notes>'
    pres = f'<p:presentation {NS}><p:embeddedFontLst><p:embeddedFont><p:font typeface="X"/></p:embeddedFont></p:embeddedFontLst></p:presentation>'
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/font" Target="fonts/font1.fntdata"/>'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
            '</Relationships>')
    app = '<Properties><Slides>0</Slides><Notes>0</Notes><Words>0</Words></Properties>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", CT % "fntdata")
        z.writestr("ppt/presentation.xml", pres)
        z.writestr("ppt/_rels/presentation.xml.rels", rels)
        z.writestr("ppt/fonts/font1.fntdata", b"\x00fontbytes")
        z.writestr("ppt/slides/slide1.xml", slide)
        z.writestr("ppt/notesSlides/notesSlide1.xml", notes)
        z.writestr("docProps/core.xml", CORE)
        z.writestr("docProps/app.xml", app)


def make_docx(path):
    doc = (f'<w:document {WNS}><w:body>'
           '<w:p><w:r><w:rPr><w:rFonts w:ascii="Georgia Bold" w:hAnsi="Georgia Bold"/></w:rPr><w:t>Title</w:t></w:r></w:p>'
           '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t xml:space="preserve">\u2022 first</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>\u2022</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>second</w:t></w:r></w:p>'
           '</w:body></w:document>')
    drels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", CT % "odttf")
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", drels)
        z.writestr("docProps/core.xml", CORE)
        z.writestr("docProps/app.xml", "<Properties><Words>0</Words></Properties>")


def all_xml_parses(test, path):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.endswith((".xml", ".rels")):
                try:
                    ET.fromstring(z.read(n))
                except ET.ParseError as e:
                    test.fail(f"{n} is not well-formed after the fix: {e}")


class OoxmlFix(Fixtures):
    def fix(self, src, *flags):
        out = self.tmp / ("out_" + src.name)
        done = run(FIX, src, "--out", out, "--json", *flags)
        self.assertEqual(done.returncode, 0, done.stderr)
        return out, json.loads(done.stdout)["fixes"]

    def read(self, path, name):
        with zipfile.ZipFile(path) as z:
            return z.read(name).decode("utf8")

    def test_pptx_all_fixes(self):
        src = self.tmp / "d.pptx"
        make_pptx(src)
        out, rep = self.fix(src, "--round-sizes", "--rename-font", "Times New Roman Bold", "Times New Roman", "--bold",
                            "--strip-embedded-fonts", "--bullets", "--props", "author=Jane Doe,date=today", "--report-notes")
        all_xml_parses(self, out)
        slide = self.read(out, "ppt/slides/slide1.xml")
        self.assertIn('sz="2500"', slide)
        self.assertNotIn('sz="2499"', slide)
        self.assertIn('<a:spcPts val="2500"/>', slide)  # scaled with its paragraph
        self.assertIn('sz="1912"', slide)  # not rounding noise: left alone
        self.assertEqual(rep["round-sizes"]["other fractional sizes left"], 1)
        self.assertIn('typeface="Times New Roman"', slide)
        self.assertIn('b="1"', slide)
        self.assertEqual(rep["bullets"]["typed bullets converted"], 3)
        self.assertEqual(slide.count("<a:buChar"), 3)
        self.assertNotIn("\u2022 first", slide)
        self.assertIn(">first point<", slide)
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(out) as b:
            self.assertNotIn("ppt/fonts/font1.fntdata", b.namelist())
            self.assertEqual([n for n in a.namelist() if n != "ppt/fonts/font1.fntdata"], b.namelist())
        self.assertNotIn("embeddedFontLst", self.read(out, "ppt/presentation.xml"))
        self.assertNotIn("/font", self.read(out, "ppt/_rels/presentation.xml.rels"))
        self.assertNotIn("fntdata", self.read(out, "[Content_Types].xml"))
        core = self.read(out, "docProps/core.xml")
        self.assertIn("<dc:creator>Jane Doe</dc:creator>", core)
        self.assertNotIn("2006-08", core)
        self.assertNotIn("2011-08", core)
        self.assertNotIn("identifier", core)
        self.assertIn("<Slides>1</Slides>", self.read(out, "docProps/app.xml"))
        self.assertEqual(rep["report-notes"]["generator-facing notes"], 1)

    def test_dry_run_writes_nothing_and_input_is_untouched(self):
        src = self.tmp / "d.pptx"
        make_pptx(src)
        before = src.read_bytes()
        done = run(FIX, src, "--round-sizes")
        self.assertIn("dry run", done.stdout)
        self.assertEqual(src.read_bytes(), before)
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["d.pptx"])

    def test_never_overwrites_and_needs_a_flag(self):
        src = self.tmp / "d.pptx"
        make_pptx(src)
        out = self.tmp / "o.pptx"
        self.assertEqual(run(FIX, src, "--out", out, "--round-sizes").returncode, 0)
        self.assertNotEqual(run(FIX, src, "--out", out, "--round-sizes").returncode, 0)
        self.assertNotEqual(run(FIX, src).returncode, 0)

    def test_no_author_flag_means_no_author(self):
        src = self.tmp / "d.pptx"
        make_pptx(src)
        out, _ = self.fix(src, "--props", "date=today")
        self.assertIn("<dc:creator></dc:creator>", self.read(out, "docProps/core.xml"))

    def test_docx_fixes_and_numbering(self):
        src = self.tmp / "d.docx"
        make_docx(src)
        out, rep = self.fix(src, "--rename-font", "Georgia Bold", "Georgia", "--bold", "--bullets", "--props", "author=Jane Doe")
        all_xml_parses(self, out)
        doc = self.read(out, "word/document.xml")
        self.assertIn('w:ascii="Georgia"', doc)
        self.assertIn("<w:b/>", doc)
        self.assertEqual(rep["bullets"]["typed bullets converted"], 2)
        self.assertEqual(doc.count("<w:numPr>"), 2)
        self.assertNotIn("\u2022", doc)
        self.assertIn("second", doc)
        self.assertIn('w:numId w:val="9001"', doc)
        self.assertIn("abstractNumId", self.read(out, "word/numbering.xml"))
        self.assertIn("numbering.xml", self.read(out, "word/_rels/document.xml.rels"))
        self.assertIn("/word/numbering.xml", self.read(out, "[Content_Types].xml"))
        self.assertIn("<Words>", self.read(out, "docProps/app.xml"))
        self.assertIn("<dc:creator>Jane Doe</dc:creator>", self.read(out, "docProps/core.xml"))

    def test_words_counter_uses_whitespace_words(self):
        src = self.tmp / "w.docx"
        docx(src, ["It's a well-known state-of-the-art plan, isn't it?"])
        with zipfile.ZipFile(src, "a") as z:
            z.writestr("docProps/app.xml", "<Properties><Words>0</Words></Properties>")
        out, rep = self.fix(src, "--props", "date=today")
        self.assertIn("<Words>7</Words>", self.read(out, "docProps/app.xml"))

    def test_non_utf8_part_is_skipped_and_reported(self):
        src = self.tmp / "u.pptx"
        make_pptx(src)
        with zipfile.ZipFile(src, "a") as z:
            z.writestr("ppt/slides/slide2.xml", "<p:sld/>".encode("utf-16"))
        out, rep = self.fix(src, "--round-sizes")
        self.assertEqual(rep["skipped"]["parts not in UTF-8, left untouched"], 1)

    def test_unsafe_archive_is_refused(self):
        evil = self.tmp / "e.pptx"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../x.xml", "x")
            z.writestr("ppt/presentation.xml", "<a/>")
        self.assertNotEqual(run(FIX, evil, "--round-sizes").returncode, 0)


def freeform(ident, rect=True, rot=0, x=0, y=0, cx=9271000, cy=6953250):
    pts = (('<a:moveTo><a:pt x="0" y="0"/></a:moveTo><a:lnTo><a:pt x="%d" y="0"/></a:lnTo><a:lnTo><a:pt x="%d" y="%d"/></a:lnTo>'
            '<a:lnTo><a:pt x="0" y="%d"/></a:lnTo><a:close/>' % (cx, cx, cy, cy)) if rect else
           '<a:moveTo><a:pt x="0" y="0"/></a:moveTo><a:lnTo><a:pt x="%d" y="0"/></a:lnTo><a:lnTo><a:pt x="0" y="%d"/></a:lnTo><a:close/>' % (cx, cy))
    return (f'<p:sp><p:nvSpPr><p:cNvPr name="Freeform {ident}" id="{ident}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm flipH="false" flipV="false" rot="{rot}"><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:custGeom><a:avLst/><a:pathLst><a:path w="{cx}" h="{cy}">{pts}</a:path></a:pathLst></a:custGeom>'
            f'<a:blipFill><a:blip r:embed="rId{ident}"/><a:stretch><a:fillRect/></a:stretch></a:blipFill></p:spPr></p:sp>')


class ImagesFix(Fixtures):
    def test_freeform_pictures_become_pics(self):
        group = ('<p:grpSp><p:nvGrpSpPr><p:cNvPr id="9" name="Group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>'
                 '<a:xfrm rot="0"><a:off x="2000000" y="4000000"/><a:ext cx="4000000" cy="3000000"/>'
                 '<a:chOff x="0" y="0"/><a:chExt cx="8000000" cy="6000000"/></a:xfrm></p:grpSpPr>'
                 + freeform(6, cx=8000000, cy=6000000) + '</p:grpSp>')
        body = group + freeform(7, rot=-3182302, x=500, y=600, cx=1000, cy=2000) + freeform(8, rect=False)
        src = self.tmp / "im.pptx"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("ppt/presentation.xml", f"<p:presentation {NS}/>")
            z.writestr("ppt/slides/slide1.xml", f"<p:sld {NS}>{body}</p:sld>")
        out = self.tmp / "im_out.pptx"
        done = run(FIX, src, "--out", out, "--images", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        rep = json.loads(done.stdout)["fixes"]["images"]
        self.assertEqual(rep["freeforms converted to p:pic"], 2)
        all_xml_parses(self, out)
        with zipfile.ZipFile(out) as z:
            x = z.read("ppt/slides/slide1.xml").decode()
        self.assertEqual(x.count("<p:pic>"), 2)
        self.assertEqual(x.count("<a:custGeom>"), 1)  # the triangle stays
        self.assertIn('<a:off x="2000000" y="4000000"/><a:ext cx="4000000" cy="3000000"/>', x)  # group transform applied
        self.assertIn('rot="-3182302"', x)  # rotation kept on the ungrouped one
        self.assertNotIn("<p:grpSp>", x)

    def test_presentation_format_and_ledger_removed(self):
        src = self.tmp / "pf.pptx"
        make_pptx(src)
        with zipfile.ZipFile(src, "a") as z:
            pass
        wide = self.tmp / "wide.pptx"
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(wide, "w") as b:
            for i in a.infolist():
                data = a.read(i.filename)
                if i.filename == "ppt/presentation.xml":
                    data = data.replace(b"</p:presentation>", b'<p:sldSz cx="18288000" cy="10287000"/></p:presentation>')
                if i.filename == "docProps/app.xml":
                    data = data.replace(b"<Slides>", b"<PresentationFormat>On-screen Show (4:3)</PresentationFormat><Slides>")
                b.writestr(i, data)
        out = self.tmp / "wide_fixed.pptx"
        self.assertEqual(run(FIX, wide, "--out", out, "--props", "date=today", "--bullets").returncode, 0)
        with zipfile.ZipFile(out) as z:
            self.assertIn("<PresentationFormat>Widescreen</PresentationFormat>", z.read("docProps/app.xml").decode())
        led = json.loads(run(PACK, "ledger", wide, out, "--json").stdout)
        self.assertEqual(led["body"]["removed"], 3)  # the three typed bullet characters

    def test_inspect_names_the_rename_command(self):
        src = self.tmp / "cmd.pptx"
        make_pptx(src)
        rows = {r["signal"]: r for r in json.loads(run(INSPECT, src, "--json").stdout)["signals"]}
        note = rows["fabricated font families (name ends in Bold/Italic)"]["note"]
        self.assertIn('--rename-font "Times New Roman Bold" "Times New Roman" --bold', note)

    def test_uniform_notes_count_once(self):
        d = self.tmp / "u.pptx"
        notes = [["Note %d about the talk, written to be nearly the same length every single time it appears here in this small test deck." % i] for i in range(1, 7)]
        deck(d, [["Slide"]] * 6, notes)
        cats = json.loads(run(SCAN, d, "--json").stdout)["categories"]
        self.assertEqual(cats["uniform note length (spread under 15%)"], 1)


def text_box(ident, x, y, cx, cy, text, color=None, fill=None, sz=2000):
    clr = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>' if color else ""
    bg = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else ""
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{ident}" name="t{ident}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"/>{bg}</p:spPr>'
            f'<p:txBody><a:p><a:r><a:rPr sz="{sz}">{clr}</a:rPr><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>')


def sized_deck(path, body):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/presentation.xml", f'<p:presentation {NS}><p:sldSz cx="9144000" cy="6858000"/></p:presentation>')
        z.writestr("ppt/slides/slide1.xml", f"<p:sld {NS}><p:cSld><p:spTree>{body}</p:spTree></p:cSld></p:sld>")


class StaticLayout(Fixtures):
    def signals(self, path):
        return {r["signal"]: r for r in json.loads(run(INSPECT, path, "--json").stdout)["signals"]}

    def test_contrast_and_geometry_signals(self):
        d = self.tmp / "l.pptx"
        sized_deck(d, text_box(2, 0, 0, 4000000, 1000000, "Pale", color="CCCCCC")
                   + text_box(3, 0, 2000000, 4000000, 1000000, "Dark", color="303030", fill="202020", sz=1200)
                   + text_box(4, 8000000, 0, 3000000, 500000, "Off the slide", color="000000")
                   + text_box(5, 0, 0, 3000000, 900000, "Overlaps the first", color="000000"))
        s = self.signals(d)
        self.assertEqual(s["text runs failing contrast (explicit colours, known background)"]["value"], 2)
        self.assertEqual(s["text boxes extending off the slide"]["value"], 1)
        self.assertEqual(s["overlapping text boxes (static; confirm with a render)"]["value"], 1)

    def test_unknown_background_is_skipped_not_guessed(self):
        d = self.tmp / "u.pptx"
        picture = ('<p:sp><p:nvSpPr><p:cNvPr id="9" name="bg"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
                   '<a:xfrm><a:off x="0" y="0"/><a:ext cx="9144000" cy="6858000"/></a:xfrm><a:prstGeom prst="rect"/>'
                   '<a:blipFill><a:blip r:embed="rId1"/></a:blipFill></p:spPr></p:sp>')
        sized_deck(d, picture + text_box(2, 100, 100, 4000000, 1000000, "White on a photo", color="FFFFFF"))
        v = self.signals(d)["text runs failing contrast (explicit colours, known background)"]
        self.assertEqual(v["value"], 0)
        self.assertIn("1 text boxes skipped", v["note"])

    def test_contrast_fix_reaches_the_target_and_input_is_untouched(self):
        d = self.tmp / "f.pptx"
        sized_deck(d, text_box(2, 0, 0, 4000000, 1000000, "Pale", color="CCCCCC")
                   + text_box(3, 0, 2000000, 4000000, 1000000, "Dark", color="303030", fill="202020", sz=1200))
        before = d.read_bytes()
        out = self.tmp / "f_out.pptx"
        done = run(FIX, d, "--out", out, "--contrast", "--json")
        self.assertEqual(json.loads(done.stdout)["fixes"]["contrast"]["text runs recoloured"], 2)
        self.assertEqual(d.read_bytes(), before)
        all_xml_parses(self, out)
        self.assertEqual(self.signals(out)["text runs failing contrast (explicit colours, known background)"]["value"], 0)

    def test_helpers_ratio_and_adjust(self):
        sys.path.insert(0, str(LAYOUT.parent))
        import ooxml_layout as L
        self.assertAlmostEqual(L.ratio("000000", "FFFFFF"), 21.0, places=1)
        self.assertGreaterEqual(L.ratio(L.adjust("CCCCCC", "FFFFFF", 4.6), "FFFFFF"), 4.6)
        self.assertGreaterEqual(L.ratio(L.adjust("303030", "202020", 4.6), "202020"), 4.6)


def inch(v):
    return int(v * 914400)


def tight_deck(path, boxes):
    """boxes: [(text, x_in, y_in, w_in, h_in, size_pt, bold, algn)] on a 20 x 11.25 in slide, zero insets like a Canva export."""
    body = ""
    for i, (text, x, y, w, h, size, bold, algn) in enumerate(boxes, 2):
        body += (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="t{i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{inch(x)}" y="{inch(y)}"/>'
                 f'<a:ext cx="{inch(w)}" cy="{inch(h)}"/></a:xfrm><a:prstGeom prst="rect"/></p:spPr><p:txBody>'
                 f'<a:bodyPr anchor="t" tIns="0" lIns="0" bIns="0" rIns="0"/><a:p><a:pPr algn="{algn}"/><a:r><a:rPr sz="{size * 100}" b="{int(bold)}">'
                 f'<a:latin typeface="Arial"/></a:rPr><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/presentation.xml", f'<p:presentation {NS}><p:sldSz cx="{inch(20)}" cy="{inch(11.25)}"/></p:presentation>')
        z.writestr("ppt/slides/slide1.xml", f"<p:sld {NS}><p:cSld><p:spTree>{body}</p:spTree></p:cSld></p:sld>")


class TextFit(Fixtures):
    """Canva-style boxes are exactly as wide as their text; any renderer that measures a hair wider wraps or breaks inside a word."""
    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(TEXTM.parent))
        import ooxml_text, ooxml_layout
        self.T, self.L = ooxml_text, ooxml_layout

    def test_widths_match_the_boxes_a_design_tool_exported(self):
        # box widths measured on the real C.pptx: Apple 2.2376 in, What happens 3.7962 in, Why it fits 2.6540 in
        for text, size, expect in (("Apple", 58, 2.2376), ("What happens", 40, 3.7962), ("Why it fits", 40, 2.6540)):
            self.assertAlmostEqual(self.T.width_pt(text, size, True) / 72, expect, delta=0.01)

    def test_wrap_and_break_inside_word(self):
        runs = [("Apple", 58.0, True, "")]
        self.assertTrue(self.T.wrap(runs, 100.0)[3])  # the word itself is wider than the box
        self.assertGreaterEqual(self.T.wrap([("one two three four five six", 20.0, False, "")], 90.0)[0], 3)
        self.assertEqual(self.T.wrap([("one two", 20.0, False, "")], 400.0)[0], 1)

    def test_findings_flag_no_slack_not_comfortable_boxes(self):
        d = self.tmp / "t.pptx"
        tight_deck(d, [("Apple", 1, 1, 2.2376, 1, 58, True, "l"), ("What happens", 1, 3, 3.7962, 1, 40, True, "l"),
                       ("Comfortable title", 1, 5, 14, 1, 40, True, "l"),
                       ("A body paragraph that wraps over several lines in a wide box but each word fits easily inside it.", 1, 7, 6, 3, 20, False, "l")])
        rows = json.loads(run(INSPECT, d, "--json").stdout)["signals"]
        by = {r["signal"]: r for r in rows}
        key = "text boxes with no slack (they wrap or break mid-word when a renderer measures a hair wider)"
        self.assertEqual(by[key]["value"], 2)
        self.assertIn("Apple", by[key]["note"])
        self.assertNotIn("Comfortable", by[key]["note"])
        self.assertEqual(by["text boxes shorter than their text (estimate)"]["value"], 0)

    def test_fit_widens_into_free_space_and_is_idempotent(self):
        d = self.tmp / "w.pptx"
        tight_deck(d, [("Apple", 1, 1, 2.2376, 1, 58, True, "l"), ("What happens", 12, 3, 3.7962, 1, 40, True, "l")])
        out = self.tmp / "w_fit.pptx"
        done = run(FIX, d, "--out", out, "--fit", "--json")
        self.assertEqual(json.loads(done.stdout)["fixes"]["fit"]["boxes widened"], 2)
        all_xml_parses(self, out)
        with zipfile.ZipFile(out) as z:
            x = z.read("ppt/slides/slide1.xml").decode()
        widths = [int(v) / 914400 for v in re.findall(r'<a:ext cx="(\d+)"', x)]
        self.assertTrue(all(w > old * 1.1 for w, old in zip(widths, (2.2376, 3.7962))), widths)
        again = run(FIX, out, "--out", self.tmp / "w_fit2.pptx", "--fit", "--json")
        self.assertEqual(json.loads(again.stdout)["fixes"]["fit"]["boxes widened"], 0)

    def test_growth_goes_the_right_way_for_centred_and_right_aligned_text(self):
        d = self.tmp / "a.pptx"
        tight_deck(d, [("Apple", 8, 1, 2.2376, 1, 58, True, "ctr"), ("Apple", 8, 4, 2.2376, 1, 58, True, "r")])
        out = self.tmp / "a_fit.pptx"
        run(FIX, d, "--out", out, "--fit")
        with zipfile.ZipFile(out) as z:
            x = z.read("ppt/slides/slide1.xml").decode()
        offs = [(int(a) / 914400, int(b) / 914400) for a, b in re.findall(r'<a:off x="(\d+)" y="\d+"/><a:ext cx="(\d+)"', x)]
        (cx0, cw0), (rx0, rw0) = offs
        self.assertLess(cx0, 8)                         # centred: grows both ways
        self.assertAlmostEqual(cx0 + cw0 / 2, 8 + 2.2376 / 2, delta=0.02)  # and stays centred
        self.assertLess(rx0, 8)                         # right-aligned: grows to the left
        self.assertAlmostEqual(rx0 + rw0, 8 + 2.2376, delta=0.02)          # and keeps its right edge

    def test_no_room_means_wrapping_off_for_a_title_and_a_report_otherwise(self):
        d = self.tmp / "n.pptx"
        tight_deck(d, [("What happens", 1, 1, 3.7962, 1, 40, True, "l"), ("Blocker", 4.8, 1, 3, 1, 40, False, "l")])
        out = self.tmp / "n_fit.pptx"
        rep = json.loads(run(FIX, d, "--out", out, "--fit", "--json").stdout)["fixes"]["fit"]
        self.assertEqual(rep["wrapping switched off"], 1)
        with zipfile.ZipFile(out) as z:
            self.assertIn('wrap="none"', z.read("ppt/slides/slide1.xml").decode())

    def test_short_box_grows_downwards_into_free_space(self):
        d = self.tmp / "s.pptx"
        text = "word " * 60
        tight_deck(d, [(text.strip(), 1, 1, 4, 0.6, 20, False, "l")])
        rows = {r["signal"]: r for r in json.loads(run(INSPECT, d, "--json").stdout)["signals"]}
        self.assertEqual(rows["text boxes shorter than their text (estimate)"]["value"], 1)
        out = self.tmp / "s_fit.pptx"
        self.assertEqual(run(FIX, d, "--out", out, "--fit").returncode, 0)
        rows2 = {r["signal"]: r for r in json.loads(run(INSPECT, out, "--json").stdout)["signals"]}
        self.assertEqual(rows2["text boxes shorter than their text (estimate)"]["value"], 0)

    def test_full_repair_runs_fit(self):
        d = self.tmp / "f.pptx"
        tight_deck(d, [("Apple", 1, 1, 2.2376, 1, 58, True, "l")])
        r = json.loads(run(FULL, d, "--workdir", self.tmp / "w", "--author", "A", "--json").stdout)
        self.assertIn("--fit", json.dumps(r["rounds"]))


class SlidePreview(Fixtures):
    def test_bad_input_is_refused(self):
        self.assertEqual(run(PREVIEW, self.write("x.txt", "hi"), "--slide", "1").returncode, 2)
        d = self.tmp / "p.pptx"
        make_pptx(d)
        self.assertEqual(run(PREVIEW, d, "--slide", "9", "--out", self.tmp).returncode, 2)

    def test_renders_the_wanted_slide_when_quick_look_exists(self):
        import shutil
        if not shutil.which("qlmanage"):
            self.skipTest("needs macOS Quick Look")
        d = self.tmp / "two.pptx"
        tight_deck(d, [("Hello", 1, 1, 5, 1, 40, True, "l")])
        before = d.read_bytes()
        done = run(PREVIEW, d, "--slide", "1", "--out", self.tmp / "png", "--timeout", "60")
        self.assertIn(done.returncode, (0, 1), done.stderr)  # 1 = Quick Look gave no answer, reported and not a pass
        if done.returncode == 0:
            self.assertTrue(Path(done.stdout.strip()).is_file())
        self.assertEqual(d.read_bytes(), before)


class Fonts(Fixtures):
    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(FONTS.parent))
        import ooxml_fonts
        self.f = ooxml_fonts

    def test_target_for(self):
        self.assertEqual(self.f.target_for("Arimo Bold"), ("Arial", True, False, "renamed"))
        self.assertEqual(self.f.target_for("Times New Roman Bold"), ("Times New Roman", True, False, "renamed"))
        self.assertEqual(self.f.target_for("Georgia Italic"), ("Georgia", False, True, "renamed"))
        self.assertEqual(self.f.target_for("Tinos"), ("Times New Roman", False, False, "renamed"))
        self.assertEqual(self.f.target_for("Arial Black")[3], "ok")        # a real family, not a fake style
        self.assertEqual(self.f.target_for("Calibri Light")[3], "ok")
        self.assertEqual(self.f.target_for("Fredoka")[3], "no-safe-answer")  # a Google font: no automatic answer

    def run_deck(self, families):
        d = self.tmp / "f.pptx"
        runs = "".join(f'<a:p><a:r><a:rPr sz="2000"><a:latin typeface="{f}"/></a:rPr><a:t>{f} text</a:t></a:r></a:p>' for f in families)
        sized_deck(d, f'<p:sp><p:txBody>{runs}</p:txBody></p:sp>')
        return d

    def test_inspect_flags_unsafe_and_suggests_the_office_font(self):
        d = self.run_deck(["Arimo Bold", "Fredoka", "Arial"])
        rows = {r["signal"]: r for r in json.loads(run(INSPECT, d, "--json").stdout)["signals"]}
        fab = rows["fabricated font families (name ends in Bold/Italic)"]
        self.assertIn('--rename-font "Arimo Bold" "Arial" --bold', fab["note"])
        risky = rows["font families that do not ship with Office or macOS (a viewer substitutes another font)"]
        self.assertIn("Fredoka", risky["note"])

    def test_normalize_fonts_sets_bold_and_italic_and_reports_the_rest(self):
        d = self.run_deck(["Arimo Bold", "Georgia Italic", "Tinos", "Fredoka"])
        out = self.tmp / "n.pptx"
        done = run(FIX, d, "--out", out, "--normalize-fonts", "--json")
        rep = json.loads(done.stdout)["fixes"]["normalize-fonts"]
        self.assertEqual(rep["families renamed"], 3)
        self.assertIn("Fredoka", rep["left (no safe answer, decide by hand)"])
        with zipfile.ZipFile(out) as z:
            x = z.read("ppt/slides/slide1.xml").decode()
        all_xml_parses(self, out)
        self.assertIn('b="1"', x)
        self.assertIn('i="1"', x)
        self.assertIn('typeface="Arial"', x)
        self.assertIn('typeface="Times New Roman"', x)
        self.assertIn('typeface="Fredoka"', x)  # untouched


def aligned(text):
    sys.path.insert(0, str(ROOT / "shared"))
    import mdtable
    return mdtable.format_text(text)[0]


GOOD_PLAN = """# Improvement loop, iteration 2 of 5

Written from scratch on 2026-10-22 after running everything. **Items: 2** (1 reasonable, 1 applied).

| # | Item | Verdict |
|---|---|---|
| 1 | **Words counter is wrong.** It counts regex tokens, so 809 words became 1146; use whitespace words. | apply |
| 2 | **Run the real renderers.** Needs LibreOffice, which this machine does not have installed. | skip: tool not installed |
"""


class ImproveSkills(Fixtures):
    def test_plan_check_accepts_the_agreed_shape(self):
        done = run(PLAN, self.write("p.md", aligned(GOOD_PLAN)))
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("2 items, 1 apply, 1 skip", done.stdout)

    def test_plan_check_rejects_each_kind_of_mistake(self):
        bad = {
            "count": GOOD_PLAN.replace("**Items: 2**", "**Items: 3**"),
            "skip without a reason": GOOD_PLAN.replace("skip: tool not installed", "skip"),
            "verdict": GOOD_PLAN.replace("| apply |", "| maybe |"),
            "limit": GOOD_PLAN.replace("2 of 5", "2 of 9"),
            "beyond": GOOD_PLAN.replace("2 of 5", "7 of 5"),
            "no heading": GOOD_PLAN.replace("iteration 2 of 5", ""),
            "numbering": GOOD_PLAN.replace("| 2 |", "| 5 |"),
            "title only": GOOD_PLAN.replace("**Run the real renderers.** Needs LibreOffice, which this machine does not have installed.", "Renderers"),
        }
        for name, text in bad.items():
            done = run(PLAN, self.write(f"{name}.md", aligned(text)))
            self.assertEqual(done.returncode, 1, name)
            self.assertNotIn("not aligned", done.stdout, name)  # it fails for the stated reason, not for layout
        done = run(PLAN, self.write("ugly.md", GOOD_PLAN))  # right content, ragged table
        self.assertEqual(done.returncode, 1)
        self.assertIn("not aligned", done.stdout)

    def test_lessons_add_list_dedupe_check(self):
        f = self.tmp / "docs" / "lessons.md"
        self.assertEqual(run(LESSONS, "add", f, "--kind", "decision", "--text", "No commit before the version is ready",
                             "--evidence", "user, 2026-10-21").returncode, 0)
        self.assertEqual(run(LESSONS, "add", f, "--kind", "lesson", "--text", "Verify a finding a second way",
                             "--evidence", "picture-fill premise was wrong", "--area", "review").returncode, 0)
        again = run(LESSONS, "add", f, "--kind", "lesson", "--text", "verify a finding a second way!", "--evidence", "x")
        self.assertEqual(again.returncode, 1)
        self.assertIn("already recorded", again.stdout)
        text = run(LESSONS, "list", f).stdout
        self.assertLess(text.index("Standing decisions"), text.index("No commit"))
        self.assertLess(text.index("No commit"), text.index("## Lessons"))
        self.assertLess(text.index("## Lessons"), text.index("Verify a finding"))
        self.assertEqual(run(LESSONS, "check", f).returncode, 0)
        self.assertEqual(run(LESSONS, "add", f, "--text", "no evidence given").returncode, 2)

    def test_recent_activity_reads_only_what_the_user_typed(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        (repo / "a.txt").write_text("hello")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=t", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-qm", "first commit"], cwd=repo, check=True)
        tdir = self.tmp / "transcripts"
        tdir.mkdir()
        lines = [
            {"type": "user", "origin": {"kind": "human"}, "timestamp": "2026-10-22T10:00:00Z",
             "message": {"role": "user", "content": "no need for a changelog, drop it"}},
            {"type": "user", "origin": {"kind": "human"}, "timestamp": "2026-10-22T10:01:00Z",
             "message": {"role": "user", "content": "please review the deck"}},
            {"type": "user", "origin": {"kind": "tool"}, "message": {"role": "user", "content": [{"type": "tool_result", "content": "SECRET TOOL OUTPUT"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": "SECRET ASSISTANT TEXT"}},
        ]
        (tdir / "s.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\nnot json\n")
        done = run(ACTIVITY, "--repo", repo, "--transcripts", tdir, "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        r = json.loads(done.stdout)
        self.assertTrue(r["git"]["is_repo"])
        self.assertIn("first commit", r["git"]["recent_commits"][0])
        self.assertEqual([p["directive"] for p in r["transcripts"]["human_prompts"]], [True, False])
        self.assertNotIn("SECRET", done.stdout)
        self.assertNotIn("transcripts", json.loads(run(ACTIVITY, "--repo", repo, "--json").stdout))  # opt-in only

    def test_run_checks_reports_pass_and_fail(self):
        repo = self.tmp / "r"
        repo.mkdir()
        (repo / "Makefile").write_text("test:\n\t@echo all good\n\nvalidate:\n\t@echo broken; exit 1\n")
        done = run(CHECKS, "--repo", repo)
        self.assertEqual(done.returncode, 1)
        self.assertIn("PASS  make test", done.stdout)
        self.assertIn("FAIL  make validate", done.stdout)
        empty = self.tmp / "e"
        empty.mkdir()
        self.assertEqual(run(CHECKS, "--repo", empty).returncode, 0)
        self.assertEqual(run(CHECKS, "--repo", self.tmp / "nope").returncode, 2)


class MarkdownTables(Fixtures):
    """The user's rule: tables are aligned, cells padded to the column, separator as wide as the column."""
    UGLY = "| # | Item | Verdict |\n|---|---|---|\n| 1 | **README does not say** what it is | apply |\n| 22 | short | skip: reason |\n"
    NICE = ("| #  | Item                               | Verdict      |\n"
            "|----|------------------------------------|--------------|\n"
            "| 1  | **README does not say** what it is | apply        |\n"
            "| 22 | short                              | skip: reason |\n")

    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(ROOT / "shared"))
        import mdtable
        self.m = mdtable

    def test_formats_like_the_editor(self):
        new, done, skipped = self.m.format_text(self.UGLY)
        self.assertEqual((new, done, skipped), (self.NICE, 1, 0))
        self.assertEqual(self.m.format_text(self.NICE)[0], self.NICE)  # idempotent

    def test_narrow_first_column_has_a_three_dash_separator(self):
        new, _, _ = self.m.format_text("| # | Item |\n|---|---|\n| 1 | x |\n")
        self.assertEqual(new, "| # | Item |\n|---|------|\n| 1 | x    |\n")

    def test_alignment_markers_wide_characters_escapes_and_code_blocks(self):
        src = ("| a | b | c |\n|:--|--:|:-:|\n| 1 | 22 | x \\| y |\n| 日本 | 3 | z |\n\n```\n| keep | this |\n|--|--|\n| ragged | x |\n```\n")
        new, done, _ = self.m.format_text(src)
        self.assertEqual(done, 1)
        self.assertIn("| keep | this |\n|--|--|\n| ragged | x |", new)  # fenced code untouched
        rows = [l for l in new.split("\n") if l.startswith("|") and "keep" not in l and "ragged" not in l and "--|--|" not in l or l.startswith("|:")]
        widths = {self.m.width(l) for l in rows[:4]}
        self.assertEqual(len(widths), 1, new)  # every row has the same display width
        self.assertIn(":-", new.split("\n")[1])
        self.assertIn("x \\| y", new)

    def test_row_with_extra_cells_is_reported_not_touched(self):
        src = "| a | b |\n|---|---|\n| 1 | 2 | 3 |\n"
        new, done, skipped = self.m.format_text(src)
        self.assertEqual((new, done, skipped), (src, 0, 1))

    def test_cli_check_and_fix(self):
        f = self.write("t.md", self.UGLY)
        self.assertEqual(run(MDTABLES, f).returncode, 1)
        self.assertEqual(run(MDTABLES, f, "--fix").returncode, 0)
        self.assertEqual(f.read_text(), self.NICE)
        self.assertEqual(run(MDTABLES, f).returncode, 0)
        self.assertEqual(run(MDTABLES, self.tmp / "nope.md").returncode, 2)

    def test_reports_written_by_the_scanner_are_aligned(self):
        f = self.write("s.md", "Certainly! Here is a plain summary of it.\n")
        out = self.tmp / "r.md"
        run(SCAN, f, "--out", out)
        self.assertEqual(run(MDTABLES, out).returncode, 0)
        self.assertEqual(run(MDTABLES, self.write("x.md", run(SCAN, f).stdout)).returncode, 0)

    def test_every_markdown_file_in_the_plugin_and_readme_is_aligned(self):
        root = ROOT.parents[1]
        self.assertEqual(run(MDTABLES, root / "README.md", ROOT).returncode, 0)


def png(color_type):
    import struct
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sIIBBBBB", 13, b"IHDR", 10, 10, 8, color_type, 0, 0, 0) + b"\0" * 20


class ClippedPictures(Fixtures):
    """--images --allow-clipped: cut-outs (PNG with transparency, straight-line outline) become pictures; nothing else."""
    def deck_with(self, name, color_type, ln=""):
        tri = freeform(5, rect=False).replace("</p:spPr>", ln + "</p:spPr>")
        d = self.tmp / name
        with zipfile.ZipFile(d, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("ppt/presentation.xml", f"<p:presentation {NS}/>")
            z.writestr("ppt/slides/slide1.xml", f"<p:sld {NS}>{tri}</p:sld>")
            z.writestr("ppt/slides/_rels/slide1.xml.rels",
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/></Relationships>')
            z.writestr("ppt/media/image1.png", png(color_type))
        return d

    def converted(self, d, *flags):
        done = run(FIX, d, "--images", *flags, "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)["fixes"]["images"]["freeforms converted to p:pic"]

    def test_cutout_png_converts_only_with_the_flag(self):
        d = self.deck_with("a.pptx", 6)
        self.assertEqual(self.converted(d), 0)
        self.assertEqual(self.converted(d, "--allow-clipped"), 1)

    def test_opaque_png_is_never_unclipped(self):
        self.assertEqual(self.converted(self.deck_with("o.pptx", 2), "--allow-clipped"), 0)

    def test_switched_off_outline_is_nothing_but_a_visible_one_blocks(self):
        off = '<a:ln cap="sq"><a:noFill/><a:prstDash val="solid"/></a:ln>'
        on = '<a:ln w="9525"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:ln>'
        self.assertEqual(self.converted(self.deck_with("n.pptx", 6, off), "--allow-clipped"), 1)
        self.assertEqual(self.converted(self.deck_with("v.pptx", 6, on), "--allow-clipped"), 0)

    def test_full_repair_passes_the_opt_in(self):
        d = self.deck_with("f.pptx", 6)
        work = self.tmp / "w"
        without = json.loads(run(FULL, d, "--workdir", work, "--json").stdout)
        self.assertEqual(without["stop_reason"], "nothing left that can be fixed automatically")
        self.assertIn("opt in with --allow-clipped", json.dumps(without["manual"]))
        work2 = self.tmp / "w2"
        with_flag = json.loads(run(FULL, d, "--workdir", work2, "--allow-clipped", "--json").stdout)
        self.assertTrue((work2 / "f-v1.pptx").is_file())
        rows = {r["signal"]: r["value"] for r in json.loads(run(INSPECT, work2 / "f-v1.pptx", "--json").stdout)["signals"]}
        self.assertEqual(rows["images as picture fill on a custom shape (invisible in many previewers)"], 0)


class FullRepair(Fixtures):
    def go(self, src, *args):
        work = self.tmp / "work"
        done = run(FULL, src, "--workdir", work, "--json", *args)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return work, json.loads(done.stdout)

    def test_new_version_per_round_and_the_original_is_untouched(self):
        src = self.tmp / "D.pptx"
        make_pptx(src)
        before = src.read_bytes()
        work, r = self.go(src, "--author", "Jane Doe")
        self.assertEqual(src.read_bytes(), before)
        self.assertTrue((work / "D-v1.pptx").is_file())
        self.assertEqual(r["latest"], str(work / "D-v1.pptx"))
        self.assertEqual(r["rounds"][0]["remaining_pct"], 100)
        self.assertLessEqual(r["rounds"][-1]["remaining_pct"], 40)
        for name in ("D-repair-log.md", "D-repair-log.json"):
            self.assertTrue((work / name).is_file())
        sys.path.insert(0, str(ROOT / "shared"))
        import mdtable
        self.assertTrue(mdtable.is_formatted((work / "D-repair-log.md").read_text()))  # the log obeys the table rule
        all_xml_parses(self, work / "D-v1.pptx")

    def test_what_a_person_must_do_is_listed_never_guessed(self):
        src = self.tmp / "D.pptx"
        make_pptx(src)
        _, r = self.go(src)  # no --author: the author stays empty and is listed
        steps = " | ".join(m["signal"] + " " + m["next"] for m in r["manual"])
        self.assertIn("ask who wrote the content", steps)
        self.assertIn("rewrite as presenter-voice", steps)  # the generator-facing speaker note
        with zipfile.ZipFile(r["latest"]) as z:
            self.assertIn("<dc:creator></dc:creator>", z.read("docProps/core.xml").decode())

    def test_ai_percentage_is_information_not_a_target(self):
        src = self.tmp / "AI.pptx"
        deck(src, [["Plain slide."]], [["The first reason is simple: it is incredibly common. So to wrap up, we absolutely agree. "
                                          "This is a big one: it is completely normal and a huge part of life today."]])
        work, r = self.go(src, "--target", "0")
        self.assertEqual(r["stop_reason"], "nothing left that can be fixed automatically")
        self.assertFalse((work / "AI-v1.pptx").exists())  # no version is made just to chase the AI score
        self.assertGreater(r["rounds"][0]["ai_signs"], 0)
        self.assertIn("never rewrites wording", (work / "AI-repair-log.md").read_text())

    def test_adopt_registers_a_hand_edit_as_the_next_version(self):
        src = self.tmp / "D.pptx"
        make_pptx(src)
        work, r = self.go(src, "--author", "A")
        edited = self.tmp / "edited.pptx"
        edited.write_bytes(Path(r["latest"]).read_bytes())
        work2, r2 = self.go(src, "--adopt", edited)
        self.assertTrue((work / "D-v2.pptx").is_file())
        self.assertEqual(r2["rounds"][-1]["applied"], "hand edit")
        self.assertEqual(len(r2["rounds"]), 3)  # original, v1, v2 (the log was continued)

    def test_target_and_rounds_are_respected_and_bad_input_refused(self):
        src = self.tmp / "D.pptx"
        make_pptx(src)
        work, r = self.go(src, "--target", "100")
        self.assertEqual(len(r["rounds"]), 1)
        self.assertTrue(r["stop_reason"].startswith("target reached"))
        for bad in (["--max-rounds", "9"], ["--target", "150"]):
            self.assertEqual(run(FULL, src, "--workdir", self.tmp / "w2", *bad).returncode, 2)
        txt = self.write("x.md", "hello")
        self.assertEqual(run(FULL, txt, "--workdir", self.tmp / "w3").returncode, 2)
        self.assertEqual(run(FULL, self.tmp / "nope.pptx", "--workdir", self.tmp / "w4").returncode, 2)

    def test_a_confirmed_author_gets_a_round_even_after_the_target_was_reached(self):
        src = self.tmp / "D.pptx"
        make_pptx(src)
        work, r = self.go(src)  # no author: the author defect stays open, the rest is fixed
        self.assertTrue(r["manual"])
        before = len(r["rounds"])
        work, r2 = self.go(src, "--author", "A B", "--target", "100")  # target already met, but a new input arrives
        self.assertEqual(len(r2["rounds"]), before + 1)
        with zipfile.ZipFile(r2["latest"]) as z:
            self.assertIn("<dc:creator>A B</dc:creator>", z.read("docProps/core.xml").decode())
        work, r3 = self.go(src, "--author", "A B", "--target", "100")  # same author again: nothing new
        self.assertEqual(len(r3["rounds"]), before + 1)

    def test_a_hand_edit_that_makes_the_counters_stale_is_caught_and_fixed(self):
        src = self.tmp / "D.pptx"
        make_pptx(src)
        work, r = self.go(src, "--author", "A")
        sys.path.insert(0, str(ROOT / "shared"))
        import mdtable
        self.assertTrue(mdtable.is_formatted((work / "D-repair-log.md").read_text()))  # props-only rounds leave no stray spaces
        edited = self.tmp / "e.pptx"
        with zipfile.ZipFile(r["latest"]) as a, zipfile.ZipFile(edited, "w") as b:
            for i in a.infolist():
                data = a.read(i.filename)
                if i.filename == "ppt/slides/slide1.xml":
                    data = data.replace(b"first point", b"first point plus four more words")
                b.writestr(i, data)
        _, adopted = self.go(src, "--adopt", edited)
        self.assertGreater(adopted["remaining_pct"], 0)
        self.assertIn("counters disagree", json.dumps(adopted["rounds"][-1]))
        _, fixed = self.go(src, "--target", "0")
        self.assertLess(fixed["remaining_pct"], adopted["remaining_pct"])
        self.assertEqual(len(fixed["rounds"]), len(adopted["rounds"]) + 1)
        rows = {r["signal"]: r["value"] for r in json.loads(run(INSPECT, fixed["latest"], "--json").stdout)["signals"]}
        self.assertEqual(rows["app.xml counters disagree with the file (after an edit)"], 0)

    def test_docx_uses_only_the_docx_fixes(self):
        src = self.tmp / "d.docx"
        make_docx(src)
        work, r = self.go(src, "--author", "A")
        self.assertTrue((work / "d-v1.docx").is_file())
        self.assertNotIn("--images", json.dumps(r["rounds"]))
        all_xml_parses(self, work / "d-v1.docx")


class OoxmlPack(Fixtures):
    def test_unpack_repack_ledger_roundtrip(self):
        src = self.tmp / "a.docx"
        docx(src, ["One two three", "Four five"])
        d = self.tmp / "u"
        self.assertEqual(run(PACK, "unpack", src, d).returncode, 0)
        self.assertNotEqual(run(PACK, "unpack", src, d).returncode, 0)  # not empty, no overwrite
        x = d / "word/document.xml"
        x.write_text(x.read_text().replace("Four five", "Four six seven"))
        out = self.tmp / "b.docx"
        self.assertEqual(run(PACK, "repack", src, d, out).returncode, 0)
        self.assertNotEqual(run(PACK, "repack", src, d, out).returncode, 0)
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(out) as b:
            self.assertEqual(a.namelist(), b.namelist())
        led = json.loads(run(PACK, "ledger", src, out, "--json").stdout)
        self.assertEqual(led["body"]["input_words"], 5)
        self.assertEqual(led["body"]["equal"], 4)
        self.assertEqual(led["body"]["rewritten"], 1)
        self.assertEqual(led["body"]["added"], 1)

    def test_unpack_rejects_zip_slip(self):
        evil = self.tmp / "evil.docx"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../evil.txt", "x")
        self.assertNotEqual(run(PACK, "unpack", evil, self.tmp / "e").returncode, 0)


class Language(Fixtures):
    def test_non_english_is_not_estimated(self):
        lv = ("Šodien es devos uz veikalu un nopirku trīs olas, jo mājās nekā nebija. "
              "Vakar lija lietus visu dienu, tāpēc mēs palīkam mājās un skatījāmies filmu. ") * 4
        self.assertIn("not estimated", run(SCAN, self.write("lv.txt", lv)).stdout)


class SelfTest(Fixtures):
    def test_selftest_runs_the_structure_check_even_without_renderers(self):
        done = run(SELFTEST, "--root", self.tmp)
        self.assertEqual(done.returncode, 0, done.stderr)
        for name in ("flow.mmd", "graph.dot", "seq.puml", "box.svg"):
            self.assertIn(f"{name} (structure check): ok", done.stdout)


class DiagramLint(Fixtures):
    def check(self, name, body):
        f = self.write(name, body)
        return run(DIAG, f, "--root", self.tmp, "--check-only").returncode

    def test_structure_check_without_renderer(self):
        self.assertEqual(self.check("a.mmd", "flowchart LR\n a[Start] --> b{OK?}\n"), 0)
        self.assertEqual(self.check("b.mmd", "flowchart LR\n a[Start --> b\n"), 3)
        self.assertEqual(self.check("c.mmd", "not a diagram\n"), 3)
        self.assertEqual(self.check("d.puml", "@startuml\nA -> B\n"), 3)
        self.assertEqual(self.check("e.dot", "digraph g { a -> b }\n"), 0)

    def test_unsafe_sources_are_refused(self):
        self.assertEqual(self.check("x.mmd", "flowchart LR\n a --> b\n click a href \"https://x.test\"\n"), 2)
        self.assertEqual(self.check("x.svg", '<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///etc/passwd"/></svg>'), 2)
        self.assertEqual(self.check("y.svg", '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>'), 2)


class PatternSamples(Fixtures):
    def test_every_sample_in_patterns_md_passes_the_check(self):
        import re
        text = (ROOT / "skills/generate-diagram/references/patterns.md").read_text()
        ext = {"mermaid": "mmd", "dot": "dot", "graphviz": "dot", "plantuml": "puml", "svg": "svg"}
        blocks = re.findall(r"```(\w+)\n(.*?)```", text, re.S)
        self.assertGreaterEqual(len(blocks), 8)
        for i, (lang, body) in enumerate(blocks):
            f = self.write(f"s{i}.{ext[lang]}", body)
            done = run(DIAG, f, "--root", self.tmp, "--check-only")
            self.assertEqual(done.returncode, 0, f"block {i} ({lang}): {done.stdout}{done.stderr}")


class BadInput(Fixtures):
    SCRIPTS = (SCAN, INVIS, TELLS, PACK, FIX)

    def test_missing_file_bad_zip_and_directory_give_one_line_not_a_traceback(self):
        bad = self.tmp / "bad.docx"
        bad.write_bytes(b"not a zip")
        for script in (SCAN, INVIS, FIX):
            for target in (self.tmp / "nope.docx", bad, self.tmp):
                args = [script, target] + (["--round-sizes"] if script == FIX else [])
                done = run(*args)
                self.assertEqual(done.returncode, 2, f"{script.name} {target.name}: {done.stderr or done.stdout}")
                self.assertNotIn("Traceback", done.stderr, f"{script.name} {target.name}")
        self.assertEqual(run(TELLS, self.tmp / "nope.md").returncode, 2)
        self.assertEqual(run(PACK, "ledger", bad, bad).returncode, 2)

    def test_prose_tells_refuses_office_files(self):
        f = self.tmp / "x.docx"
        docx(f, ["hello"])
        done = run(TELLS, f)
        self.assertEqual(done.returncode, 2)
        self.assertIn("scan_signs", done.stderr)

    def test_zip_bomb_is_refused(self):
        bomb = self.tmp / "bomb.docx"
        with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("word/document.xml", "<w:document/>")
            z.writestr("word/media/big.bin", b"\0" * (210 * 1024 * 1024))  # compresses to ~200 KB
        self.assertLess(bomb.stat().st_size, 1024 * 1024)
        for script in (SCAN, INVIS):
            done = run(script, bomb)
            self.assertEqual(done.returncode, 2, script.name)
            self.assertIn("refusing archive", done.stderr)
        self.assertEqual(run(FIX, bomb, "--round-sizes").returncode, 2)


class MetadataNames(Fixtures):
    def doc(self, core):
        d = self.tmp / "n.docx"
        docx(d, ["Plain words about eggs and bread on a Tuesday."], core=core)
        return d

    def test_person_named_claude_or_gemini_is_not_a_tool(self):
        d = self.doc("<dc:creator>Claude Bernard</dc:creator><cp:lastModifiedBy>Gemini Rossi</cp:lastModifiedBy>")
        self.assertIn("AI SIGNS FOUND: 0", run(SCAN, d).stdout)

    def test_tool_strings_in_tool_fields_are_signs(self):
        for core in ("<cp:lastModifiedBy>ChatGPT</cp:lastModifiedBy>", "<dc:description>Made with Claude Code</dc:description>"):
            self.assertIn("AI tool name in metadata", run(SCAN, self.doc(core)).stdout, core)

    def test_report_points_at_the_paragraph(self):
        d = self.tmp / "p.docx"
        docx(d, ["First paragraph is plain.", "Certainly! Here is a plain summary of it."])
        self.assertIn("word/document.xml ¶2", run(SCAN, d).stdout)


class Inspect(Fixtures):
    def signals(self, path):
        done = run(INSPECT, path, "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        return {r["signal"]: r["value"] for r in json.loads(done.stdout)["signals"]}

    def test_pptx_inventory(self):
        src = self.tmp / "i.pptx"
        make_pptx(src)
        before = src.read_bytes()
        s = self.signals(src)
        self.assertEqual(s["placeholder or future dates"], 2)
        self.assertEqual(s["author (dc:creator)"], "empty")
        self.assertEqual(s["fractional type sizes: rounding noise (sz within 2 of a multiple of 100)"], 1)
        self.assertEqual(s["fractional type sizes: other (left alone)"], 1)
        self.assertEqual(s["embedded fonts"], 1)
        self.assertEqual(s["fabricated font families (name ends in Bold/Italic)"], 1)
        self.assertEqual(s["typed bullets (should be list formatting)"], 3)
        self.assertEqual(s["generator-facing speaker notes"], 1)
        self.assertEqual(src.read_bytes(), before)  # read-only

    def test_docx_inventory_and_fix_clears_it(self):
        src = self.tmp / "i.docx"
        make_docx(src)
        s = self.signals(src)
        self.assertEqual(s["fabricated font families (name ends in Bold/Italic)"], 1)
        self.assertEqual(s["typed bullets (should be list formatting)"], 2)
        out = self.tmp / "i_fixed.docx"
        self.assertEqual(run(FIX, src, "--out", out, "--rename-font", "Georgia Bold", "Georgia", "--bold", "--bullets",
                             "--props", "author=A,date=today").returncode, 0)
        s2 = self.signals(out)
        self.assertEqual(s2["fabricated font families (name ends in Bold/Italic)"], 0)
        self.assertEqual(s2["typed bullets (should be list formatting)"], 0)
        self.assertEqual(s2["real list formatting"], 2)
        self.assertEqual(s2["placeholder or future dates"], 0)
        self.assertEqual(s2["author (dc:creator)"], "A")

    def test_language_tags_are_not_font_families(self):
        d = self.tmp / "l.docx"
        with zipfile.ZipFile(d, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", f'<w:document {WNS}><w:body><w:p><w:r><w:rPr><w:rFonts w:ascii="Georgia"/>'
                       '<w:lang w:val="en-GB" w:eastAsia="en-US"/></w:rPr><w:t>x</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(self.signals(d)["font families used"], 1)

    def test_not_a_package(self):
        bad = self.tmp / "x.docx"
        bad.write_bytes(b"nope")
        self.assertEqual(run(INSPECT, bad).returncode, 2)


class InvisiblePptx(Fixtures):
    def test_zero_width_in_slide_and_notes(self):
        src = self.tmp / "z.pptx"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("ppt/presentation.xml", f"<p:presentation {NS}/>")
            z.writestr("ppt/slides/slide1.xml", f"<p:sld {NS}><a:p><a:r><a:t>Hel\u200blo</a:t></a:r></a:p></p:sld>")
            z.writestr("ppt/notesSlides/notesSlide1.xml", f"<p:notes {NS}><a:p><a:r><a:t>no\u200bte</a:t></a:r></a:p></p:notes>")
        self.assertRegex(run(INVIS, src).stdout, r"\| zero-width\s+\| 2\s+\|")
        out = self.tmp / "z.clean.pptx"
        self.assertEqual(run(INVIS, src, "--clean", "--out", out).returncode, 0)
        all_xml_parses(self, out)
        with zipfile.ZipFile(out) as z:
            self.assertIn(">Hello<", z.read("ppt/slides/slide1.xml").decode())
            self.assertIn(">note<", z.read("ppt/notesSlides/notesSlide1.xml").decode())


def deck(path, slides, notes=()):
    """Minimal .pptx: slides and notes are lists of lists of paragraph strings."""
    para = lambda s: f"<a:p><a:r><a:t>{s}</a:t></a:r></a:p>"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/presentation.xml", f"<p:presentation {NS}/>")
        for i, paras in enumerate(slides, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", f"<p:sld {NS}>" + "".join(para(s) for s in paras) + "</p:sld>")
        for i, paras in enumerate(notes, 1):
            z.writestr(f"ppt/notesSlides/notesSlide{i}.xml", f"<p:notes {NS}>" + "".join(para(s) for s in paras) + "</p:notes>")


class Structure(Fixtures):
    def scan(self, path):
        done = run(SCAN, path, "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_repeated_sentence_and_openers_and_uniform_notes(self):
        slides = [["Brand %d" % i, "What happens", "Something specific %d occurs here today." % i, "Why it fits", "A reason number %d." % i] for i in range(1, 6)]
        same = "The category is an analysis of the purpose of this advertisement."
        notes = [[f"Audience {i} notes for the talk about this particular example and its context in detail. " + same +
                  " Extra words keep the notes about the same length every time."] for i in range(1, 6)]
        d = self.tmp / "s.pptx"
        deck(d, slides, notes)
        r = self.scan(d)
        self.assertIn("repeated sentence in 3+ units", r["categories"])
        self.assertIn("repeated unit opener (4+ slides)", r["categories"])
        self.assertIn("uniform note length (spread under 15%)", r["categories"])
        self.assertGreater(r["by_part"]["notes"]["estimate_pct"], 0)
        self.assertEqual(set(r["by_part"]), {"slides", "notes"})

    def test_short_sentence_run_and_style_rules(self):
        d = self.tmp / "r.pptx"
        deck(d, [["Eyes. Ears. Tail."]], [["The first reason is simple: it is incredibly common. So to wrap up, we absolutely agree."]])
        cats = self.scan(d)["categories"]
        self.assertIn("run of 3+ very short sentences", cats)
        self.assertIn("signposting phrase", cats)
        self.assertIn("intensifier", cats)

    def test_summary_says_it_is_a_floor_and_names_the_inspector(self):
        d = self.tmp / "f.pptx"
        deck(d, [["Plain words on a slide."]])
        out = run(SCAN, d).stdout
        self.assertIn("floor", out)
        self.assertIn("ooxml_inspect.py", out)

    def test_picture_fill_on_custom_shape_is_critical_plain_shape_is_not(self):
        d = self.tmp / "g.pptx"
        sp = lambda geom: ('<p:sp><p:spPr>' + geom + '<a:blipFill><a:blip r:embed="rId2"/></a:blipFill></p:spPr></p:sp>')
        with zipfile.ZipFile(d, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("ppt/presentation.xml", f"<p:presentation {NS}/>")
            z.writestr("ppt/slides/slide1.xml", f"<p:sld {NS}>" + sp("<a:custGeom/>") + sp('<a:prstGeom prst="rect"/>') + "</p:sld>")
        done = json.loads(run(INSPECT, d, "--json").stdout)["signals"]
        by = {r["signal"]: r for r in done}
        self.assertEqual(by["images as picture fill on a custom shape (invisible in many previewers)"]["value"], 1)
        self.assertEqual(by["images as picture fill on a custom shape (invisible in many previewers)"]["severity"], "critical")
        self.assertEqual(by["images as picture fill on a plain shape (valid; no crop or alt-text semantics of a picture)"]["value"], 1)


class Controls(Fixtures):
    """Smoke test for the rules: everyday and public-domain human text stays low, an AI-style paragraph stays high."""
    def pct(self, name):
        return json.loads(run(SCAN, Path(__file__).parent / "controls" / name, "--json").stdout)

    def test_human_controls_stay_low(self):
        for name in ("gettysburg.txt", "austen.txt", "biz.txt"):
            r = self.pct(name)
            self.assertLessEqual(r["estimate_pct"], 5, name)
            self.assertLessEqual(r["signs"], 3, name)

    def test_ai_style_paragraph_stays_high(self):
        r = self.pct("ai.txt")
        self.assertGreaterEqual(r["estimate_pct"], 50)
        self.assertGreaterEqual(r["signs"], 15)


class PdfScan(Fixtures):
    def test_pdf_text_is_scanned(self):
        import shutil
        if not (shutil.which("rsvg-convert") and shutil.which("pdftotext")):
            self.skipTest("needs rsvg-convert and pdftotext")
        svg = self.write("t.svg", '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">'
                                  '<text x="10" y="40" font-size="16">Certainly! Here is a plain summary.</text></svg>')
        pdf = self.tmp / "t.pdf"
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(pdf), str(svg)], check=True)
        self.assertIn("sycophantic opener", run(SCAN, pdf).stdout)


class Policy(Fixtures):
    def test_shared_policy_blocks_are_verbatim_in_skills(self):
        import re
        pol = (ROOT / "shared/policy.md").read_text()
        blocks = {m.group(1): m.group(2).strip("\n")
                  for m in re.finditer(r"<!-- block:(\w+) -->\n(.*?)\n<!-- /block -->", pol, re.S)}
        for skill, needs in (("repair-document", ["evasion", "disclosure"]), ("review-ai-content", ["evasion", "accuse"])):
            text = (ROOT / "skills" / skill / "SKILL.md").read_text()
            for b in needs:
                self.assertIn(blocks[b], text, f"{skill} lacks policy block {b}")

    def test_validator_passes(self):
        done = run(VALIDATE)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_disclosure_sentence_with_invisible_char_gets_a_note(self):
        f = self.write("d.txt", "AI was used here\u200b to draft.\n")
        self.assertIn("discloses AI use", run(INVIS, f).stdout)


class Misc(Fixtures):
    def test_check_tools_runs(self):
        self.assertRegex(run(TOOLS).stdout, r"\| Tool\s+\| Found\s+\|")

    def test_diagram_renderer_refuses_unsafe_plantuml(self):
        f = self.tmp / "x.puml"
        f.write_text("@startuml\n!include /etc/passwd\n@enduml\n")
        self.assertEqual(run(DIAG, f, "--root", self.tmp).returncode, 2)

    def test_marketplace_and_plugin_versions_match(self):
        m = json.loads((ROOT.parents[1] / ".claude-plugin/marketplace.json").read_text())
        p = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(m["plugins"][0]["version"], p["version"])
        for skill in (ROOT / "skills").iterdir():
            self.assertTrue((skill / "SKILL.md").is_file())
            self.assertIn(f"name: {skill.name}\n", (skill / "SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
