# Changelog

All notable changes to this repository are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are the plugin version in
`.claude-plugin/marketplace.json` and `plugins/document-skills/.claude-plugin/plugin.json` (kept equal by `make validate`).
Add new entries under **Unreleased** as you work, and rename that heading to the version when you release.

## Unreleased

## 0.1.1

Commits: `c84f9c4` "Tune repair and review skills", `1d679b2` "Add document-skills marketplace: ..." (first public push).

### Added (c84f9c4)

- `repair-document` detection (`ooxml_inspect.py`): text padded with spaces to fake alignment; XML parts that do not parse, shape ids used
  twice on a slide and animation targets naming missing shapes (the file-level checks to run before blaming a viewer); `app.xml` that lists no
  slide titles; embedded fonts split into redundant (a defect) and non-standard (kept, it keeps the look).
- `repair-document` repair (`ooxml_fix.py`): `--spaces` (padding removed, text padded on both sides is centred), `--strip-all-embedded-fonts`,
  `buFont` before `buChar` for converted bullets, animation targets re-pointed when a group becomes a picture, real slide titles, fonts,
  theme and a `Paragraphs` count written to `app.xml`.
- `slide_preview.py` renders with LibreOffice and `pdftoppm` when installed (also off PATH, as on macOS), so every slide of a heavy deck
  renders; Quick Look remains the fallback. `check_tools.py` finds LibreOffice off PATH and reports a Python 3.10+ interpreter.
- `full_repair.py` log: file size, "Media changed" (a byte-compare of the media files), and a call-out when a hand edit adds em dashes.
- `review-ai-content`: speaker notes written as a citation log (`Video:`, `Source:`, `Image source:`, `Audience:` on 3+ notes) and "X rather than
  Y" contrasts as signs.
- Guidance: a "Working with the user" section, the policy for rewriting notes and template variation (only with consent), the XML
  string-surgery technique, a seven-step verification pass, and a "do not flag" list.

### Changed (c84f9c4)

- `--strip-embedded-fonts` removes only redundant embedded fonts; a font that is not on a stock install stays embedded. Once nothing is
  embedded the `saveSubsetFonts` / `embedTrueTypeFonts` flags are removed too.
- `--fit` widens a tight box by at least 0.5 in as well as 12%.
- `--props` and the scanners skip date and slide-number fields in speaker notes ("1.7.2013", "‹#›"): they are dynamic fields, not content.
- Real names in the test fixtures replaced by "Jane Doe".

### Added (1d679b2, first public version)

- Marketplace `document-skills` with one plugin and four skills:
  - `repair-document`: detect, repair and verify machine-generation defects in .pptx and .docx (fonts, sizes, images to real pictures, text fit,
    contrast, bullets, metadata, speaker notes), checks for .html, .md, .pdf and text, and a full mode that repairs and reviews in rounds with
    a new version per round (`D-v1.pptx`, `D-v2.pptx`); the AI percentage is shown for information and is never an exit target.
  - `review-ai-content`: read-only count of AI signs and an approximate AI-looking share with a range, by part, with structural, image and
    metadata checks.
  - `generate-diagram`: Mermaid, Graphviz, PlantUML and SVG source with a safety and structure check and local rendering.
  - `improve-skills`: up to five improvement iterations (review from scratch, plan with an item count, apply, run the checks), learning from
    recent activity through a lessons and standing-decisions file.
- Standard-library scripts for each skill, shared pattern rules (`patterns.json`), shared refusal and fairness wording (`policy.md`) and the
  Markdown table formatter (`mdtable.py`).
- 109 tests (`make test`) and a marketplace validator (`make validate`, also runs `claude plugin validate`).
- Apache-2.0 license, copyright Igor; README with install lines for `sierpito/document-skills`.
