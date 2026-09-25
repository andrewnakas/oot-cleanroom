"""Drawn textures for OoT: fonts, re-typeset labels, button glyphs, faces.

texture(path, d) -> RGBA float array (h, w, 4) or None (use the digest).
Text uses OFL fonts in games/oot/fonts (Marcellus for the message font,
Montserrat for labels, Noto Sans JP for the Shift-JIS font). Nothing here
reads retail pixels.
"""
import json
import os
import re
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from games.oot import labels
from cleanroom.decomp.gen import from_digest, unpack_alpha2

HERE = os.path.dirname(__file__)
SERIF = os.path.join(HERE, "fonts", "Marcellus-Regular.ttf")
SANS = os.path.join(HERE, "fonts", "Montserrat-VF.ttf")
JP = os.path.join(HERE, "fonts", "NotoSansJP-Regular.ttf")
SS = 4                                   # supersampling
_fonts = {}


def font(which, px):
    k = (which, px)
    if k not in _fonts:
        f = ImageFont.truetype({"serif": SERIF, "jp": JP}.get(which, SANS), px)
        if which in ("sans", "sansx"):
            try:
                f.set_variation_by_name("ExtraBold" if which == "sansx" else "Bold")
            except Exception:
                pass
        _fonts[k] = f
    return _fonts[k]


def _down(m, w, h):
    return m.reshape(h, SS, w, SS).mean((1, 3))


def text_mask(lines, w, h, which="sans", align="center", size=None, pad_x=1):
    """Coverage (h, w) of lines of text, auto-sized to fit, supersampled."""
    W, H = w * SS, h * SS
    n = len(lines)
    lh = H / n
    px = size * SS if size else int(lh * 0.95)
    while px > 4:
        f = font(which, px)
        widths = [f.getbbox(t)[2] - f.getbbox(t)[0] if t else 0 for t in lines]
        asc, desc = f.getmetrics()
        if max(widths) <= W - 2 * pad_x * SS and (asc * 0.8 + desc * 0.35) <= lh * 1.02:
            break
        px -= 1
    f = font(which, px)
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    cap = f.getbbox("H")
    ch = cap[3] - cap[1]
    for i, t in enumerate(lines):
        if not t:
            continue
        bb = f.getbbox(t)
        tw = bb[2] - bb[0]
        x = {"center": (W - tw) / 2, "left": pad_x * SS, "right": W - tw - pad_x * SS}[align] - bb[0]
        y = i * lh + (lh - ch) / 2 - cap[1]
        d.text((x, y), t, font=f, fill=255)
    return _down(np.asarray(img, np.float32) / 255.0, w, h)


def dilate(m, r=1):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx or dy:
                out = np.maximum(out, np.roll(np.roll(m, dy, 0), dx, 1) * (1.0 if abs(dx) + abs(dy) <= r else 0.7))
    return out


def outlined(m, fill=(255, 255, 255), edge=(10, 10, 10), r=1):
    h, w = m.shape
    o = dilate(m, r)
    img = np.zeros((h, w, 4), np.float32)
    img[..., :3] = np.asarray(edge, np.float32)
    img[..., :3] = img[..., :3] * (1 - m[..., None]) + np.asarray(fill, np.float32) * m[..., None]
    img[..., 3] = np.clip(np.maximum(o, m), 0, 1) * 255
    return img


def grey_img(cov):
    h, w = cov.shape
    img = np.zeros((h, w, 4), np.float32)
    img[..., :] = (np.clip(cov, 0, 1) * 255)[..., None]
    return img


# ------------------------------------------------------------ message font

def _font_char(code, name):
    if code == 0x5C:
        return "¥"
    if 0x20 <= code < 0x7F:
        return chr(code)
    m = re.match(r"(Latin(Small|Capital)Letter\w+)", name)
    if m:
        words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", m.group(1)).upper()
        try:
            return unicodedata.lookup(words)
        except KeyError:
            return None
    return None


def _disc(w, h, cx, cy, r):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    return np.clip(r + 0.5 - np.hypot(xx - cx, yy - cy), 0, 1)


def _tri(w, h, pts):
    img = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(img).polygon([(x * SS, y * SS) for x, y in pts], fill=255)
    return _down(np.asarray(img, np.float32) / 255, w, h)


