"""Write four tiny diagrams into ROOT/selftest/ and render each with render_diagram.py.

Part of generate-diagram. Shows which local renderers work; installs nothing.
Usage: python3 selftest.py --root OUTPUT_FOLDER
"""

import argparse
import subprocess
import sys
from pathlib import Path

SAMPLES = {
    "flow.mmd": "flowchart LR\n  a[Start] --> b{OK?}\n  b -- yes --> c[Done]\n  b -- no --> a\n",
    "graph.dot": "digraph g {\n  rankdir=LR;\n  web -> api -> db;\n}\n",
    "seq.puml": "@startuml\nactor User\nUser -> App : Ping\nApp --> User : Pong\n@enduml\n",
    "box.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="50"><title>Box</title>'
               '<rect x="5" y="5" width="110" height="40" fill="#ffffff" stroke="#000000"/></svg>\n',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    root = ap.parse_args().root.resolve()
    folder = root / "selftest"
    folder.mkdir(parents=True, exist_ok=True)
    renderer = Path(__file__).with_name("render_diagram.py")
    for name, body in SAMPLES.items():
        path = folder / name
        if not path.exists():
            path.write_text(body, encoding="utf-8")
        check = subprocess.run([sys.executable, str(renderer), str(path), "--root", str(root), "--check-only"],
                               text=True, capture_output=True)
        print(f"{name} (structure check): {'ok' if check.returncode == 0 else 'exit ' + str(check.returncode)} "
              f"{(check.stdout or check.stderr).strip()}")
        done = subprocess.run([sys.executable, str(renderer), str(path), "--format", "svg", "--root", str(root)],
                              text=True, capture_output=True)
        status = "ok" if done.returncode == 0 else f"exit {done.returncode}"
        print(f"{name}: {status} {(done.stdout or done.stderr).strip()}")


if __name__ == "__main__":
    main()
