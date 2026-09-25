"""Prerendered locations: each JPEG background's camera and a render of the
location's own geometry from that camera (guides for image generation).

    python -m games.oot.bgscenes <clean oot.o2r> <out dir>

For every OBGI background:
  camera   the room's image entry names its background camera (bgCamIndex); the scene's
           collision header holds that camera (pos, rot as binary angles, fov*100)
  guides   depth.png (near = bright), normal.png, material.png (from collision surface
           types), mesh.png (the room's own 3D display lists with our textures, if any)
  info     info.json: scene, camera, sizes; descriptions live in location_briefs.json
"""
import json
import math
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

from games.oot import o2r
from games.oot.dlrender import Archive, Renderer

W, H = 320, 240


def parse_collision(d):
    p = o2r.HDR + 12
    nv = struct.unpack("<I", d[p:p + 4])[0]
    p += 4
    verts = np.frombuffer(d[p:p + nv * 6], "<i2").reshape(nv, 3).astype(np.float32)
    p += nv * 6
    npoly = struct.unpack("<I", d[p:p + 4])[0]
    p += 4
    polys = np.frombuffer(d[p:p + npoly * 16], "<u2").reshape(npoly, 8).copy()
    p += npoly * 16
    nt = struct.unpack("<I", d[p:p + 4])[0]
    p += 4
    ptypes = np.frombuffer(d[p:p + nt * 8], "<u4").reshape(nt, 2).copy()
    p += nt * 8
    nc = struct.unpack("<I", d[p:p + 4])[0]
    p += 4
    cams = []
    for i in range(nc):
        st, num, idx = struct.unpack("<HhI", d[p:p + 8])
        cams.append((st, num, idx))
        p += 8
    npos = struct.unpack("<I", d[p:p + 4])[0]
    p += 4
    pos = np.frombuffer(d[p:p + npos * 6], "<i2").reshape(npos, 3).astype(np.int32) if npos else np.zeros((0, 3), np.int32)
    return {"verts": verts, "polys": polys, "ptypes": ptypes, "cams": cams, "pos": pos}


def camera_for(col, cam_index):
    st, num, idx = col["cams"][cam_index]
    pos = col["pos"][idx].astype(np.float32)
    rot = col["pos"][idx + 1]
    fov = int(col["pos"][idx + 2][0]) if num >= 3 else 6000
    if fov == -1:
        fov = 6000
    if fov <= 360:
        fov *= 100
    yaw = rot[1] * 2 * math.pi / 65536
    pitch = -rot[0] * 2 * math.pi / 65536
    fwd = np.array([math.cos(pitch) * math.sin(yaw), math.sin(pitch), math.cos(pitch) * math.cos(yaw)], np.float32)
    return {"eye": pos, "fwd": fwd, "fovy": fov / 100.0, "setting": st, "rot": rot.tolist()}


def basis(cam):
    f = cam["fwd"] / np.linalg.norm(cam["fwd"])
    up = np.array([0, 1, 0], np.float32)
    r = np.cross(f, up)
    r /= np.linalg.norm(r) + 1e-9
    u = np.cross(r, f)
    return f, r, u


def project(cam, pts):
    f, r, u = basis(cam)
    q = pts - cam["eye"]
    z = q @ f
    x = q @ r
    y = q @ u
    t = math.tan(math.radians(cam["fovy"]) / 2)
    sx = (x / (z * t * (W / H)) * 0.5 + 0.5) * W
    sy = (0.5 - y / (z * t) * 0.5) * H
    return sx, sy, z


