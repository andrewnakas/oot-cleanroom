"""CLEAN ROOM: spec facts + kept archive -> clean oot.o2r.

    python -m games.oot.generate <spec dir> <kept.o2r> <out oot.o2r> [--only tex|snd|bg] [--base clean.o2r]

--base starts from an earlier clean archive (quick texture iterations).

Textures: colour grid + alpha outline + our detail (cleanroom.decomp.gen.from_digest),
or a hook (fonts, labels, faces: games.oot.drawn). Palette (CI) textures: every
image is generated as RGBA first; each palette is then fitted to the clean
images that use it, and the indices are re-derived. Secondary (swap) palettes
follow the primary one, recoloured by their own coarse grid.
Samples: resynthesised from the outline, our own 2-predictor VADPCM book.
Backgrounds: JPEG from the 16x16 grid plus detail.
"""
import io
import re
import struct
import json
import os
import sys

import numpy as np

from cleanroom.gfx import texfmt
from cleanroom.decomp.gen import from_digest, h32, upsample_grid, detail, two_predictors
from cleanroom.audio import descriptor, vadpcm
from games.oot import o2r
from games.oot.extract_spec import FMT

try:
    from games.oot import drawn
except ImportError:                  # optional hooks
    drawn = None


SKY = ("vr_fine", "vr_cloud", "vr_holy")
ROOMBG = re.compile(r"textures/vr_\w+VR_static/")       # prerendered room backdrops (shops, houses)


