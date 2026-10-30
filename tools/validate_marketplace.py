#!/usr/bin/env python3
"""Validate the marketplace and plugin files before a release. Stdlib only, read-only.

Checks: JSON parses; plugin name and version agree between marketplace.json and plugin.json; every skill folder has a SKILL.md whose frontmatter name equals the folder and
has a description under 1024 characters; every `references/...`, `scripts/...` and `${CLAUDE_PLUGIN_ROOT}/shared/...`
file named in a SKILL.md exists; the shared policy blocks are copied verbatim into the skills that use them.
If the `claude` CLI exists it also runs `claude plugin validate`.
Usage: python3 tools/validate_marketplace.py     Exit code: number of problems.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
problems = []


def bad(msg):
    problems.append(msg)
    print("PROBLEM:", msg)


def load(p):
    try:
        return json.loads(p.read_text(encoding="utf8"))
    except Exception as e:
        bad(f"{p.relative_to(ROOT)}: {e}")
        return None


def policy_blocks(pdir):
    policy = pdir / "shared/policy.md"
    if not policy.is_file():
        return {}
    return {m.group(1): m.group(2).strip("\n")
            for m in re.finditer(r"<!-- block:(\w+) -->\n(.*?)\n<!-- /block -->", policy.read_text(encoding="utf8"), re.S)}


def check_skill(skill, pdir, blocks):
    md = skill / "SKILL.md"
    if not md.is_file():
        bad(f"{skill.name}: no SKILL.md")
        return
    text = md.read_text(encoding="utf8")
    fm = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not fm:
        bad(f"{skill.name}: no frontmatter")
        return
    name = re.search(r"^name:\s*(.+)$", fm.group(1), re.M)
    desc = re.search(r"^description:\s*(.+)$", fm.group(1), re.M)
    if not name or name.group(1).strip() != skill.name:
        bad(f"{skill.name}: frontmatter name does not match the folder")
    if not desc or len(desc.group(1)) > 1024:
        bad(f"{skill.name}: description missing or over 1024 characters")
    for ref in set(re.findall(r"`((?:references|scripts)/[\w./-]+\.\w+)`", text)):
        if not ref.startswith("scripts/office/") and not (skill / ref).is_file():  # office/ is the external pptx skill
            bad(f"{skill.name}: SKILL.md mentions {ref}, which does not exist")
    for name in set(re.findall(r'\$R/(\w+\.py)', text)):  # commands written as "$R/script.py"
        if not (skill / "scripts" / name).is_file():
            bad(f"{skill.name}: SKILL.md runs $R/{name}, which does not exist")
    for line in text.splitlines():  # flags shown in the Commands block must exist in the script
        m = re.search(r'\$R/(\w+\.py)', line)
        if m and (skill / "scripts" / m.group(1)).is_file():
            source = (skill / "scripts" / m.group(1)).read_text(encoding="utf8")
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", line.split("#")[0]):
                if flag not in source:
                    bad(f"{skill.name}: SKILL.md shows {m.group(1)} {flag}, which the script does not define")
    for other, name in set(re.findall(r"CLAUDE_PLUGIN_ROOT\}/skills/([\w-]+)/scripts/([\w.]+\.py)", text)):
        if not (pdir / "skills" / other / "scripts" / name).is_file():
            bad(f"{skill.name}: SKILL.md runs {other}/scripts/{name}, which does not exist")
    for ref in set(re.findall(r"CLAUDE_PLUGIN_ROOT\}/(shared/[\w./-]+\.\w+)", text)):
        if not (pdir / ref).is_file():
            bad(f"{skill.name}: SKILL.md mentions {ref}, which does not exist")
    if "## Refuse" in text and "evasion" in blocks and blocks["evasion"] not in text:
        bad(f"{skill.name}: Refuse section lacks the shared 'evasion' block from shared/policy.md")


def check_tables(pdir):
    """Every Markdown file shipped in the plugin and the README must have aligned tables (shared/mdtable.py)."""
    sys.path.insert(0, str(pdir / "shared"))
    try:
        import mdtable
    except ModuleNotFoundError:
        return
    for f in [ROOT / "README.md", *sorted(pdir.rglob("*.md"))]:
        if f.is_file() and not mdtable.is_formatted(f.read_text(encoding="utf8")):
            bad(f"{f.relative_to(ROOT)}: tables are not aligned (python3 plugins/document-skills/skills/improve-skills/scripts/md_tables.py {f.relative_to(ROOT)} --fix)")


def main():
    market = load(ROOT / ".claude-plugin/marketplace.json")
    if not market:
        return
    for plug in market.get("plugins", []):
        pdir = (ROOT / plug["source"]).resolve()
        pj = load(pdir / ".claude-plugin/plugin.json")
        if pj:
            if pj.get("name") != plug["name"]:
                bad(f"plugin name differs: marketplace {plug['name']} vs plugin.json {pj.get('name')}")
            if pj.get("version") != plug.get("version"):
                bad(f"version differs: marketplace {plug.get('version')} vs plugin.json {pj.get('version')}")
        cl = ROOT / "CHANGELOG.md"
        ctext = cl.read_text(encoding="utf8") if cl.is_file() else ""
        if not cl.is_file():
            bad("CHANGELOG.md is missing")
        elif "## Unreleased" not in ctext or f"## {pj.get('version') if pj else ''}" not in ctext:
            bad("CHANGELOG.md needs a '## Unreleased' section and a '## <current version>' section")
        tests = (ROOT / "tests/test_scripts.py")
        tested = tests.read_text(encoding="utf8") if tests.is_file() else ""
        for script in sorted((pdir / "skills").glob("*/scripts/*.py")):
            if script.name not in tested:
                bad(f"{script.parent.parent.name}/scripts/{script.name} is not mentioned in tests/test_scripts.py (no test)")
        check_tables(pdir)
        blocks = policy_blocks(pdir)
        for skill in sorted(p for p in (pdir / "skills").iterdir() if p.is_dir()):
            check_skill(skill, pdir, blocks)
    if shutil.which("claude"):
        done = subprocess.run(["claude", "plugin", "validate", str(ROOT)], capture_output=True, text=True)
        tail = (done.stdout or done.stderr).strip().splitlines()[-1:]
        print("claude plugin validate:", tail or done.returncode)
        if done.returncode != 0:
            bad("claude plugin validate failed")


main()
print("ok" if not problems else f"{len(problems)} problem(s)")
sys.exit(min(len(problems), 125))
