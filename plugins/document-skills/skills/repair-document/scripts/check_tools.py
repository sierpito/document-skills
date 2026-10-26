#!/usr/bin/env python3
"""Part of repair-document. Lists which local tools exist and which checks each one unlocks.

Read-only: checks imports and PATH only, installs nothing, makes no network calls.
Usage: check_tools.py [--json]
"""
import importlib.util, json, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
try:
    import mdtable
except ModuleNotFoundError:
    sys.exit("needs shared/mdtable.py from the document-skills plugin root; run this script from the installed plugin")

PY = [
    ("pptx", "python-pptx", "read and edit slides, measure boxes, text frames"),
    ("lxml", "lxml", "XML edits and validation"),
    ("PIL", "Pillow", "image size, format and metadata checks"),
    ("defusedxml", "defusedxml", "safe XML parsing of untrusted files"),
    ("docx", "python-docx", "optional: paragraph and style access for .docx"),
    ("pypdf", "pypdf", "optional: PDF metadata write on a copy"),
    ("reportlab", "reportlab", "optional: typeset a new PDF from cleaned text"),
]
BIN = [
    ("soffice", "LibreOffice", "render .pptx/.docx to PDF for the look, overlap and wrapping checks"),
    ("pdftoppm", "poppler", "turn rendered PDF pages into images"),
    ("pdftotext", "poppler", "render fidelity, PDF text for review"),
    ("pdffonts", "poppler", "font resolution check"),
    ("pdfimages", "poppler", "image presence check"),
    ("pdfinfo", "poppler", "PDF metadata"),
    ("qpdf", "qpdf", "optional: PDF attachment and structure checks"),
    ("exiftool", "exiftool", "optional: deeper image and PDF metadata"),
    ("qlmanage", "macOS Quick Look", "optional: second previewer for the image-visibility check"),
]


def main():
    rows = []
    py_ok = sys.version_info >= (3, 8)
    rows.append({"kind": "python", "name": "Python %d.%d.%d" % sys.version_info[:3], "found": py_ok,
                 "unlocks": "the bundled scripts need 3.8+ (tested on 3.9)"})
    for mod, name, why in PY:
        rows.append({"kind": "python", "name": name, "found": importlib.util.find_spec(mod) is not None, "unlocks": why})
    for exe, name, why in BIN:
        rows.append({"kind": "binary", "name": f"{name} ({exe})", "found": shutil.which(exe) is not None, "unlocks": why})
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
        return
    print("\n".join(mdtable.format_table([["Tool", "Found", "Unlocks"]] + [
        [r["name"], "yes" if r["found"] else "NO", r["unlocks"]] for r in rows])))
    missing = [r["name"] for r in rows if not r["found"]]
    print(f"\n{len(rows) - len(missing)} of {len(rows)} found." + (" Missing checks are skipped and reported; nothing is installed." if missing else ""))


if __name__ == "__main__":
    main()
