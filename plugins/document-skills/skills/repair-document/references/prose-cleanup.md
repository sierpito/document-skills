# Prose clean-up: opt-in editing for quality, never for evasion

Scope: how to edit wording once the user has allowed it. What to measure first, and what must never be changed,
is in `prose-metrics.md`.

Runs only when the user answered `prose_edits: yes` for this file. It is ordinary editing - cutting
filler and padding - so the text reads better. It is not a way to hide how the text was made, and the
report never says it is.

## What it does

The word and phrase lists live in one place, `shared/patterns.json` at the plugin root, used by this skill's
`prose_tells.py` and by `review-ai-content`. Add or change a pattern there, not in these tables.

1. **Filler vocabulary.** Flag and, with consent, replace or cut stock phrases that add no meaning (the
   list is in `shared/patterns.json`; patterns 7, 22 below). Replace with the plain word or delete; never
   swap in a synonym just for variety.
2. **Sandwich structure.** Intro sentence announcing the list, the list, then a sentence summarising it:
   drop the announcing and summarising sentences when they repeat what the list already says.
3. **Meta-commentary.** Cut "It is important to remember that...", "It is worth noting...".
4. **Passive voice.** Make a sentence active only when the actor is known from the file and the meaning
   does not change.
5. **Padding on slides.** Condense wording so it fits the box, never by dropping a fact, number or
   caveat.
6. **Terms of art and quotations stay.** Do not touch code blocks, front matter, quotes, citations,
   names, figures, legal or disclosure text.

Show each change as before/after in the report. Count words input, rewritten, added in the ledger.

## Pattern catalog (from the Humanizer skill, Wikipedia "Signs of AI writing")

Explanatory: this table says what each pattern means and how to fix it. The patterns the scripts match are in
`shared/patterns.json`, which is authoritative.

Use it to find passages worth editing and to name what was changed. A pattern is a reason to look, not
proof of anything; one hit in a long document means little. Edit only with `prose_edits: yes`.

| #  | Pattern                      | Tells                                                                   | Plain fix                                                   |
|----|------------------------------|-------------------------------------------------------------------------|-------------------------------------------------------------|
| 1  | Inflated significance        | "stands as", "pivotal moment", "setting the stage for", "marks a shift" | state the fact; cut the verdict                             |
| 2  | Notability name-dropping     | lists of outlets or names with no context                               | keep one source with what it said, or cut                   |
| 3  | Tacked-on -ing analysis      | ", highlighting...", ", ensuring...", ", fostering..."                  | make it its own sentence with a fact, or delete             |
| 4  | Promotional wording          | vibrant, nestled, breathtaking, renowned, rich                          | neutral description                                         |
| 5  | Vague attribution            | "experts believe", "industry reports", "studies show"                   | name the source, or mark as unsourced                       |
| 6  | Formulaic challenges         | "Despite challenges... continues to thrive"                             | state the actual problem and outcome, or cut                |
| 7  | Stock vocabulary             | delve, tapestry, testament, underscore, landscape (abstract), intricate | plain word                                                  |
| 8  | Copula avoidance             | "serves as", "boasts", "features", "stands as"                          | "is", "has"                                                 |
| 9  | Negative parallelism         | "not just X, but Y", "it's not X, it's Y"                               | say Y                                                       |
| 10 | Rule of three                | forced triplets of adjectives or points                                 | keep the true number of items                               |
| 11 | Elegant variation            | rotating synonyms for one noun                                          | repeat the noun                                             |
| 12 | False range                  | "from X to Y" with no scale between them                                | list the items                                              |
| 13 | Em-dash overuse              | several per paragraph                                                   | commas, periods or parentheses                              |
| 14 | Bold overuse                 | bold phrases mid-sentence                                               | plain text                                                  |
| 15 | Inline-header lists          | bullets of "**Label:** text" repeating the label                        | plain bullets, or prose                                     |
| 16 | Title Case headings          | in a document that otherwise uses sentence case                         | match the document's own style                              |
| 17 | Emoji in headings or bullets |                                                                         | remove, unless the document uses them everywhere on purpose |
| 18 | Mixed quote styles           | curly and straight in one file                                          | pick the file's majority style                              |
| 19 | Chatbot artifacts            | "I hope this helps", "Certainly!", "Let me know if"                     | delete                                                      |
| 20 | Cutoff disclaimers           | "as of my last update", "details are limited"                           | delete or replace with the real date and source             |
| 21 | Sycophancy                   | "Great question!"                                                       | delete                                                      |
| 22 | Filler phrases               | "in order to", "due to the fact that", "it is important to note that"   | "to", "because", delete                                     |
| 23 | Stacked hedging              | "could potentially possibly"                                            | one qualifier, or none if the claim is established          |
| 24 | Generic upbeat close         | "the future looks bright"                                               | cut, or end on the last concrete point                      |

Patterns 1-6 change meaning when removed badly: ask whether the claim is supported by the file first, and
if not, flag it as unsupported rather than rewriting it into a plain-sounding claim.

## Rewrite checks

After each edit, check against the original:

