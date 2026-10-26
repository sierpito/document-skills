# shared

Used by `review-ai-content/scripts/scan_signs.py` and `repair-document/scripts/prose_tells.py`. Scripts find this
folder relative to themselves, so they only work from the installed plugin.

- `patterns.json` - the rules. `patterns.py` - loader and helpers (sentences, quotes, English check).
- `policy.md` - refusal and fairness wording, copied verbatim into the `SKILL.md` files and checked by the tests.

## A rule in `patterns.json`

| Field              | Meaning                                                                                                                                                              |
|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `id`, `label`      | short key, and the name shown in reports                                                                                                                             |
| `kind`             | `residue` and `token` (chat leftovers, strong), `glyph` and `format` (medium), `style` (weak, adds 1 per distinct rule), `tool` (AI tool names: listed, not counted) |
| `weight`           | 3, 2 or 1; used by the edit scanner (`prose_tells.py`). The review scanner scores by `kind`                                                                          |
| `pattern`, `flags` | Python regex; in JSON every backslash is doubled (`\\b`), `\\uXXXX` and `\\UXXXXXXXX` escapes are fine                                                               |
| `fix`              | what the edit report suggests                                                                                                                                        |
| `always`           | true: also match inside quotes and block quotes (for example the em dash)                                                                                            |
| `edge`             | `first`, `last` or `either`: only counts in the first / last sentence of a paragraph (chat residue)                                                                  |
| `where`            | `notes`: only counts in speaker notes and comments                                                                                                                   |
| `uses`             | `review`, `edit`, or both                                                                                                                                            |

## Adding or changing a rule

1. Edit `patterns.json` (keep the regex narrow: everyday phrases such as "let me know" or "in this world" must not match).
2. Run `make test`. `Controls` in `tests/test_scripts.py` scans public-domain and everyday texts that must stay
   at or below 5% and an AI-style paragraph that must stay at or above 50%; add a test for your rule.
3. Run `make validate`.
