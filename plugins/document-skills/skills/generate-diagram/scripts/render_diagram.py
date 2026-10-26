"""Render one diagram source file (Mermaid, Graphviz DOT, PlantUML or SVG) to svg, png or pdf.

Part of generate-diagram. Local tools only: installs nothing, uses no network, writes only
inside --root, never overwrites, and refuses source that would read files, fetch URLs or read
environment variables while rendering.

Usage: python3 render_diagram.py SOURCE --format svg|png|pdf --root OUTPUT_FOLDER
Exit codes: 0 rendered (or --check-only passed), 1 render failed or tool missing, 2 refused (path or unsafe
source), 3 source failed the structural check.
Options: --check-only (lint, render nothing), --background white|transparent|#hex (Mermaid).
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KINDS = {".mmd": "mermaid", ".mermaid": "mermaid", ".dot": "graphviz", ".gv": "graphviz",
         ".puml": "plantuml", ".plantuml": "plantuml", ".svg": "svg"}

# Features that make a renderer read local files, fetch URLs or expose environment variables.
UNSAFE = {
    "plantuml": re.compile(r"(!include|!import|%getenv|%get_env|%load_json|%file_exists)", re.I),
    "graphviz": re.compile(r"\b(image|shapefile|fontpath|imagepath)\s*=", re.I),
    "svg": re.compile(r"(href\s*=\s*[\"'](?!#)|<!ENTITY|<!DOCTYPE|<image\b|<foreignObject\b|<script\b|<use\b[^>]*(?:href)\s*=\s*[\"'](?!#)|url\(\s*[\"']?(?!#)|@import)", re.I),
    "mermaid": re.compile(r"(%%\{\s*init|%%\{\s*config|securityLevel|<script|javascript:|^\s*click\b[^\n]*(?:href|call|https?:)|<iframe|<img\b[^>]*src)", re.I | re.M),
}


def lint(kind, text):
    """Cheap structural check that needs no renderer. Returns a list of problems (empty = looks fine)."""
    problems = []
    stripped = re.sub(r'"[^"\n]*"', '""', text)  # ignore brackets inside quoted labels
    check_brackets = True
    if kind == "mermaid":
        stripped = re.sub(r"\w+>[^\]\n]*\]", "X", stripped)  # asymmetric shape id>text]
        head = next((l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("%%")), "")
        # erDiagram uses { } as crow's-foot symbols (||--o{), and prose-like types contain free text
        check_brackets = bool(re.match(r"(flowchart|graph|stateDiagram|classDiagram)", head))
    elif kind == "graphviz":
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)
        stripped = re.sub(r"(//|^\s*#).*$", "", stripped, flags=re.M)
    elif kind == "plantuml":
        check_brackets = False  # activations, notes and skinparam blocks make bracket counting unreliable
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    for line_no, line in enumerate(stripped.splitlines() if check_brackets else [], 1):
        if kind == "mermaid" and line.lstrip().startswith("%%"):
            continue
        for ch in line:
            if ch in pairs:
                stack.append((ch, line_no))
            elif ch in pairs.values():
                if not stack or pairs[stack[-1][0]] != ch:
                    problems.append(f"line {line_no}: unmatched '{ch}'")
                    return problems
                stack.pop()
    if stack:
        problems.append(f"line {stack[-1][1]}: '{stack[-1][0]}' is never closed")
    if kind == "plantuml":
        if not re.search(r"^\s*@start\w+", text, re.M):
            problems.append("missing @startuml")
        if not re.search(r"^\s*@end\w+", text, re.M):
            problems.append("missing @enduml")
    elif kind == "graphviz":
        if not re.match(r"\s*(strict\s+)?(di)?graph\b", text):
            problems.append("must start with graph or digraph")
    elif kind == "mermaid":
        first = next((l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("%%")), "")
        if not re.match(r"(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram(-v2)?|erDiagram|gantt|mindmap|"
                        r"journey|pie|timeline|gitGraph|quadrantChart|C4Context|requirementDiagram|sankey-beta|xychart-beta)\b", first):
            problems.append("first line is not a known Mermaid diagram keyword")
    elif kind == "svg":
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(text)
        except Exception as e:  # DOCTYPE and entities were refused before this runs
            problems.append(f"not well-formed SVG/XML: {e}")
    return problems


def fail(code, message):
    print(message, file=sys.stderr)
    sys.exit(code)


def kind_of(path, text):
    if path.suffix.lower() in KINDS:
        return KINDS[path.suffix.lower()]
    head = text.lstrip()
    if head.startswith("@startuml"):
        return "plantuml"
    if head.startswith(("digraph", "graph", "strict")):
        return "graphviz"
    if head.startswith("<svg"):
        return "svg"
    return "mermaid"


def free_path(path):
    """Return path, or path with -2, -3 ... added, so nothing is ever overwritten."""
    if not path.exists():
        return path
    n = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def tool(name):
    found = shutil.which(name)
    if not found:
        fail(1, f"{name} not found - return the diagram source only (nothing is installed)")
    return found


def run(cmd, cwd=None, env=None):
    done = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, timeout=120)
    if done.returncode != 0:
        fail(1, f"render failed ({Path(cmd[0]).name}, exit {done.returncode}): {done.stderr.strip()[:400]}")


def render(kind, src, out, fmt, background=None):
    if kind == "mermaid":
        cmd = [tool("mmdc"), "-i", str(src), "-o", str(out)]
        if background:
            cmd += ["-b", background]
        run(cmd)
    elif kind == "graphviz":
        run([tool("dot"), f"-T{fmt}", str(src), "-o", str(out)])
    elif kind == "plantuml":
        env = dict(os.environ, PLANTUML_SECURITY_PROFILE="SANDBOX")
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / src.name
            shutil.copyfile(src, copy)
            run([tool("plantuml"), f"-t{fmt}", str(copy)], cwd=tmp, env=env)
            produced = sorted(Path(tmp).glob(f"*.{fmt}"))
            if not produced:
                fail(1, "render failed: PlantUML produced no output")
            shutil.copyfile(produced[0], out)
    elif kind == "svg":
        if fmt == "svg":
            shutil.copyfile(src, out)
        else:
            run([tool("rsvg-convert"), "-f", fmt, "-o", str(out), str(src)])


def main():
    ap = argparse.ArgumentParser(description="Render a diagram source file inside an output folder.")
    ap.add_argument("source", type=Path)
    ap.add_argument("--format", choices=["svg", "png", "pdf"], default="svg")
    ap.add_argument("--root", type=Path, required=True, help="output folder; source and output must be inside it")
    ap.add_argument("--check-only", action="store_true", help="run the safety and structure checks, render nothing")
    ap.add_argument("--background", help="Mermaid background: white, transparent or a #hex colour")
    a = ap.parse_args()

    root = a.root.resolve()
    src = a.source.resolve()
    if not src.is_file():
        fail(2, f"source not found: {src}")
    if root not in src.parents:
        fail(2, f"refused: {src} is outside {root}")
    text = src.read_text(encoding="utf-8", errors="replace")
    kind = kind_of(src, text)
    hit = UNSAFE[kind].search(text)
    if hit:
        fail(2, f"refused: {kind} source uses '{hit.group(0)}', which can read files, fetch URLs or read env")
    problems = lint(kind, text)
    if problems:
        fail(3, f"source check failed ({kind}): " + "; ".join(problems))
    if a.check_only:
        print(f"ok: {kind} source passed the safety and structure checks")
        return
    out = free_path(src.with_suffix("." + a.format) if src.suffix.lower() != "." + a.format
                    else src.with_name(src.stem + "-rendered." + a.format))
    render(kind, src, out, a.format, a.background)
    if not out.exists() or out.stat().st_size == 0:
        fail(1, f"render failed: no output at {out}")
    print(f"rendered {kind} to {out}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeDecodeError) as e:
        fail(2, f"error: {getattr(e, 'strerror', None) or e}: {getattr(e, 'filename', '')}")
