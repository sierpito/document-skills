---
name: generate-diagram
description: Writes editable diagram source - Mermaid by default, Graphviz DOT for dense graphs, PlantUML for formal UML, SVG as a last resort - from notes, schemas, code or a description, and renders it to SVG, PNG or PDF with locally installed tools only when asked. Use when the user explicitly asks for a diagram: "draw a diagram", "make a flowchart", "sequence diagram", "architecture diagram", "ER diagram", "render this Mermaid".
---

# generate-diagram

It may: write diagram source,
and with `scripts/render_diagram.py` render it through locally installed tools into the output
folder. It must never: install software, use the network, write outside the output folder,
overwrite a file, take an outward action, or render diagram source that tries to read files,
fetch URLs or read environment variables.

## How to work

1. **Pin down the ask.** What should the reader understand from the diagram, and from what material?
   If the input is thin, make sensible assumptions and list them under the diagram rather than
   asking many questions.
2. **Pick the language** (table below). Mermaid unless another one is clearly better.
3. **Model before drawing.** List the nodes, relationships, order, states and branches first; then
   write the source.
4. **Write short, stable source.** ASCII node ids, short readable labels, consistent edge labels.
5. **Give the source back** in a fenced block, with an "Assumptions" list when anything was guessed.
6. **Render only when asked** for an image or PDF, or when a file clearly helps (see "Rendering").
   Never say an image exists unless the script reported success and the file is there.

## Choosing a language

| The diagram shows                          | Use                                                         | Because                              |
|--------------------------------------------|-------------------------------------------------------------|--------------------------------------|
| a process, decisions, swimlanes            | Mermaid `flowchart` with subgraphs                          | pastes into Markdown, easy to review |
| calls between people and systems over time | Mermaid `sequenceDiagram` (PlantUML if formal UML is asked) | built-in lifelines and blocks        |
| states and transitions                     | Mermaid `stateDiagram-v2`                                   | compact transitions                  |
| tables and relations                       | Mermaid `erDiagram`                                         | standard crow's-foot notation        |
| classes and interfaces                     | Mermaid `classDiagram` (PlantUML for detailed UML)          |                                      |
| a schedule                                 | Mermaid `gantt`                                             | dates and dependencies               |
| a hierarchy of ideas                       | Mermaid `mindmap`                                           |                                      |
| a large or dense dependency graph          | Graphviz DOT                                                | better automatic layout              |
| layered architecture with boundaries       | Mermaid flowchart with subgraphs, or DOT clusters           | pick by size                         |
| something none of these fit                | hand-written SVG                                            | full control                         |

## Writing rules

- **Mermaid:** start with the diagram keyword (`flowchart TD`, `flowchart LR` for pipelines and
  architecture). Ids like `order_api[Order API]`. Quote labels with punctuation. Decisions as
  `check{Valid?}` with `-- yes -->` / `-- no -->`. In sequence diagrams declare `actor` and
  `participant` first; use `alt`, `opt`, `loop`, `par` blocks.
- **Graphviz:** `digraph` for directed, `graph` for undirected. Set `rankdir`, `nodesep`, `ranksep`
  at the top; `subgraph cluster_x` for boundaries. Never use `image`, `shapefile`, `fontpath` or
  `imagepath` attributes - they read local files into the output.
- **PlantUML:** wrap in `@startuml` / `@enduml`. Never use `!include`, `!includeurl`, `!import`,
  `!includesub` or `%getenv` - they read files, fetch URLs or expose environment variables.
- **SVG:** a `<title>`, plain shapes and text, no external fonts, images or links.
- **Content:** keep the user's terms; show boundaries (client, service, database, queue, external
  system) in technical diagrams; show the happy path, decisions, failures and manual steps in process
  diagrams. Patterns to start from: `references/patterns.md`.

## Rendering

Output goes to `plans/diagrams/` in the current project when git ignores it
(`git check-ignore -q plans/diagrams/x` exits 0), otherwise to the session scratchpad. Write the
source file there, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/generate-diagram/scripts/render_diagram.py" \
  <source file> --format svg --root <output folder>
```

- `--format` is `svg`, `png` or `pdf`; the output lands next to the source, inside `--root`.
  `--background white|transparent|#hex` sets the Mermaid background.
- `--check-only` runs the safety and structure checks without rendering. The structure check needs no
  renderer: balanced brackets in flowcharts, state, class and ER diagrams, a known Mermaid keyword,
  `@startuml`/`@enduml`, `digraph`/`graph`, well-formed SVG. Run it on every diagram you write, even when
  nothing will be rendered, and fix what it reports before answering. Exit code 3 means the source failed it.
- The script refuses files outside `--root`, never overwrites (it adds `-2`, `-3`), refuses source
  that uses forbidden features (PlantUML includes, Graphviz file attributes, Mermaid `click` links and
  `securityLevel`/init directives, SVG `<image>`, `<foreignObject>`, `<script>`, external `href`/`url()`), runs PlantUML in its sandbox profile,
  and installs nothing.
- If a renderer is missing it says which one and exits non-zero. Then return the source only and
  tell the user which tool would render it (`mmdc`, `dot`, `plantuml`, `rsvg-convert`). Do not
  install it.
- To check the tools work, `scripts/selftest.py --root <output folder>` writes four tiny samples into
  `<output folder>/selftest/` and renders each one.

## Before you answer

- The diagram type fits the question; the source is plausible for its language.
- Labels are short; edges and order match the input.
- Assumptions are listed; a rendered file exists and is not empty.
