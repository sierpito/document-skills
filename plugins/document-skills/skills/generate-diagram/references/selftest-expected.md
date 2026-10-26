# Selftest: what to expect

`python3 scripts/selftest.py --root <folder>` writes four samples to `<folder>/selftest/` and renders each
to SVG. Exit codes come from `render_diagram.py`.

| Sample      | Needs               | Output when the tool exists                        | Output when it is missing                                |
|-------------|---------------------|----------------------------------------------------|----------------------------------------------------------|
| `flow.mmd`  | `mmdc`              | `flow.mmd: ok rendered mermaid to .../flow.svg`    | `exit 1 mmdc not found - return the diagram source only` |
| `graph.dot` | `dot`               | `graph.dot: ok rendered graphviz to .../graph.svg` | `exit 1 dot not found ...`                               |
| `seq.puml`  | `plantuml`          | `seq.puml: ok rendered plantuml to .../seq.svg`    | `exit 1 plantuml not found ...`                          |
| `box.svg`   | none for SVG output | `box.svg: ok rendered svg to .../box-rendered.svg` | n/a (copied); PNG/PDF need `rsvg-convert`                |

A missing tool is not a failure of the skill: it returns the source only. Record here the date and tool
versions when you run it on a machine that has them. Run the structure check without any tool with
`render_diagram.py FILE --root <folder> --check-only` (exit 0 ok, 2 refused, 3 failed the check).

Last run: not yet run with real renderers (only `rsvg-convert` was available when this was written).
