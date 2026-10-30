---
name: repair-document
description: Finds and repairs machine-generation defects in .pptx and .docx files (fonts that do not resolve, invisible images, fractional type sizes, colliding boxes, failing contrast, direct formatting instead of styles, fake bullets, placeholder metadata, chat residue), and checks .html, .md, .pdf and text files for the same signals, in three passes (detect, repair, verify) on a working copy, reporting exactly what changed; a full mode loops repair and review and writes a new version per round (D-v1.pptx, D-v2.pptx). Use when the user asks to "repair", "fix" or "clean up" a generated document or deck (it changes a copy of the file; to only count AI signs without changing anything, use review-ai-content). Refuses to make text "undetectable" or to fake authorship.
---

# repair-document

Works on a copy in a working folder. It may: create one working folder (see "Working folder"), copy
the file the user hands it into it, unpack, edit and repack that copy, and run local converters on it.
It must never: modify the original, write outside the working folder, use the network, take an
outward action (Confluence, Jira, Slack, mail, notifications), read credentials or env files, or
remove a sensitivity label without the user's explicit ask for that file.

**Repair the artifact, report the authorship.** A generated file is usually a broken file: fonts
that resolve nowhere, images no previewer can see, 24.99pt type, colliding text, 1.8:1 contrast,
metadata claiming 2006. Fixing those is ordinary document work. That it also removes generation
fingerprints is a side effect; it is never proof of human authorship.

| Does                                                                      | Refuses                                                         |
|---------------------------------------------------------------------------|-----------------------------------------------------------------|
| Fix broken fonts, geometry, colour contrast, bullets, styles, images      | Rewrite prose to defeat a detector                              |
| Replace placeholder metadata with accurate, confirmed values              | Insert an author who did not write the content                  |
| Report sensitivity labels and tenant ids; remove one only on explicit ask | Remove a disclosure, licence, citation or attribution           |
| Rewrite generator-facing text never meant for a reader                    | Claim or imply the result is human-written                      |
| Report exactly what changed and who wrote what                            | Silently clean a file headed for graded or regulated submission |

## Route by file type

| File             | Detect                                                                                         | Repair                                                       |
|------------------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| .pptx            | `references/detect-pptx.md`                                                                    | `references/repair-pptx.md`                                  |
| .docx            | `references/detect-pptx.md` (shared `docProps` and glyph checks), `references/docx-html-md.md` | `references/repair-docx.md`                                  |
| .html, .md, .txt | `references/docx-html-md.md`                                                                   | glyph cleanup and, if allowed, `references/prose-cleanup.md` |
| .pdf             | `references/detect-pdf.md`                                                                     | metadata on a copy; prose only as a new typeset file         |

Every file also gets: AI marks (`references/detect-ai-marks.md`), invisible characters and provenance metadata
(`references/invisible-and-metadata.md`), the AI score from `review-ai-content`, and the report in
`references/report.md`.

## Commands

Scripts live in the plugin; run them with Python 3 (stdlib only), never from inside an untrusted folder:

