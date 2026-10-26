# Lessons learned (from the first improvement loops)

Distilled from two full loops (ten iterations) on this repository. Each line is something that changed what the loop
did next. Read them before the first iteration; add to them through `lessons.py` and copy the generic ones here.

## Reviewing

- **Run the real thing on real files.** Most bugs were found by running a script on the user's actual documents or on a
  deliberately hostile input, not by reading it: a wrong word counter (809 became 1146), `<w:tab/>` matched as `<w:t>`,
  language tags read as font names, a person called Claude flagged as an AI tool.
- **Verify a finding a second way before building on it.** One iteration "found" that picture fills were harmless
  rectangles; a per-shape parse showed they were not, and the item had to be corrected in the plan.
- **Compare a manual read with the tool.** The review script saw about 0% in two decks where a manual read found 18 and
  22 signs; the gap listed exactly which detectors to build (repeated sentences, equal-length notes, intensifiers).
- **Use controls.** Public-domain and everyday texts (a speech, a novel opening, a business email) must stay near zero;
  an AI-style paragraph must stay high. Put them in the tests before adding any new detector.
- **Test the failure paths.** Missing file, a non-zip `.docx`, a directory, an unwritable output folder, a zip bomb,
  a path with spaces, an empty file. Early scripts ended in tracebacks on all of them.

## Building

- **A detector without a fix leaves the loop open.** Detect, fix, re-detect: after `ooxml_inspect.py` named each
  problem, a flag in `ooxml_fix.py` removed it and the inspector confirmed it was gone.
- **Be conservative, count the unknowns.** A contrast check that guesses a background produces false alarms; one that
  skips unknown backgrounds and says "N skipped" does not. Prefer "not checked" to a wrong answer.
- **Do not suggest a fix that merely moves the problem.** Renaming "Arimo Bold" to "Arimo" still names a font that is not
  on a stock machine; the right answer was the metric-compatible Office font. Check where a fix lands.
- **Let the validator police the docs.** Paths, script names, flags and shared wording in the `SKILL.md` files are
  checked by `make validate`; every script must be mentioned in the tests. Drift is caught the day it happens.
- **One source for shared things:** patterns in one JSON file, refusal wording in one policy file with a verbatim test.

## Working with the user

- **Standing decisions are binding.** Examples recorded in this project: do not commit before the version is ready; no
  changelog; the percentage and count are the one score; calibration is deferred. Read them, do not ask again.
- **Do not ask what a default can answer.** Decide, apply, and list the few decisions that really are the user's at the end.
- **Say what was not run.** No LibreOffice, no renderers, an inconclusive Quick Look timeout: report each plainly and do
  not claim an improvement the experiment could not show.
- **When a delete or a command is blocked, stop and hand over the one command.** Overwrite instead of deleting where
  that is the intent; do not look for another route.
- **Keep estimates labelled.** A script figure is a floor; a manual estimate is a judgement. Show both, never merge them.
- **Format Markdown tables like the editor does.** Pad every cell to its column and make the separator as wide as the
  column; an unpadded `|---|---|---|` over ragged rows is wrong, and the user fixed it by hand until a formatter did it.
  Run `md_tables.py --fix` on every `.md` you write.
- **Look at the result.** Counters at zero are not a finished repair: a deck whose boxes were exactly as wide as their text
  wrapped titles and broke words in a real viewer while every check said 0. Render, view, and treat a user's screenshot as a
  detector gap: measure why the tools missed it, extend them, add a test, then repair.
