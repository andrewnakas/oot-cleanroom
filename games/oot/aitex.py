"""Generated surface textures for the most visible places (Kokiri Forest, Hyrule Field)
and characters (child Link, Kokiri kids).

Each texture's description comes from evidence, never pixels:
  - how the scene's own geometry uses it (games.oot.texcensus: floor / wall / ceiling, area),
  - its kept colour grid (hue, brightness) and kept alpha outline (cut-out or solid),
  - its name where the decomp names it (boot, belt, tunic, hair, shield...), and the place.
Stable Diffusion 1.5 makes a seamless (circular-padded) 512 px material; it is shrunk to
the slot and its coarse colours are pulled to the kept 4x4 grid, so the scene keeps its
palette and layout. Prompts/seeds are logged in overrides/textures/_log.json.

    python -m games.oot.aitex [--only regex] [--list]
"""
import colorsys
import json
import os
import re
import sys
import zlib

import numpy as np
from PIL import Image

from cleanroom.decomp.gen import upsample_grid, unpack_alpha2

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "overrides", "textures")
STYLE = "macro close-up photo of the material surface, seamless tileable PBR texture, flat, even lighting, highly detailed, sharp"
NEG = ("aerial view, satellite, landscape, map, sky, horizon, trees, houses, buildings, objects, text, watermark, logo, "
       "border, frame, perspective, vignette, person, face, blurry, lowres")

SCENES = {"spot04": "a sunny forest village of tree houses", "spot00": "wide grassy plains"}
CHAR_OBJECTS = ("object_link_child", "object_km1", "object_kw1")

NAMED = [  # (regex on texture name, material)
    (r"Boot|Boots", "worn brown leather"), (r"BeltClasp|Buckle", "polished brass metal"),
    (r"Belt", "brown leather strap"), (r"DekuShieldFront", "round wooden shield face with a bold red spiral emblem"),
    (r"DekuShieldBack|HylianShieldBack", "dark wooden planks with iron rivets"),
    (r"Ear|Hand|Nose|Skin", "smooth light skin"), (r"Waist|Tunic", "green woven cloth fabric"),
    (r"TunicFringe", "green cloth fringe"), (r"FairyOcarina", "glazed blue clay"),
    (r"Slingshot(?!Seed)", "carved wood"), (r"SlingshotSeed", "small brown nut"),
    (r"SwordJewel|Emblem", "polished blue gemstone"), (r"MasterSword(Guard|Pommel)", "purple and gold metal"),
    (r"GoronBracelet", "carved red stone"), (r"GoronSymbol", "red stone carving"),
    (r"KokiriSwordSheath", "brown leather sheath"), (r"Hairline|Hair", "soft hair strands"),
    (r"BootWrinkle", "wrinkled brown leather"),
]