- the meaning, numbers, names, quotes and caveats are unchanged (diff them);
- it reads aloud without stumbling and uses the simplest verb that is true;
- no detail was invented to make it "specific": if a sentence is vague because the file gives nothing
  more, leave it and flag it ("needs a source from the author");
- the tone matches the document's own register (report, essay, UI copy), not a new voice.

Not adopted from Humanizer: adding opinions, first-person voice, mixed feelings or deliberate
looseness. That invents a persona the author did not write, and it is a way of looking human.

## Change summary

End the clean-up with a short list: pattern number and name, count, and one before/after example each.
Add it to the ledger as "best-effort changes" (`invisible-and-metadata.md`, section 5).

## Weighted scan and how to read it (from the unslop-text skill)

`scripts/prose_tells.py <file>` (read-only; `.md .txt .rst .html`) scores wording tells by weight (HIGH 3,
MEDIUM 2, LOW 1). The rules, weights and fixes are defined once in `shared/patterns.json`; do not copy them
here. It prints an edit score, a density per 1000 words, a verdict and the HIGH count as exit code. It skips front
matter, fenced code, backticks, quoted text, and any line containing `repair-ignore` (the author's way of keeping a
deliberate choice). Chat-residue rules (openers such as "Certainly!", offers such as "I hope this helps") count only
in the first or last sentence of a paragraph, so an ordinary email is not flagged.

Reading rules:

- **Judge by density and clustering, not pass/fail.** One "comprehensive" is ordinary writing. Em dashes and
  assistant boilerplate count on a single instance because they are rarely deliberate in generated text;
  still ask before removing em dashes the author may use on purpose.
- **A clean scan is not proof of anything.** It is a thin lexical filter; the structural tells below need a
  human read.
- **Avoid over-flagging.** Too many marginal flags teach people to ignore the report: show the top three
  changes and the HIGH items, and keep LOW items in the count only.
- **Never feed the score into a loop.** It is a guide for the editor, with no pass mark.

Structural tells the script cannot see (read aloud and report, edit only with `prose_edits: yes`):
uniform sentence rhythm (all short is as mechanical as all medium), sycophantic or yes-man tone, rule of
three and listicle scaffolding, the intro-three-points-conclusion skeleton, and fluent text that says
little. For the last one, ask what the claim is in one sentence; if it cannot be stated, flag the passage
as empty rather than polishing it.

## Fix rules (from unslop-text)

- **Lead with the plain fix.** Em dash to comma or period; "delve into" to "look at"; delete the
  sycophantic opener, the assistant offer and the recap.
- **Do not swap one tell for another.** "Dive into" for "delve into", or colons and ellipses to dodge
  dashes, only moves the tell.
- **Do not add costume.** No forced casualness, fake typos, sentence fragments for effect or lowercase
  starts. An over-corrected "anti-AI" voice is itself a recognisable tell, and adding it to look human is
  refused (`SKILL.md`, "Refuse").
- **Keep the document's register.** Pick the one it already has - casual, conversational-professional,
  expository or formal - and stay in it; a formal paper stays formal.
- **Leave alone:** deliberate author choices, quoted lines and backticked examples, `repair-ignore` lines,
  and lone generic words.
- **Output of an audit:** verdict and the single highest-impact change; findings by priority with
  `file:line` and the fix; edit score and density; the top three changes.

## What it does not do

- **No watermark or fingerprint breaking.** No swapping a percentage of words for synonyms, no flipping
  clauses, and no routing the text through another model "to alter its token distribution". Those
  steps exist only to defeat detection or provenance, and this skill refuses them. A
  `WATERMARKS_REWRITE_BACKEND`-style hook is not supported. Removing a provenance signal that the
  user asks about gets the same answer as in "Refuse" in `SKILL.md`: offer the repair work instead.
- **No cadence forcing.** Do not alternate sentence lengths on purpose. Vary them only where the meaning
  calls for it.
- **No score-chasing.** There is no pass threshold and no automatic second pass that runs until a
  number clears. The edit-density report below is for the person deciding what to edit.

## Edit-density report (`slop-check` equivalent)

For `check` runs on any file, report per section, as counts and not as a verdict on authorship: filler
phrases found, sandwich blocks, meta-commentary lines, passive sentences with a known actor, mean and
spread of sentence length, em-dash density. List the worst five passages with quotes. Say plainly that
these are editing findings and say nothing about who or what wrote the text.

## Rebuild per format, in place

- **Markdown:** parse with a Markdown parser; edit only paragraph and heading text; leave front matter,
  fenced and inline code, link targets and tables' structure byte-identical. Diff to confirm.
- **DOCX:** edit `w:t` text at run level inside the existing XML (python-docx or raw XML), including
  table cells, headers, footers, footnotes and comments you were asked to touch. Keep `w:rPr` and style
  ids. When a rewrite spans several runs, put the new text in the first run and empty the others; never
  rebuild the paragraph.
- **PPTX:** same at `a:t` level across slides, notes, and table cells; keep `a:rPr`, bullets and
  placeholders; re-render and run the wrapping check in `verification.md`, because shorter text should
  not shrink autofit or leave odd gaps.
- **PDF:** see `detect-pdf.md`.
