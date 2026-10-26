# Report format

Every report, check or repair, has this shape.

## Header and AI score

Open with the file header (file name, date, mode), then the AI score. **The score comes from
`review-ai-content`**, so one file never gets two different numbers: run its `scan_signs.py` on the
input as received and paste its last block:

```
AI SIGNS FOUND: <n> in <w> words (<n> per 1000)
APPROX. AI-GENERATED/ASSISTED CONTENT: ~<p>% (range lo-hi%), confidence <low|medium|high>
DISCLOSURE IN FILE: <quote, or none>
```

followed by "a judgement from signals, not detector proof". Score the input as received, never the
repaired output: repair removes fingerprints, so scoring the output would only measure the repair. The
score never states or implies who wrote the file.

## The four parts

1. **Findings** - every signal with a count, before any repair.
2. **Change log** - in numbers ("196 typeface references renamed", "10 image groups converted").
3. **Provenance ledger** - measured by diffing output against input, never estimated: words from the
   input, rewritten and added, for body text and for notes separately.
4. **What remains** - structural signals that cannot be repaired, and any regression you introduced
   and could not fix.

Split changes into **verified** (counts from scripts and diffs), **best-effort** (judged, such as
notes rewritten) and **out of scope / residual** (`references/invisible-and-metadata.md`, section 5).

## Destination line

For an academic, regulated or AI-policy destination, end with exactly this line and no argument:

> This file was processed with automated tools; that is not a disclosure of AI use, and whether and how to
> disclose is the author's decision.

`review-ai-content` appends the same line for such destinations.
