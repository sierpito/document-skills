---
name: review-ai-content
description: Reviews a document (.md, .txt, .html, .docx, .pptx, .pdf) for signs of AI-generated or AI-assisted content - stock vocabulary, template phrasing, chat residue, markdown leakage, citation/tool tokens, odd glyphs, zero-width characters, watermark-like Unicode, tool names and placeholder metadata, image provenance - and ends with a count of signs and an approximate percentage of the text that looks AI-generated or assisted. Read-only: it never changes the file (to fix or clean a file, use repair-document). Use when the user asks to "review", "check", "audit" or "grill" a document for AI content, AI signs or watermarks.
---

# review-ai-content

Read-only counterpart to `repair-document`. It looks, counts and reports; it never edits, repairs or
cleans the file, and it writes only to a report folder.

**What it can and cannot say.** The result is a judgement from signals, not detector proof. It does
not say who wrote the file, and a low number does not show human authorship. The percentage is an
estimate of how much text *looks* machine-written or machine-polished, with a range and a confidence.
Never present it as a detector verdict, and never as grounds to accuse a person.

## Run

1. Ask for nothing you can infer: the file path is enough. Optional: `depth` (`check` default, or
   `grill` for the deep pass below) and whether the destination is academic or regulated (adds the
   destination line).
2. Run the scanner (stdlib Python 3, no network, no installs):

   ```bash
   python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/review-ai-content/scripts/scan_signs.py" <file> [--json] [--media] [--out report.md]
   ```

   `--media` also reads image provenance markers in `word/media` and `ppt/media` (C2PA/JUMBF boxes, IPTC
   `DigitalSourceType`, PNG prompt chunks, generator filenames) by searching the bytes locally; it also
   reads `docProps/custom.xml` and comments. `--out` writes the review as a new Markdown file and refuses
   to overwrite one. Rules are in `${CLAUDE_PLUGIN_ROOT}/shared/patterns.json`, shared with `repair-document`.

   It reads `.md .txt .html .docx .pptx`; for `.pdf` it uses `pdftotext` if present, otherwise say the
   PDF text could not be read. Scanned PDFs with no text layer: report that, do not guess.
3. Read the output, then do the manual checks in `references/signals.md` that a script cannot: image
   provenance, unverifiable claims, invented citations, consistency, template rhythm. Add them to the
   counts as their own categories.
4. For `grill`, follow the "Grill checklist" in `references/signals.md`: quote every flagged passage, say which
   signs drove it, and remove false positives from the count with a note.
5. Report.

## Report - always in this order

1. **Header:** file, date, depth.
2. **Signs by category:** a table of category, count, two example locations. Categories are in
   `references/signals.md`.
3. **Summary** (the last block, always present):

   ```
   AI SIGNS FOUND: <n> in <w> words (<n per 1000 words> per 1000)
   APPROX. AI-GENERATED/ASSISTED CONTENT: ~<p>% (range <lo>-<hi>%), confidence <low|medium|high>
   DISCLOSURE IN FILE: <quote, or none>
   ```

   Then one sentence: "a judgement from signals, not detector proof".
4. **Open questions** for the user, only in `grill`: who checked the facts, what was generated, what
   must be disclosed.
5. For an academic, regulated or AI-policy destination, end with the destination line in
   `${CLAUDE_PLUGIN_ROOT}/skills/repair-document/references/report.md` ("Destination line"), word for word.

## How the percentage is made

The scanner splits text into units (paragraphs, bullets, table cells, speaker notes, slide titles),
scores each, and counts a unit as AI-looking at score 3+ (the low bound), 2+ (the estimate) or 1+ (the
high bound). Chat residue and tool tokens score 3, glyph and formatting leaks 2, and each distinct style
rule adds 1. Chat-residue phrases ("Certainly!", "I hope this helps") count only in the first or last sentence
of a paragraph, so an ordinary email is not flagged. Quoted passages (40+ characters between quotation marks),
block quotes, Word `Quote` styles and everything after a "References", "Bibliography" or "Literature" heading are
not scored; a disclosure is still found there. The percentage is the words in the sentences that carry a hit,
over total words, for units at or above the threshold. Tool names in body text (an essay about ChatGPT) are listed
as "mentioned, not counted"; in metadata or image names they are signs. Structural repetition is detected too:
a sentence of 6+ words that appears in 3+ units (its words count in the percentage), the same opening label on 4+
slides, 5+ speaker notes of nearly equal length, and runs of three very short sentences. The report also gives a
`BY PART` line (slides / notes / body / comments), because a deck's slide text and its notes can differ a lot. The
percentage is a floor: polished prose without lexical or structural tells is invisible to the script, which is why
the manual checks in `references/signals.md` still matter. Rules:

- Under 300 words, or fewer than 15 units: confidence is low and the report says "too short for a
  reliable estimate"; the range still comes from the scored units, never a made-up 0-100%.
- Text addressed to a chat, tool tokens and markdown leakage count as strong, near-certain signs.
- Style signs alone (a register word, an em dash) are weak and cannot push a unit past the estimate
  by themselves.
- A disclosure of AI use is reported, never counted for or against.
- Never inflate the number to look thorough, and never round a low-confidence result to a point value
  without its range.

## Fairness

Report concrete fingerprints (what, where, how many). Do not quote or chase third-party "AI smell scores": style-based detection is
unreliable, and this skill's own figure is a floor from signals, not detector proof.


Do not use the result to accuse a person; ask the author. Short texts, non-native writers and templated
writing (reports, legal text, student essays) raise false positives, so say so when it applies. The rules
are English only: for another language, report the signs but say the percentage is not estimated; when the
language is uncertain the report says so and the confidence drops.

## Refuse

Source: `${CLAUDE_PLUGIN_ROOT}/shared/policy.md` (the wording below is copied from it verbatim).

- Requests to use findings to "prove" that a named person used AI, or to rate a person. A result is a
  judgement from signals, not detector proof: offer the signal list and say to ask the author.
- Requests to make output "undetectable", "pass an AI checker" or "look human-written". Offer the
  repair work instead and explain the difference.
- Requests to break, strip or "defeat" linguistic watermarks or fingerprints: synonym swapping to shift
  token statistics, syntax inversion, routing text through a paraphrase backend, forced rhythm changes,
  or looping until a detector-style score passes. Offer plain editing (`prose-cleanup.md`) instead.
- If asked to also remove the signs, hand over to `repair-document`.
