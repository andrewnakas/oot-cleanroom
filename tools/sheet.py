"""Contact sheet: python tools/sheet.py out.png img1 img2 ... [--w 480] [--cols 3]"""
import sys
from PIL import Image, ImageDraw
args = sys.argv[1:]
w = int(args[args.index("--w") + 1]) if "--w" in args else 480
cols = int(args[args.index("--cols") + 1]) if "--cols" in args else 3
imgs = [a for i, a in enumerate(args[1:], 1) if not a.startswith("--") and not args[i - 1].startswith("--")]
ims = []
for p in imgs:
    im = Image.open(p).convert("RGB")
    im = im.resize((w, int(im.height * w / im.width)))
    ImageDraw.Draw(im).text((4, 4), p.replace("\\", "/").split("/")[-1], fill=(255, 255, 0))
    ims.append(im)
h = max(i.height for i in ims)
rows = (len(ims) + cols - 1) // cols
S = Image.new("RGB", (w * min(cols, len(ims)), h * rows))
for k, im in enumerate(ims):
    S.paste(im, ((k % cols) * w, (k // cols) * h))
S.save(args[0])
print("sheet", S.size)