```bash
R="${CLAUDE_PLUGIN_ROOT}/skills/repair-document/scripts"
python3 -I "$R/check_tools.py"                        # which tools exist (installs nothing)
python3 -I "$R/full_repair.py" FILE --workdir DIR [--target 10] [--author NAME]   # full mode: D.pptx -> D-v1.pptx, D-v2.pptx, ... + log
python3 -I "$R/full_repair.py" FILE --workdir DIR --adopt EDITED_FILE             # register a hand edit as the next version
python3 -I "$R/slide_preview.py" FILE.pptx --slide N --out DIR                # render one slide to a PNG (LibreOffice if installed, else Quick Look) and LOOK at it
python3 -I "$R/slide_preview.py" FILE.pptx --all --out DIR --renderer soffice       # every slide, LibreOffice + pdftoppm
python3 -I "$R/ooxml_inspect.py" FILE                 # detect pass for .pptx/.docx: every signal with a count (read-only)
python3 -I "$R/invisible_chars.py" FILE               # inspect invisible characters (read-only)
python3 -I "$R/invisible_chars.py" FILE --clean --out WORKDIR/out/NAME   # cleaned copy, never overwrites
# deterministic pptx/docx fixes, a count for each; without --out it is a dry run that writes nothing
python3 -I "$R/ooxml_fix.py" FILE --out OUT --round-sizes                       # pptx: 24.99pt -> 25pt
python3 -I "$R/ooxml_fix.py" FILE --out OUT --rename-font "Times New Roman Bold" "Times New Roman" --bold
python3 -I "$R/ooxml_fix.py" FILE --out OUT --normalize-fonts                    # "X Bold" -> X + bold; Arimo/Tinos/Carlito -> Arial/Times New Roman/Calibri
python3 -I "$R/ooxml_fix.py" FILE --out OUT --strip-embedded-fonts                  # redundant embedded fonts only; a non-standard font stays embedded
python3 -I "$R/ooxml_fix.py" FILE --out OUT --strip-all-embedded-fonts              # every embedded font (the look falls back to what the viewer has)
python3 -I "$R/ooxml_fix.py" FILE --out OUT --spaces                               # pptx: padding spaces used to fake alignment removed (both sides: centred)
python3 -I "$R/ooxml_fix.py" FILE --out OUT --images                            # pptx: picture-filled rectangle freeforms -> p:pic
python3 -I "$R/ooxml_fix.py" FILE --out OUT --fit                               # pptx: boxes with no slack for their text widened (estimate; look at the slide)
python3 -I "$R/ooxml_fix.py" FILE --out OUT --contrast                          # pptx: failing text colours -> 4.6:1 (known backgrounds only)
python3 -I "$R/ooxml_fix.py" FILE --out OUT --bullets                           # typed bullets -> real lists
python3 -I "$R/ooxml_fix.py" FILE --out OUT --props author=NAME,date=today      # only with a confirmed author
python3 -I "$R/ooxml_fix.py" FILE --report-notes                                # generator-facing notes (report only)
python3 -I "$R/ooxml_pack.py" unpack|repack|ledger ...    # safe unpack, in-order repack, words kept/rewritten/added
python3 -I "$R/prose_tells.py" FILE                   # weighted wording tells for the edit-density report
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/review-ai-content/scripts/scan_signs.py" FILE   # AI signs count and percentage
```

## Full mode

For `depth: full` follow `references/full-repair.md`. In short: `full_repair.py` repairs and reviews in rounds and writes
`<stem>-v1`, `-v2`, ...; it stops when at most `--target` percent (default 10) of the starting defects are open, when nothing
more can be fixed automatically, or after 5 rounds; the AI review is shown every round for information and is never the
target (lowering it would mean rewriting wording to defeat a detector, which is refused). When it stops, report the table,
list what is left for a person, and **ask the user whether a better result should be pursued** before doing more.

## Inputs - ask once, together, skip what the request already says

Put every question in one message, each with its default. Do not ask what the user already stated.

- **author** - who actually wrote the content (not who sends the file). Write it only after the user
  confirms it; a name the user states in the request ("author: Jane Doe") counts as confirmed, and
  is written to `dc:creator` and `cp:lastModifiedBy` (`Manager` and `Company` stay untouched).
  If it differs from the sender, or nobody confirms, leave the field empty and say so.
  **Dates:** a placeholder or impossible date (2006, 2011, a future date) is replaced with today's
  date, since it is not a real save time; a plausible date is kept. Never backdate to look older,
  never invent revision counts.
- **destination** - internal, client, publication, academic submission, regulated filing. Academic,
  regulated or AI-policy destinations add the disclosure line to the report.
- **prose_edits** - may wording be touched at all? Default no, beyond chat residue. If yes, follow
  `references/prose-cleanup.md`. Speaker notes are the exception: when the user asks for notes "a
  presenter would actually say", or the notes are generator-facing, rewrite them
  (`references/repair-pptx.md`, "Speaker notes").
