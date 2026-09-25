"""SoH's own soh.o2r, with the few textures that reuse retail pixels redrawn.

    python ports/soh/clean_soh.py <soh.o2r in> <soh.o2r out>

The taint scan (games.oot.taint_report with soh.o2r) lists them; they are
re-typeset here in the same style as our file-select buttons.
"""
import sys

import numpy as np

from cleanroom.gfx import texfmt
from games.oot import o2r, drawn
from games.oot.extract_spec import FMT

REDRAW = {
    "textures/title_static/gFileSelMQButtonTex": ["MQ"],
    "textures/title_static/gFileSelRANDButtonTex": ["RAND"],
}


def main(argv):
    files = o2r.read_all(argv[1])
    for path, lines in REDRAW.items():
        t = o2r.tex_parse(files[path])
        fmt, siz = FMT[t["type"]]
        d = {"w": t["w"], "h": t["h"], "type": 9}
        img = drawn.label_tex(path.replace("Tex", "ButtonTex") if "Button" not in path else path, d, lines)
        img = np.clip(img, 0, 255).astype(np.uint8)
        files[path] = o2r.tex_replace(files[path], texfmt.encode(img, fmt, siz))
    o2r.write_all(argv[2], files)
    print(f"soh.o2r: {len(REDRAW)} textures redrawn -> {argv[2]}")


if __name__ == "__main__":
    main(sys.argv)
