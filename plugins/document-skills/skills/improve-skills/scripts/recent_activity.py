#!/usr/bin/env python3
"""Part of improve-skills. A digest of recent activity in a repository, for learning from it.

Read-only, standard library only, no network. Sources:
  git        last commits, working-tree status (if the folder is a git repository)
  files      files changed in the last N days (skips .git, .idea, caches)
  transcripts (opt-in, --transcripts) the human-typed prompts of recent Claude Code sessions for this folder, read
             from ~/.claude/projects/<folder-slug>/*.jsonl. Only messages the user typed are read; assistant text,
             tool results and attachments are never printed. Prompts that read like a decision or a correction
             ("don't", "no need", "ignore", "instead", "only", "skip", ...) are marked.

Usage: recent_activity.py [--repo DIR] [--days N] [--transcripts [DIR]] [--max N] [--json]
Exit code: 0 ok, 2 bad input.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

SKIP_DIRS = {".git", ".idea", "__pycache__", "node_modules", ".venv", ".pytest_cache"}
DIRECTIVE = re.compile(
    r"\b(don'?t|do not|no need|never|always|ignore|instead|only|skip|drop|remove|without|rather|stop|must|should not|"
    r"shouldn'?t|wrong|not what|no more|later|defer|leave|keep)\b", re.I)


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def git(repo, *args):
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def recent_files(repo, days, limit):
    cutoff = time.time() - days * 86400
    found = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath, name)
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_mtime >= cutoff:
                found.append((st.st_mtime, st.st_size, str(p.relative_to(repo))))
    found.sort(reverse=True)
    return [{"path": p, "bytes": s, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(m))} for m, s, p in found[:limit]]


def transcript_dir(repo, explicit):
    if explicit:
        return Path(explicit).expanduser()
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))
    return Path("~/.claude/projects").expanduser() / slug


def human_prompts(folder, limit):
    """Human-typed prompts, oldest to newest, from the newest transcripts. Nothing else is read out."""
    prompts = []
    files = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)[-3:] if folder.is_dir() else []
    for f in files:
        with open(f, encoding="utf8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "user" or (d.get("origin") or {}).get("kind") != "human":
                    continue
                content = (d.get("message") or {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    continue
                text = re.sub(r"\s+", " ", content).strip()
                prompts.append({"time": (d.get("timestamp") or "")[:16].replace("T", " "), "text": text[:240],
                                "directive": bool(DIRECTIVE.search(text))})
    return prompts[-limit:]


def main():
    a = sys.argv[1:]
    repo = Path(a[a.index("--repo") + 1]) if "--repo" in a else Path.cwd()
    days = int(a[a.index("--days") + 1]) if "--days" in a else 7
    limit = int(a[a.index("--max") + 1]) if "--max" in a else 40
    if not repo.is_dir():
        die(f"not a folder: {repo}")
    out = {"repo": str(repo.resolve()), "days": days}
    log = git(repo, "log", "--oneline", "-n", "15")
    out["git"] = {"is_repo": git(repo, "rev-parse", "--is-inside-work-tree") == "true",
                  "recent_commits": log.splitlines() if log else [],
                  "status": (git(repo, "status", "--short") or "").splitlines()[:30]}
    out["recent_files"] = recent_files(repo, days, limit)
    if "--transcripts" in a:
        i = a.index("--transcripts")
        explicit = a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith("--") else None
        folder = transcript_dir(repo, explicit)
        out["transcripts"] = {"folder": str(folder), "found": folder.is_dir(), "human_prompts": human_prompts(folder, limit)}
    if "--json" in a:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    print(f"# Recent activity: {out['repo']} (last {days} days)\n")
    g = out["git"]
    print("## git" + ("" if g["is_repo"] else " (not a repository)"))
    for l in g["recent_commits"]:
        print("  " + l)
    if g["is_repo"] and not g["recent_commits"]:
        print("  no commits yet")
    for l in g["status"]:
        print("  " + l)
    print(f"\n## files changed ({len(out['recent_files'])})")
    for f in out["recent_files"]:
        print(f"  {f['modified']}  {f['bytes']:>9}  {f['path']}")
    if "transcripts" in out:
        t = out["transcripts"]
        print(f"\n## what the user typed ({t['folder']}{'' if t['found'] else ' - not found'})")
        for p in t["human_prompts"]:
            print(f"  {'*' if p['directive'] else ' '} {p['time']}  {p['text']}")
        print("  (* = reads like a decision or a correction; nothing but typed prompts is shown)")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as e:
        die(f"error: {e}")