- **depth** - `check` (detect and report), `repair` (default), `full` (the loop in `references/full-repair.md`: repair and
  review in rounds, a new file per round, stop at a target or when nothing more can be fixed, then ask the user whether
  to go further) or `grill` (deep AI-content review). "Full", "deep" or "complete" repair means `full`.
  "Review", "grill" or "check deeper" means `grill`: run `review-ai-content` in its grill mode and put its
  summary block and open questions in the report; do not keep a second checklist here.
- **glyph cleanup** - inspect with `invisible_chars.py`, then remove literal bullet characters (U+2022)
  in favour of real list formatting, arrows used as prose punctuation (U+2192 and similar) and
  zero-width characters? **Default yes.** Keep joiners in RTL text and emoji sequences.
- **labels** - a sensitivity label is reported. Remove it only if the user explicitly asks for this
  file (`references/repair-pptx.md`, "Metadata and labels").

If the user cannot be reached, repair with author empty, glyph cleanup at its default, labels
untouched, and list the unanswered inputs at the top of the report.

## Working folder

Create one working folder, `<file stem>-repair/`, in this order of preference:

1. **The session scratchpad**, unless the user asks for the result next to the original.
2. **`plans/repair/`** in the current project, when git ignores it
   (`git check-ignore -q plans/repair/x` exits 0).
3. **Next to the original** (`<folder>/<file stem>-repair/`) when the user asks for it and the folder
   is writable. If it is inside a git repository and not git-ignored, say the folder could be
   committed and offer the scratchpad first.

If the folder already exists, add the date to its name rather than reuse it. Inside it: `input/` (an
untouched copy of the original), `unpacked/`, `out/` and `render/`. The original file is never
modified, moved or overwritten; the repaired file is `out/<name>`. Delete only named files you created
inside the working folder, never with `-r`; repack with Python so nothing needs deleting.

Before unpacking, check every archive member path: reject the file if any path is absolute or
contains `..` (zip slip).

## Tools - check, do not install

macOS quirks that look like "tool missing": LibreOffice is often installed but not on PATH (`check_tools.py` and `slide_preview.py`
find `/Applications/LibreOffice.app/Contents/MacOS/soffice`; to call it yourself, add that folder to PATH), and the Anthropic pptx
skill's own scripts (`thumbnail.py`, `soffice.py`, `validate.py`) need Python 3.10+ while the system `python3` may be 3.9: use a
venv from `python3.13`. This skill's bundled scripts need only 3.8+. A blocked `rm` is a permission decision, not an obstacle:
nothing here needs a delete (versions are new files, repacking writes a new archive), so do not route around it.

Run `scripts/check_tools.py`. It lists Python modules and binaries (python-pptx, lxml, Pillow,
defusedxml, LibreOffice, poppler, optional qpdf and exiftool) and what each unlocks. If one is missing,
say which checks you cannot run and ask before installing anything. Run `soffice` headless only
(`--headless --norestore`), never with macros, never on files the user did not hand over.

The schema validator is the Anthropic pptx skill's `scripts/office/validate.py`. Find it with
`find ~/.claude* -path '*pptx/scripts/office/validate.py'`; run it read-only (never `--auto-repair`).
If it is not found, fall back to the package audit in `references/verification.md`.

## Three passes - never skip to fixing

1. **Detect.** For .pptx/.docx run `scripts/ooxml_inspect.py` on the copy; it inventories the signals in the
   reference tables with counts. Add what it cannot see (render, overlap, contrast) from `verification.md`. Report
   findings with counts before touching anything.
2. **Repair** in dependency order (structure, geometry, type, colour, metadata), re-validating and
   re-rendering after each group. Snippets: `references/snippets.md`.
3. **Verify.** Validate the package, render it, measure the render, diff against the input, and
   report regressions you caused: `references/verification.md`.

## Rules

