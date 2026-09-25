"""Ship of Harkinian / libultraship .o2r archives (zip of binary resources).

Every resource starts with a 0x40-byte header: endianness u8 (0 = little),
3 pad, type u32 (FourCC read little-endian, e.g. 'OTEX'), version u32,
id u64, resource version u32, rom crc u64, rom enum u32, then payload.

Payloads used here (all little-endian unless noted):
  OTEX texture   type u32, width u32, height u32, size u32, N64 texels (big-endian, linear)
  OSMP sample    codec u8, medium u8, bit26 u8, bit25 u8, size u32, data,
                 loop start/end/count u32, nstates u32, states s16[], order u32,
                 npred u32, nbook u32, book s16[]
  OBGI background  size u32, JPEG bytes
  ODLT display list  ucode u32, pad to 8, Gfx (w0 u32, w1 u32)...
Display lists reference textures by CRC64 of the resource path
(G_SETTIMG_OTR_HASH = 0x20, next Gfx word pair = hash hi, lo).
"""
import struct
import zipfile

HDR = 0x40
# libultraship Fast::TextureType
TEX_TYPES = {1: ("rgba", 32), 2: ("rgba", 16), 3: ("ci", 4), 4: ("ci", 8),   # palette4/8
             5: ("i", 4), 6: ("i", 8), 7: ("ia", 4), 8: ("ia", 8), 9: ("ia", 16), 10: ("ia", 1)}

_POLY = 0x42F0E1EBA9EA3693
_TABLE = []
for _i in range(256):
    _c = _i << 56
    for _ in range(8):
        _c = ((_c << 1) ^ _POLY) if _c & (1 << 63) else (_c << 1)
    _TABLE.append(_c & 0xFFFFFFFFFFFFFFFF)


def crc64(s: str) -> int:
    """libultraship CRC64() of a resource path (no final xor)."""
    crc = 0xFFFFFFFFFFFFFFFF
    for b in s.encode():
        crc = _TABLE[((crc >> 56) ^ b) & 0xFF] ^ ((crc << 8) & 0xFFFFFFFFFFFFFFFF)
    return crc


def rtype(data: bytes):
    if len(data) < HDR:
        return None
    return struct.unpack("<I", data[4:8])[0].to_bytes(4, "big").decode("latin1")


def read_all(path):
    """{name: bytes} in archive order."""
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}


def write_all(path, files, compress=True):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED, compresslevel=6) as z:
        for name, data in files.items():
            z.writestr(name, data)


# ---------------------------------------------------------------- textures

def tex_parse(data):
    t, w, h, n = struct.unpack("<4I", data[HDR:HDR + 16])
    return {"type": t, "w": w, "h": h, "size": n, "data": data[HDR + 16:HDR + 16 + n]}


def tex_replace(data, texels: bytes):
    t, w, h, n = struct.unpack("<4I", data[HDR:HDR + 16])
    assert len(texels) == n, (len(texels), n)
    return data[:HDR + 16] + texels + data[HDR + 16 + n:]


# ---------------------------------------------------------------- samples

def smp_parse(data):
    p = HDR
    codec, medium, b26, b25 = data[p:p + 4]
    n = struct.unpack("<I", data[p + 4:p + 8])[0]
    raw = data[p + 8:p + 8 + n]
    p += 8 + n
    ls, le, lc, ns = struct.unpack("<IIiI", data[p:p + 16])
    p += 16
    states = list(struct.unpack(f"<{ns}h", data[p:p + 2 * ns]))
    p += 2 * ns
    order, npred, nb = struct.unpack("<3I", data[p:p + 12])
    p += 12
    book = list(struct.unpack(f"<{nb}h", data[p:p + 2 * nb]))
    return {"codec": codec, "medium": medium, "b26": b26, "b25": b25, "data": raw,
            "loop": [ls, le, lc], "states": states, "order": order, "npred": npred, "book": book,
            "tail": data[p + 2 * nb:]}


def smp_build(header: bytes, s):
    out = bytearray(header[:HDR])
    out += bytes([s["codec"], s["medium"], s["b26"], s["b25"]])
    out += struct.pack("<I", len(s["data"])) + s["data"]
    out += struct.pack("<IIiI", s["loop"][0], s["loop"][1], s["loop"][2], len(s["states"]))
    out += struct.pack(f"<{len(s['states'])}h", *s["states"])
    out += struct.pack("<3I", s["order"], s["npred"], len(s["book"]))
    out += struct.pack(f"<{len(s['book'])}h", *s["book"])
    out += s.get("tail", b"")
    return bytes(out)


# ---------------------------------------------------------------- backgrounds

def bg_parse(data):
    n = struct.unpack("<I", data[HDR:HDR + 4])[0]
    return data[HDR + 4:HDR + 4 + n]


def bg_build(header: bytes, jpeg: bytes):
    return header[:HDR] + struct.pack("<I", len(jpeg)) + jpeg


# ---------------------------------------------------------------- display lists

def dl_texture_uses(data):
    """Walk one display list; yield (texture_hash, tlut_hash_or_None) for each
    texture image load, and ('TLUT', hash) markers are folded in."""
    p = HDR + 4
    while p % 8:
        p += 1
    n = len(data)
    last_img = None
    tlut = None
    uses = []
    calls = []
    while p + 8 <= n:
        w0, w1 = struct.unpack("<II", data[p:p + 8])
        op = w0 >> 24
        if op == 0x20:                         # G_SETTIMG_OTR_HASH
            hi, lo = struct.unpack("<II", data[p + 8:p + 16])
            last_img = (hi << 32) | lo
            p += 16
            continue
        if op == 0x31:                         # G_DL_OTR_HASH
            hi, lo = struct.unpack("<II", data[p + 8:p + 16])
            calls.append((hi << 32) | lo)
            p += 16
            continue
        if op in (0x32, 0x33, 0x35, 0x36):     # VTX_OTR_HASH, MARKER, BRANCH_Z_OTR, MTX_OTR: 2 Gfx
            p += 16
            continue
        if op == 0xF0 and last_img is not None:    # G_LOADTLUT
            tlut = last_img
        elif op in (0xF3, 0xF4) and last_img is not None:   # LOADBLOCK / LOADTILE
            uses.append((last_img, tlut))
        elif op == 0xDF:                       # G_ENDDL
            break
        p += 8
    return uses, calls
