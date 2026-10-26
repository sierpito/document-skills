# Detection and repair: PDF

A PDF is a rendered artifact, so detection is the main job and repair is limited.

- **Detect:** `pdftotext -layout` for text, `pdffonts` (unembedded or substituted fonts), `pdfimages -list`,
  `pdfinfo` (Producer, Creator, dates, Title, Author - placeholder or tool-generated values),
  XMP packets and any C2PA manifest. Report AI marks per `detect-ai-marks.md`. Scanned pages with
  no text layer: say OCR is needed, do not guess text.
- **Repair what is in the metadata:** write confirmed Author/Title and a real date to a copy with Python
  (`pypdf`), never touching page content; leave the original untouched in `input/`.
- **Prose changes:** in-place PDF text editing is fragile, so when `prose_edits` is yes, extract the text,
  apply `prose-cleanup.md`, and typeset a **new** PDF (reportlab or LaTeX, if installed) named
  `<stem>-clean.pdf`, and say it is a new document, not the original. Layout, images and fonts of the
  original are not preserved unless the user asks for them to be rebuilt.
- Needs `pypdf` or `pdfminer` and `reportlab`; check, do not install.
