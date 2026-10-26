#!/usr/bin/env python3
"""Part of repair-document. Full repair mode for .pptx and .docx: repair and review in a loop, one new file per round.

Each round: inspect the latest version (ooxml_inspect), apply every deterministic fix that the findings call for
(ooxml_fix), write the result as a new version (D.pptx -> D-v1.pptx, D-v2.pptx, ...), then inspect and review the new
version (review-ai-content's scan_signs). The original is never touched. The loop stops when

  * the open defects are at most --target percent of the starting defects (default 10), or
  * a round has nothing left that can be fixed automatically (the rest is listed as manual work), or
  * --max-rounds is reached (default 5).

The defect score weighs what ooxml_inspect reports: critical 5, high 3, medium 1, each open signal counted once. The AI
review is run every round and shown for information. It is NOT an exit target: lowering it would mean rewriting wording
to defeat a detector, which this skill refuses. What the loop does fix, and what it leaves for a person, is in the log.

Usage:
  full_repair.py FILE --workdir DIR [--target 10] [--max-rounds 5] [--author NAME] [--allow-clipped] [--json]
  full_repair.py FILE --workdir DIR --adopt EDITED_FILE      register a hand-edited file (for example rewritten notes) as
                                                             the next version, evaluate it, run no fixes
Outputs in DIR: <stem>-vN.<ext> per round, <stem>-repair-log.md and <stem>-repair-log.json.
Exit code: 0 target reached, 1 stopped with open defects, 2 bad input.
"""
import json, re, shutil, subprocess, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "shared"))
try:
    import mdtable
except ModuleNotFoundError:
    sys.exit("needs shared/mdtable.py from the document-skills plugin root; run this script from the installed plugin")

WEIGHT = {"critical": 5, "high": 3, "medium": 1}
NOT_DEFECTS = ("external relationship targets",)  # legitimate links, reported by the inspector but not repairable
RESIDUE = {"chat residue", "tool/citation token", "generator-facing note", "sycophantic opener", "assistant offer"}
REVIEW = HERE.parents[1] / "review-ai-content" / "scripts" / "scan_signs.py"


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def run(script, *args):
    done = subprocess.run([sys.executable, "-I", str(script), *map(str, args)], capture_output=True, text=True)
    if done.returncode not in (0, 1):
        die(f"{Path(script).name} failed: {(done.stderr or done.stdout).strip()[-300:]}")
    return done


def inspect(path):
    rows = json.loads(run(HERE / "ooxml_inspect.py", path, "--json").stdout)["signals"]
    return [r for r in rows if r["severity"] in WEIGHT and r["value"] not in (0, "0", "") and not r["signal"].startswith(NOT_DEFECTS)]


def review(path):
    r = json.loads(run(REVIEW, path, "--json", "--media").stdout)
    return {"signs": r["signs"], "ai_pct": r["estimate_pct"], "range": r["range_pct"], "confidence": r["confidence"],
            "residue": sum(v for k, v in r["categories"].items() if k in RESIDUE)}


def score(defects):
    return sum(WEIGHT[d["severity"]] for d in defects)


LEFT_BY_FIX = {
    "--round-sizes": "the remaining fractional sizes are not rounding noise and are left as designed",
    "--normalize-fonts": "some families have no safe replacement",
    "--strip-embedded-fonts": "embedded fonts could not be removed",
    "--images": "freeforms with a non-rectangular path are clipped pictures; converting them could change the look, so they are left (opt in with --allow-clipped for cut-outs: PNGs with transparency and straight-line outlines)",
    "--fit": "there is no free room next to or below these boxes; move or resize them by hand after checking a render",
    "--contrast": "the failing colours come from the theme or have no solution; pick colours by hand",
    "--bullets": "these bullets could not be converted safely",
    "--allow-clipped": "these pictures are opaque or have curved outlines, so removing the clip would change the look",
}


