# Signals

The (script) patterns are defined in `shared/patterns.json` (plugin root), shared with `repair-document`;
change them there. This file lists what each means and the manual checks.

Weights: **S** strong (3), **M** medium (2), **W** weak (1). The scanner covers the ones marked (script);
check the rest by hand and add them as their own rows.

## Residue and tokens - S
- (script) Text addressed to a chat: "Certainly!", "Sure, here", "Here's a", "I hope this helps", "Let me know if",
  "As an AI", "I cannot", "my knowledge cutoff", "user-provided", "do not claim".
- (script) Tool and citation tokens: `oaicite`, `contentReference`, `turn0search`, `utm_source=chatgpt.com`,
  `[cite:`, `:contentReference[`, `<antArtifact`, `{{`/`}}` template leftovers, `[Insert ...]`, "Lorem ipsum".

## Markdown leakage - M
- (script) `**bold**`, `##` headings, `- ` lists, backticks or `---` rules appearing as literal text in a
  .docx/.pptx/.html text run.
- (script) Emoji or sparkle glyphs leading headings (U+2728, U+2705, U+1F680).

## Glyphs and watermark-like Unicode - M
- (script) Zero-width characters (U+200B, U+200C, U+200D, U+2060, U+FEFF) outside RTL/emoji use.
- (script) Unusual spaces (U+202F, U+2009, U+00A0 in density) and mixed straight/curly quotes in one document.
- (script) Arrows (U+2192) used as prose punctuation. Literal bullets are `repair-document` territory, not a sign.
- Note: Unicode inventory is a hint only; do not call it a watermark. Report "watermark-like".

## Style - W
- (script) AI tool names in body text. A topic mention (an essay about ChatGPT) or a disclosure naming its tool
  is not a sign: the scanner skips disclosure sentences, and you drop topic mentions by hand. In metadata
  (`app.xml`/`core.xml`) a tool name is a real sign.
- (script) Stock vocabulary, "not just X, but Y" frames, em dashes, recap and hedge phrases: the lists are in
  `shared/patterns.json`; here only the meaning: each is weak alone and counts per distinct rule.
- Em-dash density above ~3 per 1000 words (manual, from the em-dash count and word total).
- (script) Sentence-length SD under 4 words over 40+ sentences (document-level only).
- Rule-of-three lists, a closing sentence restating the heading, uniform bullet counts per slide.

## Metadata - M (document-level, not in percentage units)
- (script, docx/pptx) Placeholder dates (2006, 2011), empty author, `Words 0`, generator names in
  `app.xml`/`core.xml`, a single uniform `rsid` or none.

## False positives, do not count

- Date and slide-number fields in speaker notes ("1.7.2013", "‹#›"): dynamic fields with stale cached text; the scanner skips them.
- A cursor or highlight in a phone photo of a screen that looks like a broken glyph: not evidence of anything in the file.
- A figure from a third-party "AI score" tool: vibes; report the concrete fingerprints instead.

## Structural signals (script)

- Speaker notes written as a citation log (`Video:`, `Source:`, `Image source:`, `Audience:`) on 3+ notes.
- "X rather than Y" contrasts (weak) alongside "not just X, but Y"; em dashes (high in the edit scanner, weak in the review).

- Same sentence in 3+ notes or paragraphs (boilerplate); same opening label on 4+ slides; 5+ notes of nearly equal
  length; three very short sentences in a row; intensifiers and signposting phrases (weak, from `patterns.json`).

## Grill checklist

For `grill`, go through every flagged passage and also check, quoting and locating each finding:

- Claims that cannot be checked against anything in the file (statistics, dates, quotes, names): list them as
  unverified, not as false.
- Citations and links: do they look invented (plausible author, wrong journal)? Do not fetch anything; flag them.
- Template phrasing: rule-of-three lists, a summary sentence restating the heading, uniform bullet counts and
  lengths, every slide ending on a tidy takeaway.
- Consistency: the same fact stated differently in two places, terms that drift, years or units that disagree,
  notes that contradict the slide.
- Generic imagery: stock-style or generated images with no source, caption or licence; text rendered inside images.
- False positives to remove from the count with a note: quoted sources, legal or report templates, non-native stock phrases.

End with the questions for the user: who checked the facts, what was generated, what must be disclosed.

## Manual checks
- Image provenance: EXIF/XMP `DigitalSourceType`, C2PA/JUMBF boxes, PNG `parameters` chunks, filenames
  like `ChatGPT Image`, `Gemini_Generated`; visible badges and watermarks. Read locally only.
- Claims with no source (statistics, dates, quotes); citations that look plausible but unresolvable.
  Do not fetch; list as unverified.
- Internal contradictions, drifting terms, notes that contradict slides.

## Negative evidence (lowers confidence in AI, never proves human)
Wide sentence variance, idiosyncratic or learner errors, tracked changes, comments, real revision
history, specific local detail that is checkable.
