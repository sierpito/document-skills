---
name: improve-skills
description: Runs an improvement loop on a repository of skills, scripts and docs - up to 5 iterations of "drop the old plan, review from scratch on real inputs, write a new plan with an item count, apply every reasonable fix, run the checks, restart" - and learns from recent activity (git history, changed files, and what the user typed in recent sessions) by keeping a lessons and standing-decisions file that every later loop reads first. Use when the user asks for an "improvement loop", to "improve the skills", "review and fix everything", or to learn from what was done recently.
---

# improve-skills

Turns the improvement exercise into a repeatable procedure. It edits files inside the repository it is pointed at and
nothing else. It never commits, pushes, deletes, installs software or uses the network unless the user asked for that
in this conversation. It reads transcripts only with `--transcripts`, and then only the lines the user typed.

## Inputs

Take them from the request; do not ask for what it already says.

| Input        | Default                          | Meaning                                                                          |
|--------------|----------------------------------|----------------------------------------------------------------------------------|
| target       | the current repository           | where the skills, scripts, tests and docs live                                   |
| iterations   | 5                                | the loop stops earlier when a review finds nothing reasonable; never more than 5 |
| learn        | yes                              | read recent activity and the lessons file first, update it at the end            |
| plan file    | `docs/improvement-plan.md`       | overwritten every iteration                                                      |
| lessons file | `docs/improve-skills-lessons.md` | created if missing; plain Markdown                                               |

## Scripts

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/improve-skills/scripts"
python3 -I "$S/recent_activity.py" --repo . --days 7 --transcripts     # git, changed files, what the user typed (opt-in)
python3 -I "$S/lessons.py" list docs/improve-skills-lessons.md          # read lessons and standing decisions
python3 -I "$S/lessons.py" add docs/improve-skills-lessons.md --kind lesson --text "..." --evidence "..." --area scripts
python3 -I "$S/plan_check.py" docs/improvement-plan.md                  # the plan has the agreed shape
python3 -I "$S/run_checks.py" --repo .                                  # the repository's own tests and validation
python3 -I "$S/md_tables.py" docs README.md --fix                       # align every Markdown table (check without --fix)
```

## Step 0 - learn before looping

1. Read the lessons file (`lessons.py list`). **Standing decisions** are binding: they are things the user already
   decided (for example "no commit before the version is ready", "no changelog"). Do not re-ask or re-litigate them.
2. If learning is on, run `recent_activity.py --transcripts`. Read the marked (`*`) prompts: they are decisions and
   corrections. Record each new one: a decision the user made becomes `--kind decision`; a mistake you made and were
   corrected on becomes `--kind lesson`, with the prompt or the file as evidence. `lessons.py add` refuses duplicates.
3. Read `references/lessons-learned.md` (what earlier loops taught) and the last plan's "State" section if it exists.

## The loop - repeat up to `iterations` times

Number the iteration in the plan heading: `# Improvement loop, iteration N of M`.

1. **Drop the old plan.** Do not carry its items over and do not reread them. If deletion is blocked, overwrite the
   file in step 3; never work around a blocked delete.
2. **Review from scratch, on real inputs.** Reading is not review. Do at least three of these and keep the
   evidence (command, input, result):
   - run every script and tool on the real files the user works with, not only on fixtures;
   - run the full workflow end to end the way a user would (detect, fix, re-detect, open the result);
   - try the failure paths: missing file, wrong type, empty file, huge input, a path with spaces;
   - scan ordinary human or public-domain controls for false positives, and a known-bad sample for misses;
   - check what the docs claim against what the code does (flags, paths, numbers, names);
   - compare what a manual read finds with what the tools report; every gap is a candidate;
   - run the repository's checks (`run_checks.py`) and read a coverage-style list: which scripts have no test.
3. **Verify each finding a second way** before it becomes an item. A finding built on one probe can be wrong (an early
   loop "found" a risk that a correct parse showed was not there). If the second method disagrees, keep the item only
   if it is still true, and say what changed.
4. **Write the plan from scratch** to the plan file, in exactly this shape (`plan_check.py` enforces it):

   ```markdown
   # Improvement loop, iteration N of M

   Written from scratch on <date> after <what you ran>. **Items: K** (<how many reasonable, how many applied>).

   | # | Item | Verdict |
   |---|---|---|
   | 1 | **Short title.** The finding, with its evidence (command, input, number), and the change. | apply |
   | 2 | ... | skip: <reason: needs a tool this machine lacks / unsafe / not worth it / user decided otherwise> |
   ```

   State the item count in the plan and again in your message. A plan with no reasonable item ends the loop.
5. **Apply every reasonable item.** Reasonable means: it fixes something observed, it is within the repository, it
   is reversible, and it needs no decision that belongs to the user. For each fix add or extend a test, so the loop can
   never undo it. Every script gets a test; every detector gets a fix path or a documented reason it has none; a
   heuristic that finds things gets a control that must stay quiet.
6. **Run the checks** (`run_checks.py`). A failing check is fixed before the next iteration; if it cannot be fixed,
   revert that item and say so in the plan.
7. **Restart** at step 1 with the new state of the repository. Do not stop after a quiet iteration unless the review
   itself found nothing reasonable.

At the end write a **State** section into the last plan: tests and checks passing, what the loop added, what was not
done and why (tools not installed, decisions deferred by the user, deletes that need the user), and the one command the
user must run for anything you could not do.

## Step 3 - learn after looping

Add what surprised you to the lessons file (`lessons.py add`): a wrong premise and how it was caught, a false positive
that needed a control, a claim the docs made that the code did not keep. Prefer a generic lesson with its evidence over
a note about one file. Do not store secrets, personal data or anything the user typed that is not about how to work.
A lesson that should ship with the skill is copied by hand into `references/lessons-learned.md`.

## Markdown tables

In any Markdown file you write or edit (plans, reports, READMEs, `SKILL.md`), tables are aligned the way an editor's
reformat does it: every cell padded to its column, one space either side, and a separator row as wide as the column
(`|---|------|`), never a bare `|---|---|---|` over ragged cells. After writing any `.md`, run `md_tables.py --fix` on it;
`plan_check.py` and `make validate` fail on misaligned tables. Scripts that print tables use `shared/mdtable.py`.

## Report to the user

One table: iteration, items, applied, what it covered. Then what is still open and why. Say plainly what was not run, and
never claim an effect that an inconclusive experiment could not show. List the decisions you need at the end, or none.

## Limits

- Stay inside the target repository. No commit, push, delete, install, network or global settings change without an
  explicit ask in this conversation; a standing decision from the lessons file can forbid more, never allow more.
- `--transcripts` reads only text the user typed, from this project's own session folder, and prints it only here.
- If a command is blocked by the permission system, say so and give the user the exact command to run; do not look for
  another route to the same effect.