def button_glyph(kind, w=16, h=16):
    """I4 button symbols: shape = 1, knocked-out letter/arrow = 0."""
    cx, cy = 7.5, 8.0
    if kind in ("A", "B", "C"):
        m = _disc(w, h, cx, cy, 6.6)
        t = text_mask([kind], w, h, "sansx", size=10)
        return np.clip(m - t, 0, 1)
    if kind in ("L", "R", "Z"):
        m = np.zeros((h, w), np.float32)
        m[2:14, 1:14] = 1
        t = text_mask([kind], w, h, "sansx", size=10)
        return np.clip(m - t, 0, 1)
    if kind.startswith("C"):
        m = _disc(w, h, cx, cy, 6.6)
        tri = {"CUp": [(7.5, 4), (11.5, 11), (3.5, 11)], "CDown": [(3.5, 5), (11.5, 5), (7.5, 12)],
               "CLeft": [(4, 8), (11, 4), (11, 12)], "CRight": [(4, 4), (4, 12), (11, 8)]}[kind]
        return np.clip(m - _tri(w, h, tri), 0, 1)
    if kind == "ZTarget":
        return _tri(w, h, [(3, 3), (12, 3), (7.5, 13)])
    if kind == "Stick":
        m = _disc(w, h, 7.5, 5.5, 4.2)
        m = np.maximum(m, _tri(w, h, [(6.5, 8), (8.5, 8), (9, 12), (6, 12)]))
        m = np.maximum(m, _tri(w, h, [(2, 12), (13, 12), (12, 15), (3, 15)]))
        return m
    return None


BUTTONS = {0x9F: "A", 0xA0: "B", 0xA1: "C", 0xA2: "L", 0xA3: "R", 0xA4: "Z", 0xA5: "CUp", 0xA6: "CDown",
           0xA7: "CLeft", 0xA8: "CRight", 0xA9: "ZTarget", 0xAA: "Stick"}


def glyph_mask(ch, w, h, cap_px=11, baseline=13, x0=1):
    """One message-font character, left aligned: cap height cap_px, baseline row."""
    f = font("serif", int(cap_px * SS / 0.70))
    img = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(img)
    bb = f.getbbox(ch)
    capb = f.getbbox("H")
    base_y = baseline * SS - capb[3]
    dr.text((x0 * SS - bb[0], base_y), ch, font=f, fill=255, stroke_width=1, stroke_fill=255)
    return np.clip(_down(np.asarray(img, np.float32) / 255, w, h) * 1.15, 0, 1)


def font_glyph(path, d):
    m = re.search(r"gMsgChar([0-9A-F]{2})(\w*)Tex", path)
    if not m:
        return None
    code, name = int(m.group(1), 16), m.group(2)
    w, h = d["w"], d["h"]
    if code in BUTTONS:
        cov = button_glyph(BUTTONS[code], w, h)
    else:
        ch = _font_char(code, name)
        cov = np.zeros((h, w), np.float32) if (ch is None or ch.strip() == "") else glyph_mask(ch, w, h)
    return grey_img(cov)


def kanji_glyph(path, d):
    """Shift-JIS font cell (16x16 I4): the character from the name's code."""
    m = re.search(r"gMsgKanji([0-9A-F]{4})", path)
    if not m:
        return None
    try:
        ch = bytes.fromhex(m.group(1)).decode("shift_jis")
    except UnicodeDecodeError:
        ch = ""
    w, h = d["w"], d["h"]
    cov = np.zeros((h, w), np.float32)
    if ch.strip() and ch != "　":
        f = font("jp", 15 * SS)
        img = Image.new("L", (w * SS, h * SS), 0)
        dr = ImageDraw.Draw(img)
        bb = f.getbbox("漢")                       # a full-height ideograph fixes the frame
        cb = f.getbbox(ch)
        cw = cb[2] - cb[0]
        x = (w * SS - cw) / 2 - cb[0]
        y = (h * SS - (bb[3] - bb[1])) / 2 - bb[1]
        dr.text((x, y), ch, font=f, fill=255, stroke_width=2, stroke_fill=255)
        cov = np.clip(_down(np.asarray(img, np.float32) / 255, w, h) * 1.1, 0, 1)
    return grey_img(cov)


