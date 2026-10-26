#!/usr/bin/env python3
"""Part of improve-skills. Run a repository's own checks and print one line per check, so a loop can tell at a glance
whether an iteration broke something. Runs only: `make test`, `make validate` (if the Makefile has the target), or
`python3 -m unittest discover -s tests` when there is a tests folder and no `test` target. Installs nothing.

Usage: run_checks.py [--repo DIR] [--timeout SECONDS]
Exit code: number of failed checks (0 = all passed), 2 bad input.
"""
import re, subprocess, sys, time
from pathlib import Path


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def targets(repo):
    mk = repo / "Makefile"
    return set(re.findall(r"^([A-Za-z0-9_.-]+):", mk.read_text(encoding="utf8"), re.M)) if mk.is_file() else set()


def main():
    a = sys.argv[1:]
    repo = Path(a[a.index("--repo") + 1]) if "--repo" in a else Path.cwd()
    limit = int(a[a.index("--timeout") + 1]) if "--timeout" in a else 300
    if not repo.is_dir():
        die(f"not a folder: {repo}")
    have = targets(repo)
    checks = []
    if "test" in have:
        checks.append(("make test", ["make", "-s", "test"]))
    elif (repo / "tests").is_dir():
        checks.append(("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]))
    if "validate" in have:
        checks.append(("make validate", ["make", "-s", "validate"]))
    if not checks:
        print("no checks found (no Makefile test/validate target, no tests folder)")
        return 0
    failed = 0
    for name, cmd in checks:
        t = time.time()
        try:
            done = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=limit)
            ok, tail = done.returncode == 0, (done.stdout + done.stderr).strip().splitlines()[-1:] or [""]
        except subprocess.TimeoutExpired:
            ok, tail = False, [f"timed out after {limit}s"]
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({time.time() - t:.0f}s)  {tail[0][:100]}")
    return failed


if __name__ == "__main__":
    try:
        sys.exit(min(main(), 125))
    except OSError as e:
        die(f"error: {e.strerror}: {e.filename}")
