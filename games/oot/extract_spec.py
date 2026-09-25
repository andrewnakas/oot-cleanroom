"""DIRTY ROOM: retail-extracted oot.o2r -> clean-room spec (coarse facts only).

    python -m games.oot.extract_spec <dirty oot.o2r> <soh xml dir N64_NTSC_12> <spec dir> <local dir>

Writes to <spec dir> (committed, facts only):
  textures.json     per texture: type, w, h, colour grid (4x4; 16x16 for >= 128 px
                    or skyboxes), 2-bit alpha outline if alpha varies, palette link
  palettes.json     palette path -> {entries, users}
  samples.json      per sample: codec, frame count, loop, coarse outline, median pitch
  backgrounds.json  per prerendered JPEG background: size, 16x16 grid
Writes to <local dir> (never published):
  kept.o2r          every resource with texels / sample data / JPEGs blanked:
                    the kept facts (geometry, collision, text, sequences, fonts...)
"""
import collections
import glob
import io
import json
import os
import re
import sys

import numpy as np

from cleanroom.gfx import texfmt
from cleanroom.decomp.spec import grid, alpha2
from cleanroom.audio import descriptor, vadpcm
from cleanroom.audio.pitch import median_f0
from games.oot import o2r

FMT = {1: (texfmt.RGBA, texfmt.B32), 2: (texfmt.RGBA, texfmt.B16), 3: (texfmt.CI, texfmt.B4),
       4: (texfmt.CI, texfmt.B8), 5: (texfmt.I, texfmt.B4), 6: (texfmt.I, texfmt.B8),
       7: (texfmt.IA, texfmt.B4), 8: (texfmt.IA, texfmt.B8), 9: (texfmt.IA, texfmt.B16)}


def xml_tluts(xml_dir):
    """texture name -> tlut name, from TlutOffset attributes (same File)."""
    out = {}
    for path in glob.glob(os.path.join(xml_dir, "**", "*.xml"), recursive=True):
        txt = open(path, encoding="utf-8").read()
        for fm in re.finditer(r"<File\b.*?</File>", txt, re.S):
            by_off, want = {}, []
            for m in re.finditer(r"<(\w+)\s([^>]*)/?>", fm.group(0)):
                at = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
                if "Offset" in at and "Name" in at:
                    by_off[int(at["Offset"], 16)] = at["Name"]
                if "TlutOffset" in at and "Name" in at:
                    want.append((at["Name"], int(at["TlutOffset"], 16)))
            for name, off in want:
                if off in by_off:
                    out[name] = by_off[off]
    return out


def _stem(name, suffixes):
    for suf in suffixes:
        if name.endswith(suf):
            name = name[:-len(suf)]
            break
    return re.sub(r"\d", "", name), sorted(re.findall(r"\d", name))


def pair_tlut(n, tex):
    """Tex <-> TLUT by name in the same folder or its *_pal_static twin."""
    d, base = n.rsplit("/", 1)
    dirs = {d, d.replace("_static", "_pal_static")}
    cands = [p for p in tex if p.rsplit("/", 1)[0] in dirs and ("TLUT" in p or "Pal" in p.rsplit("/", 1)[1])
             and tex[p]["type"] == 2]
    if not cands:
        return None
    want = _stem(base, ("Tex",))
    same = [p for p in cands if _stem(p.rsplit("/", 1)[1], ("TLUT", "Pal")) == want]
    if len(same) == 1:
        return same[0]
    loose = [p for p in cands if _stem(p.rsplit("/", 1)[1], ("TLUT", "Pal"))[0] == want[0]]
    if len(loose) == 1:
        return loose[0]
    pal_dir = [p for p in cands if p.rsplit("/", 1)[0] != d]
    if len(pal_dir) == 1:
        return pal_dir[0]
    return None


def decode_tex(t, pal_rgba=None):
    fmt, siz = FMT[t["type"]]
    return texfmt.decode(t["data"], t["w"], t["h"], fmt, siz, palette=pal_rgba)


def tex_fact(path, rgba, t):
    h, w = rgba.shape[:2]
    n = 16 if ("vr_" in path.lower() or "sky" in path.lower() or max(w, h) >= 128) else 4
    d = {"type": t["type"], "w": w, "h": h, "grid": grid(rgba, n)}
    if (rgba[..., 3] < 250).any():
        d["alpha2"] = alpha2(rgba[..., 3])
    return d


def book_dict(s):
    return {"order": s["order"], "npred": s["npred"], "book": s["book"]}


def sample_fact(s):
    d = {"codec": s["codec"], "medium": s["medium"], "size": len(s["data"]), "loop": s["loop"],
         "nstates": len(s["states"]), "order": s["order"], "npred": s["npred"]}
    if s["codec"] in (0, 3):                  # CODEC_ADPCM 9-byte / CODEC_SMALL_ADPCM 5-byte frames
        bits = 4 if s["codec"] == 0 else 2
        pcm = vadpcm.decode(s["data"], book_dict(s), bits=bits).astype(np.float64)
        d["nframes"] = len(s["data"]) // (1 + 2 * bits) * 16
    elif s["codec"] == 1:                     # CODEC_S8
        pcm = np.frombuffer(s["data"], np.int8).astype(np.float64) * 256
        d["nframes"] = len(s["data"])
    else:
        return d, False
    rate = 32000.0                            # outline only; playback rate comes from the font
    d["desc"] = descriptor.describe(pcm, rate)
    f0 = median_f0((pcm / 32768).astype(np.float32), rate)
    if f0:
        d["f0"] = round(f0, 1)
    return d, True


