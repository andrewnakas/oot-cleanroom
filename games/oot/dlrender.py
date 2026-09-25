"""Software renderer for SoH display lists (F3DEX2 subset) from a clean .o2r.

Used to draw pictures (item icons...) from the game's own geometry with our
regenerated textures: render(archive, [dl paths], size, yaw, pitch) -> RGBA.

Supports: vertices (G_VTX_OTR_HASH), TRI1/TRI2/QUAD, sub-DLs, SETTIMG by
hash + LOADTLUT, SETTILE/SETTILESIZE (wrap/mirror/clamp), G_TEXTURE scale,
geometry mode (lighting, texgen, culling), prim/env colour, the two-cycle
colour combiner. No TMEM emulation: a load binds the whole texture resource.
"""
import struct

import numpy as np

from cleanroom.gfx import texfmt
from games.oot import o2r
from games.oot.extract_spec import FMT

G_LIGHTING, G_TEXTURE_GEN, G_CULL_FRONT, G_CULL_BACK = 0x00020000, 0x00040000, 0x0200, 0x0400


class Archive:
    def __init__(self, files):
        self.files = files
        self.by_hash = {o2r.crc64(n): n for n in files}
        self._tex = {}

    def vtx(self, name):
        d = self.files[name]
        typ, cnt = struct.unpack("<II", d[o2r.HDR:o2r.HDR + 8])
        a = np.frombuffer(d[o2r.HDR + 8:o2r.HDR + 8 + cnt * 16], dtype=np.dtype(
            [("x", "<i2"), ("y", "<i2"), ("z", "<i2"), ("f", "<u2"), ("s", "<i2"), ("t", "<i2"),
             ("r", "u1"), ("g", "u1"), ("b", "u1"), ("a", "u1")]))
        return a

    def texture(self, name, tlut=None):
        k = (name, tlut)
        if k not in self._tex:
            t = o2r.tex_parse(self.files[name])
            pal = None
            if t["type"] in (3, 4):
                if tlut and tlut in self.files:
                    p = o2r.tex_parse(self.files[tlut])
                    pal = texfmt.decode(p["data"], p["w"] * p["h"], 1, texfmt.RGBA, texfmt.B16)[0]
                    pal = np.concatenate([pal] * (256 // len(pal) + 1))[:256]
                else:
                    pal = np.tile(np.arange(256, dtype=np.uint8)[:, None], (1, 4))
                    pal[:, 3] = 255
            fmt, siz = FMT[t["type"]]
            img = texfmt.decode(t["data"], t["w"], t["h"], fmt, siz, palette=pal).astype(np.float32) / 255
            if t["type"] in (5, 6):
                img[..., 3] = img[..., 0]
            self._tex[k] = img
        return self._tex[k]


def _src(sel, table, env):
    v = table.get(sel)
    return env[v] if isinstance(v, str) else v


class Renderer:
    def __init__(self, arc, size=128, light=(-0.4, 0.55, 0.75), cull=True, alpha_min=0.35):
        self.arc = arc
        self.cull = cull
        self.alpha_min = alpha_min
        self.size = size
        self.tris = []                       # list of (pos3x3, uv3x2, shade3x4, state dict)
        self.light = np.asarray(light, np.float32) / np.linalg.norm(light)

    # ---------------------------------------------------------------- DL walk
    def run(self, name, depth=0):
        st = self.state
        d = self.arc.files[name]
        p = o2r.HDR + 4
        while p % 8:
            p += 1
        while p + 8 <= len(d):
            w0, w1 = struct.unpack("<II", d[p:p + 8])
            op = w0 >> 24
            nxt = p + 8
            if op in (0x20, 0x31, 0x32, 0x33, 0x35, 0x36):
                hi, lo = struct.unpack("<II", d[p + 8:p + 16])
                h = (hi << 32) | lo
                nxt = p + 16
                ref = self.arc.by_hash.get(h)
                if op == 0x20:
                    st["timg"] = ref
                elif op == 0x31 and ref and depth < 12:
                    self.run(ref, depth + 1)
                    if (w0 >> 16) & 0xFF == 1:          # branch: no return
                        return
                elif op == 0x32 and ref:
                    n = (w0 >> 12) & 0xFF
                    v0 = ((w0 >> 1) & 0x7F) - n
                    a = self.arc.vtx(ref)[w1 // 16:w1 // 16 + n]
                    for i, v in enumerate(a):
                        if 0 <= v0 + i < 64:
                            st["vbuf"][v0 + i] = v
            elif op == 0x05:
                self.tri(st, (w0 >> 16 & 0xFF) // 2, (w0 >> 8 & 0xFF) // 2, (w0 & 0xFF) // 2)
            elif op in (0x06, 0x07):
                self.tri(st, (w0 >> 16 & 0xFF) // 2, (w0 >> 8 & 0xFF) // 2, (w0 & 0xFF) // 2)
                self.tri(st, (w1 >> 16 & 0xFF) // 2, (w1 >> 8 & 0xFF) // 2, (w1 & 0xFF) // 2)
            elif op == 0xD7:
                st["tex_on"] = (w0 >> 1) & 0x7F
                st["tscale"] = ((w1 >> 16) / 65536.0 or 1 / 65536, (w1 & 0xFFFF) / 65536.0 or 1 / 65536)
            elif op == 0xD9:
                st["geom"] = (st["geom"] & (w0 & 0xFFFFFF)) | w1
            elif op == 0xF0 and st.get("timg"):
                st["tlut"] = st["timg"]
            elif op in (0xF3, 0xF4) and st.get("timg"):
                st["tex"] = st["timg"]
            elif op == 0xF5:
                tile = (w1 >> 24) & 7
                st["tiles"][tile] = {"cmt": (w1 >> 18) & 3, "maskt": (w1 >> 14) & 0xF,
                                     "cms": (w1 >> 8) & 3, "masks": (w1 >> 4) & 0xF,
                                     "shiftt": (w1 >> 10) & 0xF, "shifts": w1 & 0xF}
            elif op == 0xF2:
                tile = (w1 >> 24) & 7
                st["tsize"][tile] = ((w0 >> 12) & 0xFFF, w0 & 0xFFF, (w1 >> 12) & 0xFFF, w1 & 0xFFF)
            elif op == 0xFA:
                st["prim"] = np.asarray([(w1 >> 24) & 255, (w1 >> 16) & 255, (w1 >> 8) & 255, w1 & 255], np.float32) / 255
            elif op == 0xFB:
                st["env"] = np.asarray([(w1 >> 24) & 255, (w1 >> 16) & 255, (w1 >> 8) & 255, w1 & 255], np.float32) / 255
            elif op == 0xFC:
                st["comb"] = (w0 & 0xFFFFFF, w1)
            elif op == 0xDF:
                return
            p = nxt

    def tri(self, st, a, b, c):
        vs = [st["vbuf"][i] for i in (a, b, c)]
        if any(v is None for v in vs):
            return
        pos = np.asarray([[v["x"], v["y"], v["z"]] for v in vs], np.float32)
        col = np.asarray([[v["r"], v["g"], v["b"], v["a"]] for v in vs], np.float32)
        uv = np.asarray([[v["s"], v["t"]] for v in vs], np.float32) / 32.0
        lit = bool(st["geom"] & G_LIGHTING)
        if lit:
            n = col[:, :3].copy()
            n[n > 127] -= 256
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        else:
            n = None
        self.tris.append((pos, uv, col, n, dict(tex=st.get("tex"), tlut=st.get("tlut"), prim=st["prim"],
                                                 env=st["env"], comb=st["comb"], geom=st["geom"],
                                                 tscale=st["tscale"], tile=dict(st["tiles"].get(0, {})),
                                                 tsize=st["tsize"].get(0, (0, 0, 0, 0)), tex_on=st["tex_on"])))

    def new_state(self):
        self.state = {"vbuf": [None] * 64, "geom": G_LIGHTING, "prim": np.ones(4, np.float32),
                      "env": np.ones(4, np.float32), "comb": None, "tscale": (1.0, 1.0), "tiles": {},
                      "tsize": {}, "tex_on": 1}

    # ---------------------------------------------------------------- raster
    def draw(self, dls, yaw=0.0, pitch=0.0, roll=0.0, margin=0.08, prim=None, env=None):
        self.tris = []
        self.new_state()                        # state carries across the list, like the game's draw code
        if prim is not None:
            self.state["prim"] = np.asarray(prim, np.float32) / 255
        if env is not None:
            self.state["env"] = np.asarray(env, np.float32) / 255
        for dl in dls:
            self.run(dl)
        S = self.size
        img = np.zeros((S, S, 4), np.float32)
        if not self.tris:
            return img
        cy, sy = np.cos(np.radians(yaw)), np.sin(np.radians(yaw))
        cp, sp = np.cos(np.radians(pitch)), np.sin(np.radians(pitch))
        cr, sr = np.cos(np.radians(roll)), np.sin(np.radians(roll))
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32)
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float32)
        Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]], np.float32)
        R = Rz @ Rx @ Ry
        allp = np.concatenate([t[0] for t in self.tris]) @ R.T
        lo, hi = allp.min(0), allp.max(0)
        span = max(hi[0] - lo[0], hi[1] - lo[1]) * (1 + 2 * margin) or 1
        ctr = (lo + hi) / 2
        zbuf = np.full((S, S), -1e9, np.float32)
        ys, xs = np.mgrid[0:S, 0:S].astype(np.float32) + 0.5
        for pos, uv, col, n, ts in self.tris:
            q = pos @ R.T
            sx = (q[:, 0] - ctr[0]) / span * S + S / 2
            syy = S / 2 - (q[:, 1] - ctr[1]) / span * S
            area = (sx[1] - sx[0]) * (syy[2] - syy[0]) - (sx[2] - sx[0]) * (syy[1] - syy[0])
            if abs(area) < 1e-6:
                continue
            if self.cull and (ts["geom"] & G_CULL_BACK) and area > 0:
                continue
            if self.cull and (ts["geom"] & G_CULL_FRONT) and area < 0:
                continue
            x0, x1 = int(max(0, np.floor(sx.min()))), int(min(S, np.ceil(sx.max()) + 1))
            y0, y1 = int(max(0, np.floor(syy.min()))), int(min(S, np.ceil(syy.max()) + 1))
            if x0 >= x1 or y0 >= y1:
                continue
            px, py = xs[y0:y1, x0:x1], ys[y0:y1, x0:x1]
            w0 = ((sx[1] - px) * (syy[2] - py) - (sx[2] - px) * (syy[1] - py)) / area
            w1 = ((sx[2] - px) * (syy[0] - py) - (sx[0] - px) * (syy[2] - py)) / area
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
            if not inside.any():
                continue
            z = w0 * q[0, 2] + w1 * q[1, 2] + w2 * q[2, 2]
            vis = inside & (z > zbuf[y0:y1, x0:x1])
            if not vis.any():
                continue
            W = np.stack([w0[vis], w1[vis], w2[vis]], 1)
            if n is not None:
                nn = W @ (n @ R.T)
                nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-6)
                lam = np.clip(nn @ self.light, 0, 1)
                shade = np.ones((len(W), 4), np.float32)
                shade[:, :3] = (0.5 + 0.6 * lam)[:, None]
                shade[:, 3] = (W @ col[:, 3]) / 255
            else:
                nn = None
                shade = (W @ col) / 255
            tex = self.sample(ts, W @ uv, nn)
            out = self.combine(ts, tex, shade)
            a = np.clip(out[:, 3], 0, 1)
            keep = a > self.alpha_min
            if not keep.any():
                continue
            yy, xx = np.nonzero(vis)
            yy, xx = yy[keep] + y0, xx[keep] + x0
            zbuf[yy, xx] = z[vis][keep]
            img[yy, xx, :3] = np.clip(out[keep, :3], 0, 1)
            img[yy, xx, 3] = 1.0
        return img

    def sample(self, ts, uv, nn):
        if not ts["tex"] or ts["tex"] not in self.arc.files:
            return np.ones((len(uv), 4), np.float32)
        t = self.arc.texture(ts["tex"], ts["tlut"])
        h, w = t.shape[:2]
        if nn is not None and (ts["geom"] & G_TEXTURE_GEN):
            u = (nn[:, 0] * 0.5 + 0.5) * w
            v = (0.5 - nn[:, 1] * 0.5) * h
        else:
            u = uv[:, 0] * ts["tscale"][0] - ts["tsize"][0] / 4.0
            v = uv[:, 1] * ts["tscale"][1] - ts["tsize"][1] / 4.0
        tl = ts["tile"]

        def wrap(c, n, mode):
            if mode & 2:
                return np.clip(c, 0, n - 1)
            if mode & 1:
                m = np.mod(c, 2 * n)
                return np.where(m >= n, 2 * n - 1 - m, m)
            return np.mod(c, n)
        ui = wrap(np.floor(u).astype(np.int64), w, tl.get("cms", 0)).astype(int)
        vi = wrap(np.floor(v).astype(np.int64), h, tl.get("cmt", 0)).astype(int)
        return t[vi, ui]

    def combine(self, ts, tex, shade):
        n = len(tex)
        prim = np.broadcast_to(ts["prim"], (n, 4))
        env = np.broadcast_to(ts["env"], (n, 4))
        one = np.ones((n, 4), np.float32)
        zero = np.zeros((n, 4), np.float32)
        if ts["comb"] is None:
            return tex * shade
        w0, w1 = ts["comb"]
        f = {"a0": (w0 >> 20) & 0xF, "c0": (w0 >> 15) & 0x1F, "Aa0": (w0 >> 12) & 7, "Ac0": (w0 >> 9) & 7,
             "a1": (w0 >> 5) & 0xF, "c1": w0 & 0x1F, "b0": (w1 >> 28) & 0xF, "b1": (w1 >> 24) & 0xF,
             "Aa1": (w1 >> 21) & 7, "Ac1": (w1 >> 18) & 7, "d0": (w1 >> 15) & 7, "Ab0": (w1 >> 12) & 7,
             "Ad0": (w1 >> 9) & 7, "d1": (w1 >> 6) & 7, "Ab1": (w1 >> 3) & 7, "Ad1": w1 & 7}
        comb = zero
        for cyc in (0, 1):
            C = {0: comb, 1: tex, 2: tex, 3: prim, 4: shade, 5: env}
            a = C.get(f[f"a{cyc}"], one if f[f"a{cyc}"] == 6 else (np.full((n, 4), 0.5) if f[f"a{cyc}"] == 7 else zero))
            b = C.get(f[f"b{cyc}"], zero)
            cc = f[f"c{cyc}"]
            if cc <= 5:
                c = C[cc]
            else:
                al = {7: comb, 8: tex, 9: tex, 10: prim, 11: shade, 12: env}.get(cc)
                c = np.repeat(al[:, 3:4], 4, 1) if al is not None else (one if cc in (6, 14, 15) else zero)
            d = C.get(f[f"d{cyc}"], one if f[f"d{cyc}"] == 6 else zero)
            rgb = (a - b) * c + d
            A = {0: comb, 1: tex, 2: tex, 3: prim, 4: shade, 5: env}
            aa = A.get(f[f"Aa{cyc}"], one if f[f"Aa{cyc}"] == 6 else zero)[:, 3]
            ab = A.get(f[f"Ab{cyc}"], one if f[f"Ab{cyc}"] == 6 else zero)[:, 3]
            ac = {1: tex, 2: tex, 3: prim, 4: shade, 5: env}.get(f[f"Ac{cyc}"], one if f[f"Ac{cyc}"] in (0, 6) else zero)[:, 3]
            ad = A.get(f[f"Ad{cyc}"], one if f[f"Ad{cyc}"] == 6 else zero)[:, 3]
            comb = np.concatenate([rgb[:, :3], ((aa - ab) * ac + ad)[:, None]], 1)
        return comb
