"""Prerendered locations, generated: Stable Diffusion 1.5 + depth ControlNet, guided by a
depth render of each location's own collision from the game camera (games.oot.bgscenes)
and our own written description (location_briefs.json). The model never sees retail pixels.

    python -m games.oot.aibg <guides dir (bgscenes out)> [--only regex] [--steps 30] [--seed 7]

Writes games/oot/overrides/backgrounds/<name>.png (JPEG backgrounds, 320x240 view) and
games/oot/overrides/pictures/<texture>.png (panorama faces, 256x256), which generate.py uses.
Prompts, seeds and model ids are recorded in overrides/backgrounds/_log.json.
"""
import json
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(__file__)
BASE = os.environ.get("SD_MODEL", "stable-diffusion-v1-5/stable-diffusion-v1-5")
CONTROL = os.environ.get("SD_CONTROL", "lllyasviel/control_v11f1p_sd15_depth")


def panorama_scene(info):
    return "texture" in info


def brief_for(scene, briefs):
    keys = sorted((k for k in briefs if not k.startswith("_")), key=len, reverse=True)
    for k in keys:
        if scene == k:
            return briefs[k]
    for k in keys:
        if scene.startswith(k):
            return briefs[k]
    return "a room"


def main(argv):
    import torch
    from diffusers import ControlNetModel, StableDiffusionControlNetPipeline, UniPCMultistepScheduler
    gdir = argv[1]
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    steps = int(argv[argv.index("--steps") + 1]) if "--steps" in argv else 30
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 7
    briefs = json.load(open(os.path.join(HERE, "location_briefs.json")))
    out_bg = os.path.join(HERE, "overrides", "backgrounds")
    out_pic = os.path.join(HERE, "overrides", "pictures")
    os.makedirs(out_bg, exist_ok=True)
    cn = ControlNetModel.from_pretrained(CONTROL, torch_dtype=torch.float16, variant="fp16",
                                         cache_dir=os.environ.get("SD_CONTROL_CACHE"))
    pipe = StableDiffusionControlNetPipeline.from_pretrained(BASE, controlnet=cn, torch_dtype=torch.float16,
                                                             variant="fp16", safety_checker=None,
                                                             requires_safety_checker=False,
                                                             cache_dir=os.environ.get("SD_CACHE"))
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    pipe.enable_model_cpu_offload()
    pipe.enable_attention_slicing()
    log_path = os.path.join(out_bg, "_log.json")
    log = json.load(open(log_path)) if os.path.exists(log_path) else {}
    for name in sorted(os.listdir(gdir)):
        if only and not re.search(only, name):
            continue
        info_p = os.path.join(gdir, name, "info.json")
        if not os.path.exists(info_p):
            continue
        info = json.load(open(info_p))
        scene = info["scene"].replace("_scene", "")
        outdoor = scene.startswith(("shrine", "market", "entra", "enrui"))
        if scene.startswith("market") and panorama_scene(info):
            outdoor = True
        prompt = brief_for(scene, briefs) + ", " + (briefs["_style_outdoor"] if outdoor else briefs["_style"])
        panorama = "texture" in info
        fwd = info.get("fwd", [0, 0, 1])
        topdown = (not panorama) and fwd[1] < -0.6         # camera looking down steeply
        if topdown:
            prompt = "bird's eye view looking straight down at the floor of " + prompt.replace(", seen from above", "")
        if panorama:
            prompt = prompt.replace(", seen from above", "") + ", eye-level view of one wall"
        depth = Image.open(os.path.join(gdir, name, "depth.png")).convert("RGB")
        size = (512, 512) if panorama else (576, 432)
        depth = depth.resize(size, Image.BILINEAR)
        import zlib
        g = torch.Generator("cpu").manual_seed(seed + zlib.crc32(name.encode()) % 100000)   # own seed per image
        img = pipe(prompt, image=depth, negative_prompt=briefs["_negative"], num_inference_steps=steps,
                   guidance_scale=7.0, controlnet_conditioning_scale=(0.45 if outdoor else (1.0 if topdown else 0.85)),
                   width=size[0], height=size[1], generator=g).images[0]
        if panorama:
            img.resize((256, 256), Image.LANCZOS).save(os.path.join(out_pic, name + ".png"))
        else:
            img.resize((320, 240), Image.LANCZOS).save(os.path.join(out_bg, name + ".png"))
        log[name] = {"prompt": prompt, "negative": briefs["_negative"], "seed": seed, "steps": steps,
                     "base": BASE, "control": CONTROL, "guide": "depth of own collision, game camera"}
        json.dump(log, open(log_path, "w"), indent=1)
        print("done", name, flush=True)


if __name__ == "__main__":
    main(sys.argv)
