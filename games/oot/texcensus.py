"""Which textures a scene's own geometry uses, and how: surface orientation,
covered area, wrap. Evidence for describing each texture (no pixels involved).

    python -m games.oot.texcensus <clean oot.o2r> <scene dir name> [...] -> texcensus.json
"""
import json
import os
import re
import sys

import numpy as np

from games.oot import o2r
from games.oot.dlrender import Archive, Renderer

HERE = os.path.dirname(__file__)


def census(arc, scene):
    dls = sorted(n for n in arc.files if re.match(r"scenes/\w+/%s_scene/" % re.escape(scene), n)
                 and o2r.rtype(arc.files[n]) == "ODLT")
    R = Renderer(arc, 8)
    R.tris = []
    R.new_state()
    for dl in dls:
        R.run(dl)
    use = {}
    for pos, uv, col, n, ts in R.tris:
        t = ts.get("tex")
        if not t:
            continue
        e1, e2 = pos[1] - pos[0], pos[2] - pos[0]
        nrm = np.cross(e1, e2)
        area = float(np.linalg.norm(nrm)) / 2
        if area <= 0:
            continue
        ny = float(nrm[1] / (np.linalg.norm(nrm) + 1e-9))
        u = use.setdefault(t, {"area": 0.0, "up": 0.0, "down": 0.0, "side": 0.0, "tlut": ts.get("tlut"),
                               "cms": ts["tile"].get("cms", 0), "cmt": ts["tile"].get("cmt", 0), "tris": 0})
        u["area"] += area
        u["tris"] += 1
        u["up" if ny > 0.6 else ("down" if ny < -0.6 else "side")] += area
    return use


def main(argv):
    arc = Archive(o2r.read_all(argv[1]))
    out = {}
    for scene in argv[2:]:
        u = census(arc, scene)
        out[scene] = u
        top = sorted(u.items(), key=lambda kv: -kv[1]["area"])
        print(f"{scene}: {len(u)} textures; top by area:")
        for t, v in top[:8]:
            o = max(("up", "side", "down"), key=lambda k: v[k])
            print(f"   {t.rsplit('/', 1)[1]:40s} area {v['area']:12.0f} {o}")
    json.dump(out, open(os.path.join(HERE, "texcensus.json"), "w"), indent=0)


if __name__ == "__main__":
    main(sys.argv)
