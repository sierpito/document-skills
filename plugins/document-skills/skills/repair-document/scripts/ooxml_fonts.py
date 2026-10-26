"""Part of repair-document. Which font families render the same on a stock Office / macOS install, and what to use
instead when a deck names one that does not. Imported by ooxml_inspect.py and ooxml_fix.py. Standard library only.

SAFE is deliberately conservative: families that ship with Microsoft Office (Windows and Mac) or macOS itself. SUBSTITUTES
lists only metric-compatible replacements (same glyph widths, so text does not reflow); a family that is neither safe nor
in SUBSTITUTES has no automatic answer and is reported for a human decision.
"""
import re

SAFE = {s.lower() for s in (
    "Arial", "Arial Black", "Arial Narrow", "Calibri", "Calibri Light", "Cambria", "Cambria Math", "Candara", "Consolas",
    "Constantia", "Corbel", "Courier New", "Georgia", "Impact", "Segoe UI", "Tahoma", "Times New Roman", "Trebuchet MS",
    "Verdana", "Aptos", "Aptos Display", "Aptos Narrow", "Aptos Serif", "Aptos Mono", "Comic Sans MS", "Century Gothic",
    "Franklin Gothic Book", "Franklin Gothic Medium", "Gill Sans MT", "Garamond", "Palatino Linotype", "Book Antiqua",
    "Rockwell", "Symbol", "Wingdings", "Wingdings 2", "Wingdings 3", "Webdings", "Lucida Sans Unicode", "MS Gothic",
    "Helvetica", "Helvetica Neue", "Times", "Courier", "Menlo", "Monaco", "Geneva", "Optima", "Avenir", "Avenir Next",
    "Futura", "Baskerville", "Didot", "Hoefler Text", "Gill Sans", "Palatino", "Cochin", "Copperplate", "American Typewriter",
    "Marker Felt", "Noteworthy", "San Francisco", "SF Pro", "SF Pro Display", "SF Pro Text", "Songti SC", "PingFang SC",
    "Hiragino Sans", "Yu Gothic", "Meiryo", "Malgun Gothic", "Microsoft YaHei", "Microsoft Sans Serif", "Sitka",
    "+mj-lt", "+mn-lt", "+mj-ea", "+mn-ea", "+mj-cs", "+mn-cs", "")}

SUBSTITUTES = {  # open-licence, metric-compatible with the Office font on the right
    "arimo": "Arial", "liberation sans": "Arial", "tinos": "Times New Roman", "liberation serif": "Times New Roman",
    "cousine": "Courier New", "liberation mono": "Courier New", "carlito": "Calibri", "caladea": "Cambria",
    "helvetica": "Arial", "nimbus sans": "Arial", "nimbus roman": "Times New Roman",
}

FAKE_STYLE = re.compile(r"^(?P<base>.+?)\s+(?P<style>Bold Italic|Bold|Italic)$")


def split_fake_style(family):
    """('Arimo', bold, italic) for a family named like 'Arimo Bold'; (family, False, False) otherwise.
    'Arial Black' and 'Calibri Light' are real families and are not touched (only Bold / Italic suffixes)."""
    if family.lower() in SAFE:
        return family, False, False
    m = FAKE_STYLE.match(family)
    if not m:
        return family, False, False
    s = m.group("style")
    return m.group("base"), "Bold" in s, "Italic" in s


def is_safe(family):
    return family.lower() in SAFE


def target_for(family):
    """(new_family, bold, italic, status) where status is 'ok', 'renamed' (fake style or substitute) or 'no-safe-answer'."""
    base, bold, italic = split_fake_style(family)
    new = SUBSTITUTES.get(base.lower(), base)
    if is_safe(new):
        return new, bold, italic, ("ok" if new == family else "renamed")
    return new, bold, italic, "no-safe-answer"
