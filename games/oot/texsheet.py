"""Dev tool: contact sheet of textures from an o2r (dirty or clean) by regex.

    python -m games.oot.texsheet <oot.o2r> <regex> <out.png> [--scale 3] [--cols 12] [--bg 60]

Palette textures are drawn with the palette the spec links them to.
Dirty sheets are for looking only; never published.
"""
import json
import os
import re
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw

from cleanroom.gfx import texfmt
from games.oot import o2r
from games.oot.extract_spec import FMT

SPEC = os.path.join(os.path.dirname(__file__), "spec", "textures.json")


def decode_path(z, path, T):
    t = o2r.tex_parse(z.read(path))
    pal = None
    if t["type"] in (3, 4) and T.get(path, {}).get("pal"):
        p = o2r.tex_parse(z.read(T[path]["pal"][0]))
        pal = texfmt.decode(p["data"], p["w"] * p["h"], 1, texfmt.RGBA, texfmt.B16)[0]
        pal = np.concatenate([pal] * (256 // len(pal) + 1))[:256]
    fmt, siz = FMT[t["type"]]
    return texfmt.decode(t["data"], t["w"], t["h"], fmt, siz, palette=pal)


def main(argv):
    src, rx, out = argv[1:4]
    scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 3
    cols = int(argv[argv.index("--cols") + 1]) if "--cols" in argv else 12
    bg = int(argv[argv.index("--bg") + 1]) if "--bg" in argv else 60
    T = json.load(open(SPEC))
    z = zipfile.ZipFile(src)
    paths = [p for p in z.namelist() if re.search(rx, p) and o2r.rtype(z.read(p)[:0x40]) == "OTEX"]
    tiles = []
    for p in paths:
        img = decode_path(z, p, T).astype(np.float32)
        a = img[..., 3:4] / 255
        rgb = img[..., :3] * a + bg * (1 - a)
        im = Image.fromarray(rgb.astype(np.uint8)).resize((img.shape[1] * scale, img.shape[0] * scale), Image.NEAREST)
        tiles.append((p.rsplit("/", 1)[1], im))
    if not tiles:
        print("no match")
        return
    cw = max(t[1].width for t in tiles) + 4
    ch = max(t[1].height for t in tiles) + 14
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new("RGB", (cw * min(cols, len(tiles)), ch * rows), (20, 20, 30))
    d = ImageDraw.Draw(S)
    for k, (name, im) in enumerate(tiles):
        x, y = (k % cols) * cw, (k // cols) * ch
        S.paste(im, (x + 2, y + 12))
        d.text((x + 2, y), name[:cw // 6], fill=(255, 255, 0))
    S.save(out)
    print(f"{len(tiles)} textures -> {out} {S.size}")


if __name__ == "__main__":
    main(sys.argv)
