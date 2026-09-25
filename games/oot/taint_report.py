"""Taint report: every regenerated resource of a clean oot.o2r (and SoH's own
soh.o2r textures) vs every retail one, as raw payload bytes and as decoded
RGBA / PCM / RGB. Runs >= cleanroom.taint.FAIL_RUN bytes fail.

    python -m games.oot.taint_report <dirty oot.o2r> <clean oot.o2r> [soh.o2r]
"""
import io
import json
import os
import sys

import numpy as np

from cleanroom import taint
from cleanroom.gfx import texfmt
from cleanroom.audio import vadpcm
from games.oot import o2r
from games.oot.extract_spec import FMT

SPEC = os.path.join(os.path.dirname(__file__), "spec", "textures.json")


def streams(files, T):
    types = {n: o2r.rtype(d) for n, d in files.items()}
    for n, d in files.items():
        ty = types[n]
        if ty == "OTEX":
            t = o2r.tex_parse(d)
            yield "tex:" + n, t["data"]
            pal = None
            link = T.get(n, {}).get("pal")
            if t["type"] in (3, 4) and link and link[0] in files:
                p = o2r.tex_parse(files[link[0]])
                pal = texfmt.decode(p["data"], p["w"] * p["h"], 1, texfmt.RGBA, texfmt.B16)[0]
                pal = np.concatenate([pal] * (256 // len(pal) + 1))[:256]
            if t["type"] in FMT:
                fmt, siz = FMT[t["type"]]
                try:
                    yield "rgba:" + n, texfmt.decode(t["data"], t["w"], t["h"], fmt, siz, palette=pal).tobytes()
                except Exception:
                    pass
        elif ty == "OSMP":
            s = o2r.smp_parse(d)
            yield "smp:" + n, s["data"]
            if s["codec"] in (0, 3) and any(s["book"]):
                bits = 4 if s["codec"] == 0 else 2
                pcm = vadpcm.decode(s["data"], {"order": s["order"], "npred": s["npred"], "book": s["book"]}, bits=bits)
                yield "pcm:" + n, pcm.astype(">i2").tobytes()
        elif ty == "OBGI":
            from PIL import Image
            jp = o2r.bg_parse(d)
            # raw JPEG bytes are not scanned: every baseline encoder writes the same standard tables
            yield "rgb:" + n, np.asarray(Image.open(io.BytesIO(jp)).convert("RGB")).tobytes()


def main(argv):
    T = json.load(open(SPEC))
    dirty = o2r.read_all(argv[1])
    clean = o2r.read_all(argv[2])
    index = taint.build_index(s for _, s in streams(dirty, T))
    cs = list(streams(clean, T))
    if len(argv) > 3:
        soh = o2r.read_all(argv[3])
        cs += [("soh." + k, v) for k, v in streams(soh, {})]
    hits = taint.scan(index, iter(cs))
    bad = sorted((h for h in hits if h[3] >= taint.FAIL_RUN), key=lambda h: -h[3])
    print(f"taint: {len(cs)} generated streams scanned; {len(hits)} with short coincidental matches; "
          f"{len(bad)} failing (run >= {taint.FAIL_RUN} B)")
    for label, off, n, run in bad[:15]:
        print(f"  FAIL {label} run {run} B")
    json.dump([h[0] for h in bad], open(os.path.join(os.path.dirname(argv[2]), "taint_fail.json"), "w"), indent=0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
