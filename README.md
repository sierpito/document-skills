# document skills

Claude Code skills marketplace `document-skills` with one plugin of the same name.

| Skill               | Use it when                                                                                                                                                                                                                                                        | Needs locally                                                                                                                                                                                                          |
|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `repair-document`   | a generated or messy .pptx/.docx needs its fonts, images, lists, styles, metadata or speaker notes fixed, or an .html/.md/.pdf/text file needs a check for the same signals. Works on a copy, reports what changed.                                                | Python 3 (stdlib for the bundled scripts). For deck/doc repair also `python-pptx`, `lxml`, `Pillow`, `defusedxml`, LibreOffice, poppler; `scripts/check_tools.py` lists what is missing. Nothing is installed for you. |
| `review-ai-content` | you want to know how much of a document looks AI-generated or AI-assisted: a count of signs and an approximate percentage with a range. Read-only.                                                                                                                 | Python 3 (stdlib). `pdftotext` for PDFs.                                                                                                                                                                               |
| `improve-skills`    | you want an improvement loop on a repository of skills, scripts and docs (up to 5 iterations: review from scratch, write a plan with an item count, apply the reasonable fixes, run the checks) and want it to learn from recent activity and keep a lessons file. | Python 3 (stdlib); `git` for the activity digest; `make` for the repository's own checks.                                                                                                                              |
| `generate-diagram`  | you ask for a diagram: Mermaid, Graphviz, PlantUML or SVG source, rendered to SVG/PNG/PDF.                                                                                                                                                                         | Python 3; any of `mmdc`, `dot`, `plantuml`, `rsvg-convert` for the formats you render. Source is checked even without them.                                                                                            |

Shared files live in `plugins/document-skills/shared/`: `patterns.json` and `patterns.py` (rules for both
scanners) and `policy.md` (refusal and fairness wording, copied verbatim into the skills).

## Scripts

All in `plugins/document-skills/skills/<skill>/scripts/`, standard library only. "Writes" means a new file you name
with `--out`; none overwrites or changes its input.

| Script                                                               | Skill             | What it does                                                                                                                                                            | Writes                          |
|----------------------------------------------------------------------|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------|
| `scan_signs.py`                                                      | review-ai-content | counts AI signs, estimates the AI-looking share, by part, with structural and image checks                                                                              | optional `--out` report         |
| `ooxml_inspect.py`                                                   | repair-document   | the detect pass for .pptx/.docx: properties, sizes, fonts (also those not on stock Office/macOS), images, bullets, notes, contrast and box geometry                     | no                              |
| `ooxml_fix.py`                                                       | repair-document   | deterministic fixes: sizes, fonts, embedded fonts, images to `p:pic`, contrast, bullets, properties; dry run without `--out`                                            | yes                             |
| `ooxml_pack.py`                                                      | repair-document   | safe unpack, in-order repack, word ledger (kept / rewritten / added / removed)                                                                                          | unpack folder, repacked file    |
| `invisible_chars.py`                                                 | repair-document   | zero-width, bidi, odd spaces, lookalike letters: inspect or clean a copy                                                                                                | yes                             |
| `prose_tells.py`                                                     | repair-document   | weighted wording tells for an edit report (text files)                                                                                                                  | no                              |
| `recent_activity.py`, `lessons.py`, `plan_check.py`, `run_checks.py` | improve-skills    | activity digest (git, changed files, opt-in: what the user typed), lessons and standing decisions file, plan shape check, run the repository's own tests and validation | lessons file (`lessons.py add`) |
| `full_repair.py`                                                     | repair-document   | full mode: repair and review in rounds, a new version per round (`D-v1.pptx`, `D-v2.pptx`), stops at a target or when nothing more can be fixed, log of every round     | yes (versions and log)          |
| `slide_preview.py`                                                   | repair-document   | render one slide (or all) of a .pptx to a PNG with macOS Quick Look so it can be looked at                                                                              | PNG in a folder you name        |
| `check_tools.py`                                                     | repair-document   | which local tools exist and what each unlocks                                                                                                                           | no                              |
| `render_diagram.py`, `selftest.py`                                   | generate-diagram  | safety and structure check, render Mermaid / DOT / PlantUML / SVG                                                                                                       | yes                             |
| `ooxml_layout.py`, `ooxml_fonts.py`                                  | repair-document   | helpers (geometry, contrast, font safety) imported by the scripts above                                                                                                 | no                              |

Needs Python 3.8 or newer (tested on 3.9) for the bundled scripts; they use only the standard library.

## Install

    /plugin marketplace add sierpito/document-skills
    /plugin install document-skills@document-skills

Or, in one step on a recent Claude Code: `/plugin install document-skills --marketplace sierpito/document-skills`.
From a local clone, use its folder path instead of `sierpito/document-skills`.

## Develop

    make test        # unit tests, standard library only
    make validate    # marketplace/plugin/skill checks, plus `claude plugin validate`

Scripts exit 0 when they ran, 1 when a check found something (`prose_tells.py`: the number of HIGH findings), 2 when the
input was refused or bad (missing file, not a zip, unsafe or oversized archive), and 3 when a diagram failed the
structure check. Input mistakes print one line, never a traceback.

Bump the version in `.claude-plugin/marketplace.json` and `plugins/document-skills/.claude-plugin/plugin.json`
together; `make validate` fails if they differ.

## License

Apache License 2.0, copyright 2026 Igor. See `LICENSE` and `NOTICE`.