def main(argv):
    src, xml_dir, spec, local = argv[1:5]
    os.makedirs(spec, exist_ok=True)
    os.makedirs(local, exist_ok=True)
    files = o2r.read_all(src)
    types = {n: o2r.rtype(d) for n, d in files.items()}
    names = {o2r.crc64(n): n for n in files}
    by_base = collections.defaultdict(list)
    for n in files:
        by_base[n.rsplit("/", 1)[-1]].append(n)

    # palette links: display lists first, extractor XML second
    uses = collections.defaultdict(collections.Counter)
    carried = collections.defaultdict(collections.Counter)   # TLUT left loaded by an earlier DL of the same room
    last = {}
    for n in sorted(n for n in files if types[n] == "ODLT"):
        room = re.sub(r"(DL|Set)_?[0-9A-Fa-f]{4,}.*$", "", n)
        for tex, tl in o2r.dl_texture_uses(files[n])[0]:
            if tl is not None:
                uses[names[tex]][names[tl]] += 1
                last[room] = tl
            elif room in last:
                carried[names[tex]][names[last[room]]] += 1
    xt = xml_tluts(xml_dir)
    tex = {n: o2r.tex_parse(d) for n, d in files.items() if types[n] == "OTEX"}
    pal_of, how = {}, collections.Counter()
    for n, t in tex.items():
        if t["type"] not in (3, 4):
            continue
        if uses.get(n):
            pal_of[n] = [p for p, _ in uses[n].most_common()]
            how["dl"] += 1
            continue
        base = n.rsplit("/", 1)[-1]
        tl = xt.get(base)
        if tl:
            cands = [p for p in by_base.get(tl, []) if p.rsplit("/", 1)[0] == n.rsplit("/", 1)[0]] or by_base.get(tl, [])
            if cands:
                pal_of[n] = [cands[0]]
                how["xml"] += 1
                continue
        tl = pair_tlut(n, tex)
        if tl:
            pal_of[n] = [tl]
            how["name"] += 1
            continue
        if carried.get(n):
            pal_of[n] = [p for p, _ in carried[n].most_common()]
            how["carried"] += 1
            continue
        how["none"] += 1
    palettes = collections.defaultdict(list)
    for n, ps in pal_of.items():
        for p in ps:
            palettes[p].append(n)

    def pal_rgba(p):
        t = tex[p]
        p = texfmt.decode(t["data"], t["w"] * t["h"], 1, texfmt.RGBA, texfmt.B16)[0]
        return np.concatenate([p] * (256 // len(p) + 1))[:256]    # banks: index i -> entry i % n

    tfacts = {}
    for i, (n, t) in enumerate(tex.items()):
        if t["type"] in (3, 4):
            if n in pal_of:
                rgba = decode_tex(t, pal_rgba(pal_of[n][0]))
            else:
                rgba = decode_tex(t)                  # index as grey; generator keeps it as an index map
            d = tex_fact(n, rgba, t)
            if n in pal_of:
                d["pal"] = pal_of[n]
                e = tex[pal_of[n][0]]["w"] * tex[pal_of[n][0]]["h"]
                idx = np.frombuffer(t["data"], np.uint8) if t["type"] == 4 else None
                if idx is not None and e < 256 and idx.max() // e == idx.min() // e and idx.min() >= e:
                    d["idx_base"] = int(idx.min() // e * e)
        else:
            d = tex_fact(n, decode_tex(t), t)
        if n in palettes:
            d["is_pal"] = True
        tfacts[n] = d
    json.dump(tfacts, open(os.path.join(spec, "textures.json"), "w"), separators=(",", ":"))
    json.dump({p: {"entries": tex[p]["w"] * tex[p]["h"], "users": sorted(u)} for p, u in palettes.items()},
              open(os.path.join(spec, "palettes.json"), "w"), separators=(",", ":"))

    # samples
    sfacts, codecs = {}, collections.Counter()
    for n, d in files.items():
        if types[n] == "OSMP":
            s = o2r.smp_parse(d)
            codecs[s["codec"]] += 1
            sfacts[n], ok = sample_fact(s)
    json.dump(sfacts, open(os.path.join(spec, "samples.json"), "w"), separators=(",", ":"))

    # backgrounds
    from PIL import Image
    bfacts = {}
    for n, d in files.items():
        if types[n] == "OBGI":
            im = Image.open(io.BytesIO(o2r.bg_parse(d)))
            rgb = np.asarray(im.convert("RGBA"))
            bfacts[n] = {"w": im.width, "h": im.height, "mode": im.mode,
                         "sampling": getattr(im, "layer", None) and [l[1:3] for l in im.layer],
                         "grid": grid(rgb, 16)}
    json.dump(bfacts, open(os.path.join(spec, "backgrounds.json"), "w"), separators=(",", ":"))

    # kept archive: blank every regenerated payload
    kept = {}
    for n, d in files.items():
        ty = types[n]
        if ty == "OTEX":
            kept[n] = o2r.tex_replace(d, bytes(tex[n]["size"]))
        elif ty == "OSMP":
            s = o2r.smp_parse(d)
            s["data"] = bytes(len(s["data"]))
            s["states"] = [0] * len(s["states"])
            s["book"] = [0] * len(s["book"])
            kept[n] = o2r.smp_build(d, s)
        elif ty == "OBGI":
            kept[n] = d[:o2r.HDR]
        else:
            kept[n] = d
    o2r.write_all(os.path.join(local, "kept.o2r"), kept)
    print(f"spec: {len(tfacts)} textures ({dict(how)} palette links, {len(palettes)} palettes), "
          f"{len(sfacts)} samples codecs={dict(codecs)}, {len(bfacts)} backgrounds, "
          f"{collections.Counter(types.values()).get('OBLB', 0)} blobs kept -> {spec}")


if __name__ == "__main__":
    main(sys.argv)
