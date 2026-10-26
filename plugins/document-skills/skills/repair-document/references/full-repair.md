# Full repair mode (`depth: full`)

A loop that repairs and reviews a .pptx or .docx until little is left to fix, writing a new file for every round and
never touching the original: `D.pptx` becomes `D-v1.pptx`, `D-v2.pptx`, ... in the working folder.

## What one round does

1. **Inspect** the latest version (`ooxml_inspect.py`): every signal with a severity.
2. **Fix** everything the findings call for that is deterministic (`ooxml_fix.py`): rounding noise in type sizes,
   fake or look-alike font families, embedded fonts, picture-filled rectangle freeforms, failing literal colours, typed
   bullets, placeholder properties and counters. A dry run decides first; a round that would change nothing is not written.
3. **Write** the result as the next version.
4. **Review** the new version: inspect again for the defect score, and run `review-ai-content` (`scan_signs.py`).

`scripts/full_repair.py FILE --workdir DIR` runs the rounds. Options: `--target 10` (default), `--max-rounds 5`
(default and maximum), `--author NAME` (only once the user has confirmed who wrote the content), `--json`.

## When it stops

| Reason                                       | Meaning                                                                          |
|----------------------------------------------|----------------------------------------------------------------------------------|
| target reached                               | open defects are at most `--target` percent of the starting defects (default 10) |
| nothing left that can be fixed automatically | the rest is listed under "Left for a person", with the next step                 |
| reached `--max-rounds`                       | the loop is capped at 5 rounds                                                   |

The **defect score** is the sum over open findings of critical 5, high 3, medium 1, each signal counted once; "remaining"
is the score of the latest version over the score of the original. Findings that are legitimate by nature (links to
outside resources) are not counted.

## The AI percentage is not the target

The review runs every round and its figures are in the log (signs, estimate with range, residue signs), but the loop never
tries to bring that percentage down and never exits on it. Lowering it would mean rewriting wording so that a detector
reads it differently, which this skill refuses (`SKILL.md`, "Refuse"). What it does fix is what is legitimately a defect:
generator-facing text, placeholder metadata, invisible characters. If the user wants wording edited for quality (filler,
padding, passive voice), that is a separate, consented step (`prose-cleanup.md`), done by hand and registered with
`--adopt`, still without a score target.

## Work the agent does between rounds

1. Run `full_repair.py` and read the table and "Left for a person".
2. For each manual item, decide whether it needs the user:
   - author empty: ask who wrote the content; rerun with `--author` only after they confirm;
   - generator-facing notes: with consent for prose edits, rewrite them as presenter-voice text (`repair-pptx.md`,
     "Speaker notes") into a new file, then `full_repair.py FILE --workdir DIR --adopt EDITED` to register it as the next
     version and review it;
   - font with no safe replacement: ask which installed font to use, then apply `ooxml_fix.py --rename-font OLD NEW` to
     the latest version and `--adopt` the result;
   - boxes off the slide or overlapping: check in a render, fix by hand, `--adopt`.
3. Rerun without `--adopt` to let the automatic fixes catch up, if the manual edit changed anything they handle.

## Look before you stop (pptx)

When the numbers reach the target, render with `slide_preview.py` (Quick Look) and view the slides: every slide with a title, a
brand name or picture fills, plus one per layout. Static estimates (`--fit`, contrast, overlap) can miss what the eye sees,
and an original that showed no pictures at all in Quick Look (picture fills inside groups) is evidence the fix worked when they
appear. Anything visibly wrong is a defect even at 0%: fix it, write the next version, look again. Say plainly when no
previewer answered.

## After the loop: always ask

Report the table, the latest version, what is left and why. Then ask the user, in one question with options, whether a better
result should be pursued: lower the target, work through the listed manual items now, allow plain wording edits, or stop.
Do not continue past the question without an answer; a "stop" ends the mode and the latest version is the result.

## Files

`<stem>-vN.<ext>` per round; `<stem>-repair-log.md` (aligned table of rounds, what was applied, what is left for a person) and
`<stem>-repair-log.json` (the same data, and the baseline the next run continues from). A rerun with the same working folder
continues the numbering and the baseline.