# ------------------------------------------------------------ labels

def label_tex(path, d, lines):
    w, h = d["w"], d["h"]
    base = path.rsplit("/", 1)[1]
    align = "left" if ("FileSel" in base and "Button" not in base and len(lines[0]) > 8) else "center"
    if "TitleCard" in base and len(lines) == 2:          # boss: small subtitle, big name
        top = text_mask([lines[0]], w, h // 3, "sans")
        bot = text_mask([lines[1]], w, h - h // 3, "sansx")
        m = np.concatenate([top, bot], 0)
    else:
        m = text_mask(lines, w, h, "sansx" if h >= 16 else "sans", align=align)
    if "Button" in base and d["type"] == 9:              # file select buttons: grey bevel, dark text
        img = np.zeros((h, w, 4), np.float32)
        g = np.linspace(200, 120, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
        img[..., :3] = g[..., None]
        img[..., :3] *= (1 - 0.85 * m[..., None])
        img[..., 3] = 255
        img[0, :, :3] = 240
        img[-1, :, :3] = 60
        img[:, 0, :3] = 230
        img[:, -1, :3] = 70
        if "alpha2" in d:
            img[..., 3] = unpack_alpha2(d["alpha2"], w, h)
        return img
    return outlined(m, r=1)


# ------------------------------------------------------------ pause page headers

_SPEC = None


def spec():
    global _SPEC
    if _SPEC is None:
        _SPEC = json.load(open(os.path.join(HERE, "spec", "textures.json")))
    return _SPEC


PAUSE_TITLES = {"SelectItem": "SELECT ITEM", "QuestStatus": "QUEST STATUS", "Equipment": "EQUIPMENT",
                "Map": "MAP", "Save": "SAVE", "GameOver": "GAME OVER"}


def _find(page, col, row):
    T = spec()
    for p in (f"textures/icon_item_nes_static/gPause{page}{col}{row}ENGTex",
              f"textures/icon_item_static/gPause{page}{col}{row}Tex"):
        if p in T:
            return p
    return None


def pause_header(path, d):
    m = re.search(r"gPause(SelectItem|QuestStatus|Equipment|Map|Save|GameOver)(\d)(\d)(ENG)?Tex$", path)
    if not m or m.group(3) != "0" or not m.group(4):
        return None
    page, col = m.group(1), int(m.group(2))
    T = spec()
    cols = [c for c in range(3) if _find(page, c, 0)] if page in ("SelectItem", "QuestStatus") else [col]
    w, h = d["w"], d["h"]
    strip = np.concatenate([from_digest(_find(page, c, 0), T[_find(page, c, 0)]).astype(np.float32) for c in cols], 1)
    W = strip.shape[1]
    tm = np.roll(text_mask([PAUSE_TITLES[page]], W, h, "sansx", size=15), -3, 0)
    hi = np.roll(np.roll(tm, 1, 0), 1, 1)
    rgb = strip[..., :3]
    rgb = rgb * (1 - 0.6 * hi[..., None]) + 235 * 0.6 * hi[..., None]
    rgb = rgb * (1 - tm[..., None]) + np.asarray([45, 38, 30], np.float32) * tm[..., None]
    strip[..., :3] = rgb
    k = cols.index(col)
    return strip[:, k * w:(k + 1) * w]


# ------------------------------------------------------------ dispatch

def texture(path, d):
    if "/kanji/" in path:
        return kanji_glyph(path, d)
    if "/nes_font_static/" in path:
        return font_glyph(path, d)
    if path.endswith("nintendo_rogo_static_Tex_000000"):       # the wordmark under the N64 logo
        return grey_img(text_mask(["Nintendo"], d["w"], d["h"], "sansx", size=26))
    if "gPause" in path and re.search(r"gPause(SelectItem|QuestStatus|Equipment|Map|Save|GameOver)\d\d", path):
        img = pause_header(path, d)
        if img is not None:
            return img
    lines = labels.label(path)
    if lines:
        return label_tex(path, d, lines)
    try:
        from games.oot import faces
        img = faces.texture(path, d)
        if img is not None:
            return img
    except FileNotFoundError:
        pass
    return None
