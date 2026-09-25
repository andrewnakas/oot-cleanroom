"""Dungeon room minimaps (map_i_static, 96x85 I4) drawn from each room's own
geometry, placed with the game's compass tables so Link's arrow lines up.

The compass puts world (x, z) at screen (160 + (offX + x/sx)/10, 120 - (offY - z/sy)/10);
the minimap's top-left is at (204, 140) (R_DGN_MINIMAP_X/Y). Tables come from
the game code (z_map_data.c / z_map_exp.c in the SoH source).

    python -m games.oot.minimaps <clean oot.o2r> <soh src dir> <out dir> [--sheet png]
"""
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

from games.oot import o2r
from games.oot.dlrender import Archive, Renderer

SCENES = ["ydan", "ddan", "bdan", "Bmori1", "HIDAN", "MIZUsin", "jyasinzou", "HAKAdan", "HAKAdanCH", "ice_doukutu"]
MAP_X, MAP_Y, W, H = 204, 140, 96, 85


def c_array(src, name):
    m = re.search(r"\b" + name + r"\s*\[[^\]]*\](\s*\[[^\]]*\])?\s*=\s*\{(.*?)\};", src, re.S)
    body = m.group(2)
    if "{" in body:
        return [[float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", row)] for row in re.findall(r"\{([^{}]*)\}", body)]
    return [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", body)]


def tables(soh_src):
    data = open(os.path.join(soh_src, "code", "z_map_data.c"), encoding="utf-8").read()
    exp = open(os.path.join(soh_src, "code", "z_map_exp.c"), encoding="utf-8").read()
    names = re.findall(r"(g\w+MinimapTex)", re.search(r"minimapTableDangeon\[\]\s*=\s*\{(.*?)\};", exp, re.S).group(1))
    return {"offX": c_array(data, "sRoomCompassOffsetX"), "offY": c_array(data, "sRoomCompassOffsetY"),
            "texOff": c_array(data, "sDgnMinimapTexIndexOffset"), "info": c_array(data, "sDgnCompassInfo"),
            "floorY": c_array(data, "sFloorCoordY"), "names": names}


def room_tris(arc, scene, room):
    rx = re.compile(r"scenes/nonmq/%s_scene/%s_room_%d(DL|Set)" % (scene, scene, room))
    dls = sorted(n for n in arc.files if rx.match(n) and o2r.rtype(arc.files[n]) == "ODLT")
    R = Renderer(arc, 8)
    R.tris = []
    R.new_state()
    for dl in dls:
        R.run(dl)
    return [t[0] for t in R.tris]


def draw(tris, sx, sy, offx, offy, ylo=-1e9, yhi=1e9, ss=4):
    img = Image.new("L", (W * ss, H * ss), 0)
    edge = Image.new("L", (W * ss, H * ss), 0)
    d, e = ImageDraw.Draw(img), ImageDraw.Draw(edge)
    for p in tris:
        v1, v2 = p[1] - p[0], p[2] - p[0]
        n = np.cross(v1, v2)
        ln = np.linalg.norm(n)
        if ln == 0 or abs(n[1]) / ln < 0.6:           # floors (either winding)
            continue
        if not (ylo <= p[:, 1].mean() < yhi):
            continue
        pts = [((160 + (offx + x / sx) / 10 - MAP_X) * ss, (120 - (offy - z / sy) / 10 - MAP_Y) * ss) for x, _, z in p]
        d.polygon(pts, fill=150)
        e.line(pts + [pts[0]], fill=255, width=1)
    fill = np.asarray(img, np.float32) / 255
    fill = fill.reshape(H, ss, W, ss).mean((1, 3))
    # outline where the filled area ends
    m = fill > 0.3
    ring = np.zeros_like(m)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ring |= ~np.roll(np.roll(m, dy, 0), dx, 1)
    ring &= m
    out = np.where(ring, 1.0, np.clip(fill, 0, 1) * 0.28)
    return out


def main(argv):
    arc = Archive(o2r.read_all(argv[1]))
    T = tables(argv[2])
    out = argv[3]
    os.makedirs(out, exist_ok=True)
    made = []
    cache = {}
    for mi, scene in enumerate(SCENES):
        start = int(T["texOff"][mi])
        end = int(T["texOff"][mi + 1]) if mi + 1 < len(SCENES) else len(T["names"])
        sx, sy = T["info"][mi][0], T["info"][mi][1]
        floors = sorted(T["floorY"][mi])
        for k in range(start, end):
            name = T["names"][k]
            m = re.search(r"Room(\d+)(?:Floor(\d+)|Basement(\d+))?", name)
            if not m:
                continue
            room = int(m.group(1))
            if (scene, room) not in cache:
                cache[(scene, room)] = room_tris(arc, scene, room)
            tris = cache[(scene, room)]
            if not tris:
                continue
            ylo, yhi = -1e9, 1e9
            fl = m.group(2) or m.group(3)
            if fl:
                ys = sorted({round(float(t[:, 1].mean()) / 200) * 200 for t in tris})
                # split the room's floor heights into bands; FloorN / BasementN pick one band
                bands = np.array_split(np.array(ys), max(1, len(ys) and min(len(ys), 3)))
                idx = int(fl) - 1
                if m.group(3):
                    bands = bands[::-1]
                if idx < len(bands) and len(bands[idx]):
                    ylo, yhi = bands[idx].min() - 100, bands[idx].max() + 100
            local = k - start
            offx = T["offX"][mi][local] if local < len(T["offX"][mi]) else 1000
            offy = T["offY"][mi][local] if local < len(T["offY"][mi]) else -800
            img = draw(tris, sx, sy, offx, offy, ylo, yhi)
            Image.fromarray((img * 255).astype(np.uint8)).save(os.path.join(out, name + ".png"))
            made.append(name)
    if "--sheet" in argv:
        ims = [Image.open(os.path.join(out, n + ".png")) for n in made[:40]]
        S = Image.new("L", (W * 10, H * ((len(ims) + 9) // 10)), 40)
        for i, im in enumerate(ims):
            S.paste(im, ((i % 10) * W, (i // 10) * H))
        S.save(argv[argv.index("--sheet") + 1])
    print(f"minimaps: {len(made)} -> {out}")


if __name__ == "__main__":
    main(sys.argv)