def plan(defects, kind, author, allow_clipped=False):
    """(args for ooxml_fix, [manual items], [(defect, flag) the fixer is expected to handle]) from the open defects."""
    flags, manual, props, auto = [], [], False, []
    for d in defects:
        s, note = d["signal"], d["note"]
        before = len(flags)
        if s.startswith("fractional type sizes: rounding noise"):
            flags.append("--round-sizes")
        elif s.startswith("fabricated font families") or (s.startswith("font families that do not ship") and "metric-compatible swap" in note):
            flags.append("--normalize-fonts")
            if "no safe automatic answer" in note:
                manual.append((d, "choose an installed font for: " + note.split("no safe automatic answer:")[-1].strip()))
        elif s.startswith("font families that do not ship"):
            manual.append((d, "no safe automatic answer; pick an installed font or accept the viewer's fallback: " + note.split(":")[-1].strip()))
        elif s == "embedded fonts":
            flags.append("--strip-embedded-fonts")
        elif s.startswith("images as picture fill on a custom shape"):
            flags.append("--images")
            if allow_clipped:
                flags.append("--allow-clipped")
        elif s.startswith(("text boxes with no slack", "text boxes shorter than their text")):
            flags.append("--fit")
        elif s.startswith("text runs failing contrast"):
            flags.append("--contrast")
        elif s.startswith("typed bullets"):
            flags.append("--bullets")
        elif s.startswith(("placeholder or future dates", "app.xml counters", "stray dc:identifier", "PresentationFormat contradicts")):
            props = True
        elif s.startswith("author (dc:creator)"):
            if author:
                props = True
            else:
                manual.append((d, "ask who wrote the content; pass --author NAME only once the user confirms it"))
        elif s.startswith("generator-facing"):
            manual.append((d, "rewrite as presenter-voice text (needs the user's consent for prose edits), then --adopt the edited file"))
        elif s.startswith(("text boxes extending", "overlapping text boxes")):
            manual.append((d, "check in a render and move or resize the boxes by hand"))
        else:
            manual.append((d, "review by hand (not repairable automatically)"))
        if len(flags) > before:
            auto.append((d, flags[-1]))
    flags = [f for i, f in enumerate(flags) if f not in flags[:i]]
    if kind == "docx":
        flags = [f for f in flags if f in ("--normalize-fonts", "--strip-embedded-fonts", "--bullets")]
    args = list(flags)
    if props:
        args += ["--props", f"author={author}" if author else ""]
    return args, manual, auto


def changed(fixes):
    """True when a dry run reports at least one change."""
    for name, group in fixes.items():
        if name == "props":
            if "changed" not in group:
                return True
            continue
        if name in ("skipped", "report-notes"):
            continue
        if any(isinstance(v, int) and v > 0 and "left" not in k for k, v in group.items()):
            return True
    return False


def latest(log, original):
    return Path(log["rounds"][-1]["file"]) if log["rounds"] else original


def evaluate(path):
    defects = inspect(path)
    return defects, review(path)


def open_summary(r):
    """Short text of the open signals with their counts, so progress inside a signal is visible (56 -> 1 pictures)."""
    if "open" not in r and Path(r["file"]).is_file():
        r["open"] = [[d["signal"], d["value"]] for d in inspect(Path(r["file"]))]
    return "; ".join(f"{s.split(' (')[0][:46]}: {v}" for s, v in r.get("open", [])) or "none"


def table(log):
    rows = [["Version", "Open defects", "Remaining", "Open signals (count)", "Fixes applied", "AI signs", "AI-looking % (info only)", "Residue signs"]]
    for r in log["rounds"]:
        rows.append([Path(r["file"]).name, f'{r["defect_score"]} ({r["defects"]} signals)', f'{r["remaining_pct"]}%',
                     open_summary(r), r["applied"].strip() or "-", str(r["ai_signs"]), f'~{r["ai_pct"]}% (range {r["range"][0]}-{r["range"][1]}%)'
                     if r["ai_pct"] is not None else "not estimated", str(r["residue"])])
    return "\n".join(mdtable.format_table(rows))


