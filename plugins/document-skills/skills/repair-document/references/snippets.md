# Snippets

Reference code, not scripts: write what you need into the working folder for one run.

## Contrast repair - darken along the hue until it clears the threshold

```python
import colorsys
def lum(h):
    c = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    c = [x/12.92 if x <= 0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return 0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2]
def ratio(fg, bg):
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a+0.05)/(b+0.05)
def darken(hexcol, bg, target=4.6):
    r, g, b = [int(hexcol[i:i+2], 16)/255 for i in (0, 2, 4)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    lo, hi = 0.0, l
    for _ in range(60):
        mid = (lo+hi)/2
        cand = '%02X%02X%02X' % tuple(round(v*255) for v in colorsys.hls_to_rgb(h, mid, s))
        lo, hi = (mid, hi) if ratio(cand, bg) >= target else (lo, mid)
    return '%02X%02X%02X' % tuple(round(v*255) for v in colorsys.hls_to_rgb(h, lo, s))
```

## Safe widening - only into free space, never a centred box

```python
for sh, x, y, w, h in boxes:
    if not sh.has_text_frame or not sh.text_frame.text.strip(): continue
    if {p.alignment for p in sh.text_frame.paragraphs} - {PP_ALIGN.LEFT, None}: continue
    limit = SLIDE_W - 0.5
    for o, ox, oy, ow, oh in boxes:
        if o is sh or min(y+h, oy+oh) - max(y, oy) <= 0.02: continue
        if ox >= x + w - 0.01: limit = min(limit, ox - 0.15)
    new = min(w * 1.10, limit - x)
    if new > w + 0.02: sh.width = Emu(int(new * IN))
```

## Provenance ledger, safe unpack, repack

Use `scripts/ooxml_pack.py` (tested; never overwrites, never deletes):

```bash
P="${CLAUDE_PLUGIN_ROOT}/skills/repair-document/scripts/ooxml_pack.py"
python3 -I "$P" unpack input/deck.pptx unpacked/            # rejects absolute and .. member paths
python3 -I "$P" repack input/deck.pptx unpacked/ out/deck.pptx [--skip docMetadata/LabelInfo.xml]
python3 -I "$P" ledger input/deck.pptx out/deck.pptx        # words kept / rewritten / added, body and notes
```

`repack` writes the input's member list in the input's order (so `[Content_Types].xml` stays first), adds
no directory entries, and checks the result. A part removed on purpose goes in `--skip`; remove its
`<Override>` and relationship in the same step. The ledger is a word-level diff, run on body text and on
notes separately: the two numbers usually differ enormously, and the difference is the finding.

For invisible characters use `scripts/invisible_chars.py` (see `invisible-and-metadata.md`).
