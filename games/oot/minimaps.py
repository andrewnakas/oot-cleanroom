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
            if m.group(2) or m.group(3):
                # the dungeon's floor bands (sFloorCoordY), named top-down FloorN..Floor1, Basement1..
                fl_idx = [i for i in range(8) if T["floorY"][mi][i] < 9999]
                pn = [n for n in arc.files if "/g%sPauseScreenMapFloor" % PAUSE_NAMES[mi] in n]
                nf = max([int(x) for n in pn for x in re.findall(r"MapFloor(\d+)", n)] or [0])
                order = ["F%d" % k2 for k2 in range(nf, 0, -1)] + ["B%d" % k2 for k2 in range(1, 9)]
                want = ("F" + m.group(2)) if m.group(2) else ("B" + m.group(3))
                if want in order and order.index(want) < len(fl_idx):
                    fi = fl_idx[order.index(want)]
                    ylo = T["floorY"][mi][fi]
                    yhi = T["floorY"][mi][fi - 1] if fi > 0 and T["floorY"][mi][fi - 1] < 9999 else 1e9
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
    made2 = pause_maps(arc, argv[2], out)
    print(f"minimaps: {len(made)}, pause maps: {len(made2)} -> {out}")


# ------------------------------------------------------------ pause-screen dungeon maps

PAUSE_NAMES = ["DekuTree", "DodongosCavern", "Jabu", "ForestTemple", "FireTemple", "WaterTemple", "SpiritTemple",
               "ShadowTemple", "BottomOfTheWell", "IceCavern"]


def pause_maps(arc, soh_src, out):
    """map_48x85_static: per floor, every room's floors seen from above, each pixel holding the
    room's palette index (sRoomPalette; the game colours them at runtime). Left/right halves."""
    data = open(os.path.join(soh_src, "code", "z_map_data.c"), encoding="utf-8").read()
    pal = c_array(data, "sRoomPalette")
    fy = c_array(data, "sFloorCoordY")
    made = []
    for mi, (scene, nm) in enumerate(zip(SCENES, PAUSE_NAMES)):
        rooms = sorted({int(m.group(1)) for n in arc.files
                        for m in [re.match(r"scenes/nonmq/%s_scene/%s_room_(\d+)" % (scene, scene), n)] if m})
        tris = [(r, t) for r in rooms for t in room_tris(arc, scene, r)]
        floors = [i for i in range(8) if fy[mi][i] < 9999]
        names = sorted({m.group(1) for n in arc.files
                        for m in [re.search(r"g%sPauseScreenMap((?:Floor|Basement)\d)LeftTex$" % nm, n)] if m})
        nf = sum(1 for n in names if n.startswith("Floor"))
        order = ["Floor%d" % k for k in range(nf, 0, -1)] + ["Basement%d" % k for k in range(1, 9)]
        allp = np.concatenate([t for _, t in tris]) if tris else np.zeros((1, 3))
        x0, x1 = allp[:, 0].min(), allp[:, 0].max()
        z0, z1 = allp[:, 2].min(), allp[:, 2].max()
        sc = min((W - 6) / max(1, x1 - x0), (H - 6) / max(1, z1 - z0))
        for k, fi in enumerate(floors):
            if k >= len(order) or order[k] not in names:
                continue
            lo = fy[mi][fi]
            hi = fy[mi][fi - 1] if fi > 0 and fy[mi][fi - 1] < 9999 else 1e9
            img = Image.new("L", (W, H), 0)
            d = ImageDraw.Draw(img)
            for r, p in tris:
                v1, v2 = p[1] - p[0], p[2] - p[0]
                n = np.cross(v1, v2)
                ln = np.linalg.norm(n)
                if ln == 0 or abs(n[1]) / ln < 0.6 or not (lo <= p[:, 1].mean() < hi):
                    continue
                idx = int(pal[mi][r]) if r < len(pal[mi]) else 1
                pts = [(3 + (x - x0) * sc + (W - 6 - (x1 - x0) * sc) / 2, 3 + (z - z0) * sc + (H - 6 - (z1 - z0) * sc) / 2)
                       for x, _, z in p]
                d.polygon(pts, fill=idx * 17)
            a = np.asarray(img)
            rgba = np.zeros((H, W, 4), np.uint8)
            rgba[..., :3] = a[..., None]
            rgba[..., 3] = 255
            for half, sl in (("Left", slice(0, 48)), ("Right", slice(48, 96))):
                nmf = "g%sPauseScreenMap%s%sTex" % (nm, order[k], half)
                Image.fromarray(rgba[:, sl]).save(os.path.join(out, nmf + ".png"))
                made.append(nmf)
    return made


if __name__ == "__main__":
    main(sys.argv)
