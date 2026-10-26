# Prose: measure everything, change almost nothing

Scope: what to measure and what may never change. How to edit when editing is allowed is in `prose-cleanup.md`.

Measure prose because the numbers are diagnostic, and report them. What you do with them is tightly
limited.

Measure per document and per section:

- **Sentence length mean and standard deviation.** Generated prose clusters: a standard deviation
  under about 4 words over 40+ sentences is a strong signal.
- **Em-dash density** (U+2014) per thousand words, spaced or unspaced.
- **Repeated n-grams** - identical 4+ word strings recurring across sections.
- **Unicode inventory** - every code point above 127 with counts. Surfaces zero-width characters,
  mixed quote styles and stray arrows in one pass.
- **Register vocabulary** - stock words and frames; the list is `shared/patterns.json`, scanned by
  `scripts/prose_tells.py` and `review-ai-content`.

**May change:** text addressed to the chat rather than the reader - opening acknowledgements, closing
offers of help, instructions to itself, hedges that only make sense as grounding notes. Example:
speaker notes reading "Source: user-provided IMG_1971.jpg... do not claim all were recorded on one
confirmed day" were never meant for a presenter.

**Must not change:** everything else - sentence rhythm, vocabulary, em dashes, structure - when the
only reason is that a detector might notice.

Why: rewriting prose to look human is writing the document again, in a register chosen to defeat a classifier.
Even rewritten text that scores as "human" on a measurement was still written by a model; the measurement only
shows that it can be gamed. Report the numbers, fix the chat residue, leave the prose to the person whose name is on it.

## Deep review

The deep review (`grill`) lives in `review-ai-content` (`references/signals.md`, "Grill checklist"). Run it
there; this skill only reports its result.

## AI score

The report's score comes from `review-ai-content` (`scripts/scan_signs.py`): a count of signs and an
approximate percentage with a range and a confidence. Do not keep a second scale here. What this skill
measures (sentence-length spread, em-dash density, repeated 4-grams, register words, chat residue) feeds
that scan through the shared pattern file `shared/patterns.json`; read its rubric in
`review-ai-content/SKILL.md`. Never present the result as a detector verdict, and never use a low
percentage to argue authorship.