def render_collision(col, cam, ss=2):
    """depth (camera z), normals (view space), material id per pixel."""
    Wd, Hd = W * ss, H * ss
    zbuf = np.full((Hd, Wd), np.inf, np.float32)
    nrm = np.zeros((Hd, Wd, 3), np.float32)
    mat = np.zeros((Hd, Wd), np.int32)
    v = col["verts"]
    f, r, u = basis(cam)
    ys, xs = np.mgrid[0:Hd, 0:Wd].astype(np.float32) + 0.5
    for poly in col["polys"]:
        ia, ib, ic = poly[1] & 0x1FFF, poly[2] & 0x1FFF, poly[3] & 0x1FFF
        P = v[[ia, ib, ic]]
        sx, sy, z = project(cam, P)
        if (z < 5).any():
            continue
        sx, sy = sx * ss, sy * ss
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(area) < 1e-6:
            continue
        x0, x1 = int(max(0, np.floor(sx.min()))), int(min(Wd, np.ceil(sx.max()) + 1))
        y0, y1 = int(max(0, np.floor(sy.min()))), int(min(Hd, np.ceil(sy.max()) + 1))
        if x0 >= x1 or y0 >= y1:
            continue
        px, py = xs[y0:y1, x0:x1], ys[y0:y1, x0:x1]
        w0 = ((sx[1] - px) * (sy[2] - py) - (sx[2] - px) * (sy[1] - py)) / area
        w1 = ((sx[2] - px) * (sy[0] - py) - (sx[0] - px) * (sy[2] - py)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        # perspective-correct depth
        iz = w0 / z[0] + w1 / z[1] + w2 / z[2]
        zz = np.where(inside, 1 / np.maximum(iz, 1e-9), np.inf)
        vis = zz < zbuf[y0:y1, x0:x1]
        if not vis.any():
            continue
        n = np.array([poly[4], poly[5], poly[6]], np.float32).view(np.int16).astype(np.float32) / 32767 \
            if poly[4] > 32767 or True else None
        n = np.array([np.int16(poly[4]), np.int16(poly[5]), np.int16(poly[6])], np.float32) / 32767
        nv = np.array([n @ r, n @ u, -(n @ f)], np.float32)
        zbuf[y0:y1, x0:x1] = np.where(vis, zz, zbuf[y0:y1, x0:x1])
        nrm[y0:y1, x0:x1][vis] = nv
        mat[y0:y1, x0:x1][vis] = int(poly[0])
    zbuf = zbuf.reshape(H, ss, W, ss).min((1, 3))
    nrm = nrm.reshape(H, ss, W, ss, 3).mean((1, 3))
    mat = mat[::ss, ::ss]
    return zbuf, nrm, mat


SURFACE = {0: "dirt", 1: "sand", 2: "stone", 3: "shallow water", 4: "shallow water", 5: "deep water", 6: "lava",
           7: "grass", 8: "wood", 9: "wood", 10: "packed earth", 11: "ice", 12: "carpet"}


def material_names(col, mat):
    """surface material (footstep type) per collision polygon type."""
    out = {}
    for t in np.unique(mat):
        if t >= len(col["ptypes"]):
            continue
        d1 = int(col["ptypes"][t][1])       # data[0] was written second: low word
        sfx = (d1 >> 0) & 0xF if False else (int(col["ptypes"][t][0]) >> 0) & 0xF
        out[int(t)] = SURFACE.get(sfx, "stone")
    return out


def depth_png(z):
    fin = np.isfinite(z)
    img = np.zeros(z.shape, np.float32)
    if fin.any():
        lo, hi = np.percentile(z[fin], 1), np.percentile(z[fin], 99)
        img[fin] = 1 - np.clip((z[fin] - lo) / max(1, hi - lo), 0, 1)
    return (img * 255).astype(np.uint8)


def backgrounds(files):
    """background path -> (scene dir, room path, camera id)"""
    out = {}
    bgs = [n for n, d in files.items() if o2r.rtype(d) == "OBGI"]
    rooms = [n for n, d in files.items() if o2r.rtype(d) == "OROM"]
    for b in bgs:
        sd = b.rsplit("/", 1)[0]
        key = b.encode()
        for r in rooms:
            if not r.startswith(sd):
                continue
            d = files[r]
            i = d.find(key)
            if i < 0:
                continue
            cam_id = d[i - 5]                  # u8 id, then u32 string length, then the path
            if sum(1 for x in bgs if x.rsplit("/", 1)[0] == sd) == 1:
                cam_id = 0                     # single-image rooms: the scene's one fixed camera
            out[b] = (sd, r, int(cam_id))
            break
    return out


def main(argv):
    files = o2r.read_all(argv[1])
    out = argv[2]
    os.makedirs(out, exist_ok=True)
    arc = Archive(files)
    bg = backgrounds(files)
    summary = []
    for b, (sd, room, cam_id) in sorted(bg.items()):
        cols = [n for n in files if n.startswith(sd + "/") and o2r.rtype(files[n]) == "OCOL"]
        if not cols:
            continue
        col = parse_collision(files[cols[0]])
        if cam_id >= len(col["cams"]):
            summary.append(f"{b}: cam {cam_id} missing")
            continue
        cam = camera_for(col, cam_id)
        z, n, mat = render_collision(col, cam)
        name = b.rsplit("/", 1)[1]
        d = os.path.join(out, name)
        os.makedirs(d, exist_ok=True)
        Image.fromarray(depth_png(z)).save(os.path.join(d, "depth.png"))
        Image.fromarray(((n * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)).save(os.path.join(d, "normal.png"))
        # the room's own 3D meshes (counters, doors...) with our textures, from the same camera
        info = {"background": b, "scene": sd.split("/")[-1], "room": room, "cam_id": cam_id,
                "eye": cam["eye"].tolist(), "fwd": cam["fwd"].tolist(), "fovy": cam["fovy"],
                "setting": cam["setting"], "coverage": float(np.isfinite(z).mean()),
                "materials": sorted(set(material_names(col, mat).values()))}
        json.dump(info, open(os.path.join(d, "info.json"), "w"), indent=1)
        summary.append(f"{name:55s} cam {cam_id} fov {cam['fovy']:.0f} cover {info['coverage']:.2f}")
    print("\n".join(summary))
    print(f"{len(summary)} backgrounds -> {out}")
    panoramas(files, out)


# ------------------------------------------------------------ panorama rooms (vr_*VR skyboxes)

PANORAMA = {  # texture folder -> (scene, faces)
    "vr_LHVR": ("link_home", 4), "vr_K5VR": ("kokiri_home5", 4), "vr_K4VR": ("kokiri_home4", 4),
    "vr_K3VR": ("kokiri_home3", 4), "vr_KHVR": ("kokiri_home", 4), "vr_KSVR": ("kokiri_shop", 2),
    "vr_KKRVR": ("kakariko", 4), "vr_KR3VR": ("kakariko3", 4), "vr_IPVR": ("impa", 4), "vr_LBVR": ("souko", 4),
    "vr_MLVR": ("malon_stable", 4), "vr_TTVR": ("tent", 3), "vr_MDVR": ("market_day", 4),
    "vr_MNVR": ("market_night", 4), "vr_RUVR": ("market_ruins", 4), "vr_ALVR": ("alley_shop", 2),
    "vr_DGVR": ("drag", 2), "vr_FCVR": ("face_shop", 2), "vr_GLVR": ("golon", 2), "vr_ZRVR": ("zoora", 2),
    "vr_NSVR": ("night_shop", 2), "vr_SP1a": ("shop1", 2),
}
FACES = [np.array([0, 0, -1.0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([-1.0, 0, 0])]


def panoramas(files, out):
    global W, H
    tex = sorted(n for n in files if re.match(r"textures/vr_\w+VR_static/|textures/vr_SP1a_static/", n)
                 and o2r.rtype(files[n]) == "OTEX" and not n.endswith("TLUT"))
    groups = {}
    for n in tex:
        key = n.split("/")[1].replace("_static", "")
        groups.setdefault(key, []).append(n)
    done = []
    for key, texs in sorted(groups.items()):
        if key not in PANORAMA:
            continue
        scene, nfaces = PANORAMA[key]
        cols = [n for n in files if re.match(r"scenes/\w+/%s_scene/" % scene, n) and o2r.rtype(files[n]) == "OCOL"]
        if not cols:
            continue
        col = parse_collision(files[cols[0]])
        # the panorama surrounds a first-person viewer standing in the middle of the room
        v = col["verts"]
        floor = np.percentile(v[:, 1], 10)
        eye = np.array([(v[:, 0].min() + v[:, 0].max()) / 2, floor + 50, (v[:, 2].min() + v[:, 2].max()) / 2], np.float32)
        # textures in face order: Bg, Bg2, Bg3, Bg4
        order = sorted(texs, key=lambda n: int(re.search(r"(\d?)BgTex$", n).group(1) or 1))
        for i, tpath in enumerate(order[:nfaces]):
            cam = {"eye": eye, "fwd": FACES[i].astype(np.float32), "fovy": 90.0, "setting": -1}
            W, H = 256, 256
            z, nrm, mat = render_collision(col, cam)
            W, H = 320, 240
            name = tpath.rsplit("/", 1)[1]
            d = os.path.join(out, name)
            os.makedirs(d, exist_ok=True)
            Image.fromarray(depth_png(z)).save(os.path.join(d, "depth.png"))
            json.dump({"texture": tpath, "scene": scene, "face": i, "eye": eye.tolist(),
                       "fwd": FACES[i].tolist(), "coverage": float(np.isfinite(z).mean())},
                      open(os.path.join(d, "info.json"), "w"), indent=1)
            done.append(f"{name:28s} {scene:14s} face {i} cover {np.isfinite(z).mean():.2f}")
    print("\n".join(done))
    print(f"{len(done)} panorama faces")


if __name__ == "__main__":
    main(sys.argv)