- Never change the substance of the content: fix how it is built, not what it says. Rewriting a
  sentence to read as less machine-like is out of scope; rewriting text addressed to the chat or the
  generator (speaker notes saying "user-provided", "do not claim", "as an AI"; "Certainly! Here's...";
  "Let me know if...") is in scope and counts as "rewritten" in the ledger.
- Verify every factual claim you can check against the file's own evidence before touching the text
  around it.
- Keep every repair diffable against the untouched input.
- The structural signals (absolute positioning, no layout placeholders, inline typefaces) cannot be
  repaired without rebuilding the file. Report them; rebuilding is a separate job the user must ask
  for.

## Working with the user

- **Check their numbers before acting.** "Six slides use this pattern" may be five: say so and proceed on the real five.
- **Report concrete fingerprints, not smell scores.** Structural and metadata findings are facts; third-party "AI scores" and
  style-based text detection are unreliable. Still fix the legitimately formulaic patterns they ask about.
- **Layout and metadata fixes can go ahead; rewriting their words cannot.** On-slide text, speaker notes and template variation
  across repeated slides change their content: ask first, show before and after.
- **When someone reports corruption in another app**, rule out file-level causes first (`ooxml_inspect.py`: well-formed XML,
  unique shape ids, animation targets, relationships, untouched media and fonts byte for byte), then fix the likely real cause
  (a font that is not on the viewer's machine) and ask them to reopen a fresh copy. For a phone photo of a screen, ask for the
  app and version, whether a repair dialog appears, and a fresh screenshot before assuming corruption: a text cursor or a
  highlight can look like a broken glyph.
- **Re-measure after any content change.** Swapping the text of two slots, or lengthening a sentence, can make a label wrap or a
  body outgrow its box: run `ooxml_inspect.py` (or `--adopt` through `full_repair.py`) again and look.
- **Never introduce em dashes in your own rewrites** (a period, colon, comma or parentheses); a hand edit that adds some is
  called out by `full_repair.py`.

## Look at the slides

LibreOffice and Quick Look are proxies for PowerPoint: name the renderer, and do not claim it is PowerPoint. Static checks are estimates and a deck can look broken to a person while every counter says 0. Before calling a .pptx repaired,
render the slides with `slide_preview.py` and **view the PNGs** (the Read tool shows images): the titles, the brand names, any
slide that had picture fills or overlap findings, at least one slide per layout. Compare with the original's render. If you
can see wrapped titles, broken words, overlapping text, missing pictures or wrong fonts, it is not finished: fix, make the next
version, look again. If no previewer answers, say so; that is not a pass. When the user shows a screenshot of a defect, treat it
as a detector gap: measure why the tools missed it, extend them, add a test, then repair the file.

## Always check, on every pptx

Every run answers these five and reports each as pass or fail:

1. **AI marks** - visible symbols, watermarks and badges, tool names in metadata, image provenance
   (`references/detect-ai-marks.md`).
2. **Notes** are in a presenter's voice, not the generator's (find the generator-facing ones with `ooxml_fix.py FILE --report-notes`).
3. **Properties** carry the confirmed author and a real date, no placeholders.
4. **Fonts** resolve in a clean environment (no fabricated families, theme and run fonts agree).
5. **Previewers and wrapping** - every image is a real picture that previewers show, and no text
   wraps or overflows its box (`references/verification.md`).

## Refuse

Source: `${CLAUDE_PLUGIN_ROOT}/shared/policy.md` (the wording below is copied from it verbatim).

- Requests to make output "undetectable", "pass an AI checker" or "look human-written". Offer the
  repair work instead and explain the difference.
- Requests to break, strip or "defeat" linguistic watermarks or fingerprints: synonym swapping to shift
  token statistics, syntax inversion, routing text through a paraphrase backend, forced rhythm changes,
  or looping until a detector-style score passes. Offer plain editing (`prose-cleanup.md`) instead.
- Requests to strip a required disclosure or to backdate authorship. Disclosures (an AI-use statement,
  C2PA or IPTC `DigitalSourceType` provenance, a licence, a citation) are reported and kept.