def fbm(seed, w, h, cells=(32, 16, 8, 4, 2)):
    """Our own fractal noise in [-1, 1] (sum of smooth value-noise octaves)."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for k, c in enumerate(cells):
        out += amp * (detail(seed + k, w, h, 1.0, float(c)) - 1.0)
        tot += amp
        amp *= 0.55
    return out / tot


def sky_clouds(img, path):
    """Skies: soft cloud banks brightening the grid's gradient, strongest where the grid is light."""
    h, w = img.shape[:2]
    n = fbm(h32("sky", path), w, h)
    lum = img[..., :3].mean(-1) / 255.0
    cover = np.clip(n * 1.6 + 0.1, 0, 1) * (0.35 + 0.65 * lum)
    out = img.astype(np.float32)
    out[..., :3] = out[..., :3] * (1 - 0.35 * cover[..., None]) + 245 * 0.35 * cover[..., None]
    out[..., :3] *= (1 + 0.06 * fbm(h32("sky2", path), w, h, (4, 2)))[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def encode_plain(rgba, t):
    fmt, siz = FMT[t]
    return texfmt.encode(rgba, fmt, siz)


def quantise(pixels, k, seed):
    """pixels (N,4) uint8 -> palette (k,4). k-means on RGB, alpha kept binary."""
    px = pixels.astype(np.float32)
    opaque = px[:, 3] >= 128
    rng = np.random.default_rng(seed)
    pal = np.zeros((k, 4), np.float32)
    n_clear = 1 if (~opaque).any() else 0
    if n_clear:
        pal[0] = [0, 0, 0, 0]
        cm = px[~opaque, :3].mean(0)
        pal[0, :3] = cm
    src = px[opaque][:, :3] if opaque.any() else px[:, :3]
    if len(src) > 20000:
        src = src[rng.choice(len(src), 20000, replace=False)]
    kk = k - n_clear
    uniq = np.unique(src.astype(np.int32), axis=0).astype(np.float32)
    if len(uniq) <= kk:
        c = np.zeros((kk, 3), np.float32)
        c[:len(uniq)] = uniq
        c[len(uniq):] = uniq[-1] if len(uniq) else 0
    else:
        c = uniq[rng.choice(len(uniq), kk, replace=False)]
        for _ in range(10):
            lab = np.argmin(((src[:, None, :] - c[None]) ** 2).sum(-1), 1) if len(src) * kk < 4e7 else \
                np.concatenate([np.argmin(((s[:, None, :] - c[None]) ** 2).sum(-1), 1) for s in np.array_split(src, 20)])
            for j in range(kk):
                m = lab == j
                if m.any():
                    c[j] = src[m].mean(0)
    pal[n_clear:, :3] = c + rng.uniform(-9, 9, c.shape)     # centroids must not snap onto the same 5-bit grid points
    pal[n_clear:, 3] = 255
    return np.clip(np.round(pal), 0, 255).astype(np.uint8)


def index_image(rgba, pal, seed=0, amp=None):
    px = rgba.reshape(-1, 4).astype(np.int32)
    if amp is None:
        amp = 30 if len(pal) <= 16 else 44      # dense 256-colour palettes need a wider pick
    px[:, :3] += np.random.default_rng(seed).integers(-amp, amp + 1, (len(px), 3))   # stochastic dither between entries
    p = pal.astype(np.int32)
    opaque_p = p[:, 3] >= 128
    d = ((px[:, None, :3] - p[None, :, :3]) ** 2).sum(-1)
    d = d + np.where((px[:, 3:4] >= 128) != opaque_p[None, :], 10 ** 7, 0)
    return np.argmin(d, 1).astype(np.uint8).reshape(rgba.shape[:2])


def pal_cell_means(d):
    """Mean colour per entry region of a palette's own coarse grid (entries in raster order)."""
    w, h = d["w"], d["h"]
    n = int(round(len(d["grid"]) ** 0.5))
    g = np.asarray(d["grid"], np.float32).reshape(n, n, 4)
    ys = np.minimum(np.arange(h) * n // max(1, h), n - 1)
    xs = np.minimum(np.arange(w) * n // max(1, w), n - 1)
    return g[ys][:, xs].reshape(-1, 4)


def gen_textures(T, P, kept, hook_stats):
    out = {}
    rgba = {}
    hooked = set()
    for path, d in T.items():
        img = drawn.texture(path, d) if drawn else None
        if img is not None:
            hook_stats["hooked"] += 1
            hooked.add(path)
            img = np.clip(img, 0, 255).astype(np.uint8)
        else:
            hook_stats["digest"] += 1
            img = from_digest(path, d)
            if any(k in path for k in SKY) and not path.endswith("TLUT"):
                img = sky_clouds(img, path)
            elif ROOMBG.search(path) and not path.endswith("TLUT"):
                f = img.astype(np.float32)
                f[..., :3] *= (1 + 0.10 * fbm(h32("paint", path), img.shape[1], img.shape[0], (16, 8, 4, 2)))[..., None]
                img = np.clip(f, 0, 255).astype(np.uint8)
        # per-texel dither: smooth regions must not quantise to the same texels as retail
        rng = np.random.default_rng(h32("tdither", path))
        img = img.astype(np.int16)
        amp = 3 if (any(k in path for k in SKY) or ROOMBG.search(path)) else (8 if path in hooked else 13)   # skies and our drawings stay clean
        img[..., :3] += rng.integers(-amp, amp + 1, img.shape[:2] + (3,), dtype=np.int16)
        rgba[path] = np.clip(img, 0, 255).astype(np.uint8)
    # palettes: primary users define them
    primary = {}
    for path, d in T.items():
        if d["type"] in (3, 4) and d.get("pal"):
            primary.setdefault(d["pal"][0], []).append(path)
    clean_pal = {}
    for p, users in primary.items():
        entries = P[p]["entries"]
        k = min(entries, 16 if any(T[u]["type"] == 3 for u in users) else 256)
        px = np.concatenate([rgba[u].reshape(-1, 4) for u in users])
        pal = quantise(px, k, h32("pal", p))
        full = np.zeros((entries, 4), np.uint8)
        full[:k] = pal
        clean_pal[p] = full
    # secondary palettes: recolour the primary by the ratio of the coarse grids
    for p in P:
        if p in clean_pal:
            continue
        users = P[p]["users"]
        base = next((T[u]["pal"][0] for u in users if T[u]["pal"][0] in clean_pal), None)
        entries = P[p]["entries"]
        if base is None or T[base]["w"] * T[base]["h"] != entries:
            clean_pal[p] = from_digest(p, T[p]).reshape(-1, 4)[:entries]
            continue
        mine, theirs = pal_cell_means(T[p]), pal_cell_means(T[base])
        ratio = (mine[:, :3] + 8) / (theirs[:, :3] + 8)
        pal = clean_pal[base].astype(np.float32)
        pal[:, :3] *= ratio
        pal[:, 3] = np.where(mine[:, 3] >= 128, 255, 0)
        clean_pal[p] = np.clip(pal, 0, 255).astype(np.uint8)
    for path, d in T.items():
        t = d["type"]
        if path in clean_pal:
            pal = clean_pal[path].reshape(d["h"], d["w"], 4)
            out[path] = encode_plain(pal, t)
        elif t in (3, 4):
            if d.get("pal"):
                idx = index_image(rgba[path], clean_pal[d["pal"][0]], h32("idx", path),
                                  amp=18 if (any(k in path for k in SKY) or ROOMBG.search(path)) else (14 if path in hooked else None)) + d.get("idx_base", 0)
            else:                                     # no known palette: grey grid is an index map
                idx = np.round(rgba[path][..., 0].astype(np.float32) * ((16 if t == 3 else 256) - 1) / 255).astype(np.uint8)
            img = np.zeros(idx.shape + (4,), np.uint8)
            img[..., 0] = idx
            out[path] = encode_plain(img, t)
        else:
            out[path] = encode_plain(rgba[path], t)
    return out


def gen_sample(path, d):
    n = d.get("nframes")
    bits = 4 if d["codec"] == 0 else 2
    fb = 1 + 2 * bits
    rate = 32000.0
    x = drawn.sample(path, d) if (drawn and hasattr(drawn, "sample")) else None
    if x is None:
        x = descriptor.synthesize(d["desc"], n, rate, seed=h32("smp", path))
    x = np.asarray(x, np.float32)[:n]
    x = np.pad(x, (0, n - len(x)))
    ls, le, lc = d["loop"]
    if lc != 0 and le > ls and le <= n:
        x = descriptor.make_loop_seamless(x, ls, le)
    dither = np.random.default_rng(h32("dither", path)).integers(-1, 2, n)
    pcm = np.clip(np.round(np.clip(x, -1, 1) * 30000) + dither, -32768, 32767).astype(np.int64)
    book = vadpcm.make_book(two_predictors(pcm.astype(np.float64)))
    data, book, dec = vadpcm.encode(pcm, book, bits=bits)
    data = (data + bytes(d["size"]))[:d["size"]]
    states = vadpcm.loop_state(dec, ls)[:d["nstates"]] if d["nstates"] else []
    states += [0] * (d["nstates"] - len(states))
    return data, states, book


def gen_background(path, d, seed):
    from PIL import Image
    w, h = d["w"], d["h"]
    img = upsample_grid(d["grid"], 16, w, h)
    img[..., :3] *= detail(seed, w, h, 0.05, 6.0)[..., None]
    img[..., :3] += np.random.default_rng(seed).uniform(-14, 14, (h, w, 3))
    im = Image.fromarray(np.clip(img[..., :3], 0, 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92, subsampling=2)     # 4:2:0 like the retail backgrounds
    jpg = buf.getvalue()
    # SoH's loader sizes its output buffer from the resource's data size and then
    # writes a full 320x240x2 image: backgrounds must be (at least) that long.
    return jpg + bytes(max(0, 320 * 240 * 2 - len(jpg)))


def main(argv):
    spec, kept_path, out_path = argv[1:4]
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else {"tex", "snd", "bg"}
    files = o2r.read_all(argv[argv.index("--base") + 1] if "--base" in argv else kept_path)
    T = json.load(open(os.path.join(spec, "textures.json")))
    P = json.load(open(os.path.join(spec, "palettes.json")))
    S = json.load(open(os.path.join(spec, "samples.json")))
    B = json.load(open(os.path.join(spec, "backgrounds.json")))
    stats = {"hooked": 0, "digest": 0}
    if "tex" in only:
        for path, texels in gen_textures(T, P, files, stats).items():
            files[path] = o2r.tex_replace(files[path], texels)
    ns = 0
    if "snd" in only:
        for path, d in S.items():
            if "desc" not in d:
                continue
            s = o2r.smp_parse(files[path])
            s["data"], s["states"], book = gen_sample(path, d)
            s["order"], s["npred"], s["book"] = book["order"], book["npred"], list(book["book"])
            files[path] = o2r.smp_build(files[path], s)
            ns += 1
    nb = 0
    if "bg" in only:
        for path, d in B.items():
            files[path] = o2r.bg_build(files[path], gen_background(path, d, h32("bg", path)))
            nb += 1
    # unreferenced data blobs (no display list, room or C source uses them): blanked, since
    # some may be leftover image data; the text/ blobs are Navi's hint text (kept facts)
    nblob = 0
    for path, data in files.items():
        if o2r.rtype(data) == "OBLB" and not path.startswith("text/"):
            n = struct.unpack("<I", data[o2r.HDR:o2r.HDR + 4])[0]
            files[path] = data[:o2r.HDR + 4] + bytes(n) + data[o2r.HDR + 4 + n:]
            nblob += 1
    print(f"blobs blanked: {nblob}")
    o2r.write_all(out_path, files)
    print(f"generated: textures {stats}, samples {ns}, backgrounds {nb} -> {out_path} "
          f"({os.path.getsize(out_path) // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv)