def write_log(workdir, stem, log, manual, why):
    (workdir / f"{stem}-repair-log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf8")
    lines = [f"# Full repair log: {log['original']}", "", f"Date: {date.today().isoformat()} · target: open defects at most "
             f"{log['target']}% of the starting {log['start_score']} · stop reason: {why}", "", table(log), ""]
    if manual:
        lines += ["## Left for a person", ""] + mdtable.format_table([["Severity", "Finding", "Next step"]] + [
            [d["severity"], d["signal"], step] for d, step in manual]) + [""]
    lines += ["The AI-looking percentage is shown for information. It is a floor from lexical and structural signals, it is not "
              "an exit target, and this loop never rewrites wording to lower it."]
    (workdir / f"{stem}-repair-log.md").write_text("\n".join(lines) + "\n", encoding="utf8")


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-") or "--workdir" not in a:
        die(__doc__)
    src = Path(a[0])
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
    workdir = Path(opt("--workdir"))
    clipped = "--allow-clipped" in a
    target, max_rounds, author, adopt = int(opt("--target", 10)), int(opt("--max-rounds", 5)), opt("--author"), opt("--adopt")
    if src.suffix.lower() not in (".pptx", ".docx"):
        die("full repair works on .pptx and .docx; use scan_signs.py / prose_tells.py for other files")
    if not src.is_file():
        die(f"not found: {src}")
    if not 0 <= target <= 100 or not 1 <= max_rounds <= 5:
        die("--target must be 0-100 and --max-rounds 1-5")
    kind = src.suffix.lower()[1:]
    workdir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    logf = workdir / f"{stem}-repair-log.json"
    if logf.is_file():
        log = json.loads(logf.read_text(encoding="utf8"))
    else:
        defects, rev = evaluate(src)
        base = score(defects)
        log = {"original": str(src), "target": target, "start_score": base, "author": author, "rounds": [
            {"file": str(src), "defect_score": base, "defects": len(defects), "remaining_pct": 100 if base else 0, "applied": "original",
             "ai_signs": rev["signs"], "ai_pct": rev["ai_pct"], "range": rev["range"], "residue": rev["residue"]}]}
    log["target"] = target
    base = log["start_score"]
    why, manual = "", []
    # new inputs (a confirmed author, the opt-in for cut-outs) get one round even when the target was already reached
    new_inputs = bool(author and author != log.get("author")) or (clipped and not log.get("clipped"))
    log["clipped"] = bool(clipped or log.get("clipped"))

    def record(path, applied):
        defects, rev = evaluate(path)
        sc = score(defects)
        log["rounds"].append({"file": str(path), "defect_score": sc, "defects": len(defects),
                              "remaining_pct": round(100 * sc / base) if base else 0, "applied": applied,
                              "ai_signs": rev["signs"], "ai_pct": rev["ai_pct"], "range": rev["range"], "residue": rev["residue"]})
        log["rounds"][-1]["open"] = [[d["signal"], d["value"]] for d in defects]
        return defects

    def next_path():
        n = len([r for r in log["rounds"] if "-v" in Path(r["file"]).stem]) + 1
        return workdir / f"{stem}-v{n}{src.suffix.lower()}"

    if adopt:
        edited = Path(adopt)
        if not edited.is_file() or edited.suffix.lower() != src.suffix.lower():
            die("--adopt needs an existing file of the same type")
        dest = next_path()
        shutil.copyfile(edited, dest)
        defects = record(dest, "hand edit")
        _, manual, _ = plan(defects, kind, author or log.get("author"), clipped)
        why = "hand edit adopted"
    else:
        rounds_run = 0
        for _ in range(max_rounds):
            cur = latest(log, src)
            defects = inspect(cur)  # always fresh: the inspector may know more than when the version was recorded
            last = log["rounds"][-1]
            last["defect_score"], last["defects"] = score(defects), len(defects)
            last["remaining_pct"] = round(100 * last["defect_score"] / base) if base else 0
            last["open"] = [[d["signal"], d["value"]] for d in defects]
            if last["remaining_pct"] <= target and not (new_inputs and rounds_run == 0):
                why = f"target reached ({last['remaining_pct']}% open)"
                break
            args, manual, auto = plan(defects, kind, author or log.get("author"), clipped)
            dry = json.loads(run(HERE / "ooxml_fix.py", cur, *args, "--json").stdout) if args else {"fixes": {}}
            if not args or not changed(dry.get("fixes", {})):
                why = "nothing left that can be fixed automatically"
                manual = manual + [(d, "automatic fix leaves this: " + LEFT_BY_FIX.get(f, "it cannot resolve it")) for d, f in auto]
                break
            dest = next_path()
            done = run(HERE / "ooxml_fix.py", cur, "--out", dest, *args)
            if not dest.is_file():
                die("ooxml_fix wrote no file")
            record(dest, " ".join(x for x in args if x.startswith("--") and x != "--props") + (" props" if "--props" in args else ""))
            rounds_run += 1
            if author:
                log["author"] = author  # remembered only once a round has used it
            if log["rounds"][-1]["remaining_pct"] <= target:
                why = f"target reached ({log['rounds'][-1]['remaining_pct']}% open)"
                break
        else:
            why = f"reached --max-rounds {max_rounds}"
        if not manual or why.startswith(("target", "reached")):
            defects = inspect(latest(log, src))
            _, manual, _ = plan(defects, kind, author or log.get("author"), clipped)
    final = log["rounds"][-1]
    if not why:
        why = "stopped"
    write_log(workdir, stem, log, manual, why)
    if "--json" in a:
        print(json.dumps({"stop_reason": why, "latest": final["file"], "remaining_pct": final["remaining_pct"], "rounds": log["rounds"],
                          "manual": [{"signal": d["signal"], "severity": d["severity"], "next": s} for d, s in manual]}, indent=2, ensure_ascii=False))
    else:
        print(table(log))
        print(f"\nstop reason: {why}\nlatest version: {final['file']}\nlog: {workdir / (stem + '-repair-log.md')}")
        if manual:
            print("\nleft for a person:")
            for d, step in manual:
                print(f"  [{d['severity']}] {d['signal']}: {step}")
        print("\nAI-looking % is information only; this loop never rewrites wording to lower it.")
    return 0 if final["remaining_pct"] <= target else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as e:
        die(f"error: {e}")