def hue_words(rgb):
    r, g, b = [c / 255 for c in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h *= 360
    if v < 0.18:
        return "dark"
    if s < 0.15:
        return "grey" if v < 0.75 else "pale"
    if 60 <= h < 170:
        return "green"
    if 170 <= h < 260:
        return "blue"
    if 20 <= h < 60:
        return "brown" if v < 0.65 else "tan"
    return "red"


def scene_material(orient, hue, cutout, big, scene):
    forest = scene == "spot04"
    if cutout:
        return {"green": "cluster of green leaves", "brown": "wooden fence posts",
                "tan": "dry grass tufts", "pale": "white flowers"}.get(hue, "leaves and twigs")
    if hue == "blue":
        return "clear shallow water surface"
    if orient == "up":
        return {"green": "lush short grass with clover" if forest else "green meadow grass",
                "brown": "forest dirt ground with fallen leaves" if forest else "packed earth path", "tan": "sandy dirt road", "grey": "flat stone paving",
                "dark": "dark forest soil", "pale": "light stone"}.get(hue, "grassy ground")
    # walls and ceilings
    return {"green": "moss covered rock" if not forest else "dense green hedge leaves",
            "brown": ("rough tree bark" if big else "wooden planks") if forest else "brown earth cliff",
            "tan": "sandstone cliff", "grey": "rough grey rock cliff", "dark": "dark tree bark",
            "pale": "weathered stone"}.get(hue, "rock wall")


def targets():
    T = json.load(open(os.path.join(HERE, "spec", "textures.json")))
    C = json.load(open(os.path.join(HERE, "texcensus.json")))
    out = {}
    for scene, uses in C.items():
        if scene not in SCENES:
            continue
        areas = sorted((v["area"] for v in uses.values()), reverse=True)
        big_cut = areas[min(len(areas) - 1, 6)] if areas else 0
        for path, u in uses.items():
            if path not in T or re.search(r"(TLUT|Eye|Mouth)", path):
                continue
            d = T[path]
            g = np.asarray(d["grid"], np.float32)
            mean = g[:, :3].mean(0)
            orient = max(("up", "side", "down"), key=lambda k: u[k])
            cutout = "alpha2" in d and float((unpack_alpha2(d["alpha2"], d["w"], d["h"]) < 128).mean()) > 0.2
            mat = scene_material(orient, hue_words(mean), cutout, u["area"] >= big_cut, scene)
            out[path] = {"prompt": f"{mat}, {SCENES[scene]}", "tile": not cutout, "why":
                         f"{scene} {orient} {hue_words(mean)} {'cutout' if cutout else 'solid'} area {u['area']:.0f}"}
    for p, d in T.items():
        if p.split("/")[1] not in CHAR_OBJECTS or re.search(r"(TLUT|Eye|Mouth|Mask|Hood|Unused)", p):
            continue
        name = p.rsplit("/", 1)[1]
        mat = next((m for rx, m in NAMED if re.search(rx, name)), None)
        if not mat:
            continue
        if "Hair" in name:
            mat = f"{hue_words(np.asarray(d['grid'], np.float32)[:, :3].mean(0))} {mat}"
        out[p] = {"prompt": mat, "tile": "ShieldFront" not in name, "why": "named " + name}
    return out, T


def color_match(img, d):
    """Keep the kept colours; borrow only the generated texture's light/dark detail."""
    h, w = img.shape[:2]
    n = int(round(len(d["grid"]) ** 0.5))
    target = upsample_grid(d["grid"], n, w, h)[..., :3]
    lum = img[..., :3].mean(-1)
    k = max(1, min(w, h) // 4)
    pad = np.pad(lum, k, mode="wrap")
    blur = np.zeros_like(lum)
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            blur += pad[k + dy:k + dy + h, k + dx:k + dx + w]
    blur /= (2 * k + 1) ** 2
    detail = np.clip((lum + 6) / (blur + 6), 0.55, 1.6)
    return np.clip(target * detail[..., None], 0, 255)


def make_tileable(pipe):
    import torch
    for m in list(pipe.unet.modules()) + list(pipe.vae.modules()):
        if isinstance(m, torch.nn.Conv2d):
            m.padding_mode = "circular"


def main(argv):
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    todo, T = targets()
    if only:
        todo = {k: v for k, v in todo.items() if re.search(only, k)}
    if "--list" in argv:
        for k, v in sorted(todo.items()):
            print(f"{k.rsplit('/', 1)[1]:36s} {v['prompt'][:60]:60s} [{v['why']}]")
        print(len(todo), "textures")
        return
    import torch
    from diffusers import StableDiffusionPipeline
    os.makedirs(OUT, exist_ok=True)
    pipe = StableDiffusionPipeline.from_pretrained(os.environ.get("SD_MODEL", "stable-diffusion-v1-5/stable-diffusion-v1-5"),
                                                   torch_dtype=torch.float16, variant="fp16", safety_checker=None,
                                                   requires_safety_checker=False, cache_dir=os.environ.get("SD_CACHE"))
    pipe.enable_model_cpu_offload()
    pipe.enable_attention_slicing()
    tiled = False
    log_p = os.path.join(OUT, "_log.json")
    log = json.load(open(log_p)) if os.path.exists(log_p) else {}
    for i, (path, b) in enumerate(sorted(todo.items(), key=lambda kv: not kv[1]["tile"])):
        if b["tile"] and not tiled:
            make_tileable(pipe)
            tiled = True
        if not b["tile"] and tiled:                      # non-tiling pictures come first; reload is not needed
            pass
        d = T[path]
        seed = zlib.crc32(path.encode()) % 100000
        prompt = b["prompt"].split(",")[0] + ", " + (STYLE if b["tile"] else "centered, flat texture, highly detailed")
        g = torch.Generator("cpu").manual_seed(seed)
        img = pipe(prompt, negative_prompt=NEG, num_inference_steps=22, guidance_scale=7.0,
                   width=512, height=512, generator=g).images[0]
        w, h = d["w"], d["h"]
        small = np.asarray(img.resize((max(w, 1), max(h, 1)), Image.LANCZOS), np.float32)
        rgb = color_match(small, d)
        a = unpack_alpha2(d["alpha2"], w, h) if "alpha2" in d else np.full((h, w), 255, np.float32)
        out = np.concatenate([rgb, a[..., None]], -1).astype(np.uint8)
        Image.fromarray(out, "RGBA").save(os.path.join(OUT, path.rsplit("/", 1)[1] + ".png"))
        log[path] = {"prompt": prompt, "negative": NEG, "seed": seed, "steps": 22, "why": b["why"]}
        if i % 10 == 0:
            json.dump(log, open(log_p, "w"), indent=1)
            print(f"{i}/{len(todo)}", flush=True)
    json.dump(log, open(log_p, "w"), indent=1)
    print("done", len(todo))


if __name__ == "__main__":
    main(sys.argv)
