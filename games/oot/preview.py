"""Clean preview: render textures matching a regex with drawn.py (or the digest)
into a contact sheet, without building an archive.

    python -m games.oot.preview <regex> <out.png> [--scale 3] [--cols 8] [--bg 90]
"""
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

from cleanroom.decomp.gen import from_digest
from games.oot import drawn

SPEC = os.path.join(os.path.dirname(__file__), "spec", "textures.json")


def main(argv):
    rx, out = argv[1:3]
    scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 3
    cols = int(argv[argv.index("--cols") + 1]) if "--cols" in argv else 8
    bg = int(argv[argv.index("--bg") + 1]) if "--bg" in argv else 90
    T = json.load(open(SPEC))
    tiles = []
    for p, d in T.items():
        if not re.search(rx, p):
            continue
        img = drawn.texture(p, d)
        img = from_digest(p, d) if img is None else np.clip(img, 0, 255)
        img = img.astype(np.float32)
        if d["type"] in (5, 6):                 # I formats: intensity is alpha too
            img[..., 3] = img[..., 0]
        a = img[..., 3:4] / 255
        rgb = img[..., :3] * a + bg * (1 - a)
        im = Image.fromarray(rgb.astype(np.uint8)).resize((d["w"] * scale, d["h"] * scale), Image.NEAREST)
        tiles.append((p.rsplit("/", 1)[1], im))
    if not tiles:
        print("no match")
        return
    cw = max(t[1].width for t in tiles) + 4
    ch = max(t[1].height for t in tiles) + 14
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new("RGB", (cw * min(cols, len(tiles)), ch * rows), (20, 20, 30))
    dr = ImageDraw.Draw(S)
    for k, (name, im) in enumerate(tiles):
        x, y = (k % cols) * cw, (k // cols) * ch
        S.paste(im, (x + 2, y + 12))
        dr.text((x + 2, y), name[:cw // 6], fill=(255, 255, 0))
    S.save(out)
    print(f"{len(tiles)} textures -> {out} {S.size}")


if __name__ == "__main__":
    main(sys.argv)
