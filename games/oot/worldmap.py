"""Pause world map picture: a top-down render of Hyrule Field's own room
geometry with our textures (dlrender), framed like a parchment map.

    python -m games.oot.worldmap <clean oot.o2r> <out png> [--size 216x128]
"""
import sys

import numpy as np
from PIL import Image

from games.oot import o2r
from games.oot.dlrender import Archive, Renderer


def render(arc, prefix="scenes/shared/spot00_scene/spot00_room_0", w=216, h=128, ss=3):
    dls = sorted(n for n in arc.files if n.startswith(prefix) and o2r.rtype(arc.files[n]) == "ODLT")
    S = max(w, h) * ss
    R = Renderer(arc, S, light=(0.3, 0.9, 0.3), cull=False, alpha_min=-1)
    img = R.draw(dls, yaw=0, pitch=-90, roll=0, margin=0.0)
    # crop the square render to the map aspect (the field is wider than tall)
    top = (S - h * ss) // 2
    img = img[top:top + h * ss, (S - w * ss) // 2:(S - w * ss) // 2 + w * ss]
    img = img.reshape(h, ss, w, ss, 4).mean((1, 3))
    # parchment where nothing was drawn, gentle vignette
    parch = np.asarray([0.86, 0.78, 0.58], np.float32)
    a = img[..., 3:4]
    rgb = img[..., :3] * a + parch * (1 - a)
    yy, xx = np.mgrid[0:h, 0:w]
    v = 1 - 0.35 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    rgb = rgb * v[..., None] * 0.8 + parch * 0.2
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = np.clip(rgb, 0, 1)
    out[..., 3] = 1
    return out, len(R.tris)


def main(argv):
    arc = Archive(o2r.read_all(argv[1]))
    img, n = render(arc)
    Image.fromarray((img * 255).astype(np.uint8)).save(argv[2])
    print(f"world map: {n} triangles -> {argv[2]}")


if __name__ == "__main__":
    main(sys.argv)
