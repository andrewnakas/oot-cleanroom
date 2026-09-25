"""Download the image models used by games.oot.aibg (fp16 weights only).

    python -m games.oot.fetch_models [sd cache dir] [controlnet cache dir]

Stable Diffusion 1.5 and the SD1.5 depth ControlNet (both public). Neither is
given any retail material; they only see our own depth renders and text.
"""
import sys

from huggingface_hub import snapshot_download


def main(argv):
    sd_cache = argv[1] if len(argv) > 1 else "E:/hfcache"
    cn_cache = argv[2] if len(argv) > 2 else "C:/Users/andre/n64work/hfcache"
    p1 = snapshot_download("stable-diffusion-v1-5/stable-diffusion-v1-5", cache_dir=sd_cache, allow_patterns=[
        "model_index.json", "scheduler/*", "tokenizer/*", "text_encoder/config.json", "text_encoder/model.fp16.safetensors",
        "unet/config.json", "unet/diffusion_pytorch_model.fp16.safetensors", "vae/config.json",
        "vae/diffusion_pytorch_model.fp16.safetensors", "feature_extractor/*"])
    print("sd:", p1, flush=True)
    p2 = snapshot_download("lllyasviel/control_v11f1p_sd15_depth", cache_dir=cn_cache,
                           allow_patterns=["config.json", "diffusion_pytorch_model.fp16.safetensors"])
    print("controlnet:", p2, flush=True)


if __name__ == "__main__":
    main(sys.argv)
