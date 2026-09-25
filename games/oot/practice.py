"""Voice practice pack for OoT (PERSONAL USE: built from the user's own ROM
extraction; written outside the repo, never published).

Same layout as cleanroom.voice.practice (so cleanroom.voice.takes can cut the
recordings), but the reference clips are decoded from the dirty oot.o2r.

    python -m games.oot.practice <dirty oot.o2r> <out dir>
"""
import json
import os
import sys
import wave

import numpy as np

from cleanroom.audio import vadpcm
from games.oot import o2r

HERE = os.path.dirname(__file__)
HZ = 22050


def main(argv):
    src, out = argv[1], argv[2]
    S = json.load(open(os.path.join(HERE, "spec", "samples.json")))
    L = [(k, v) for k, v in json.load(open(os.path.join(HERE, "voice_lines.json"))).items()
         if not k.startswith("_") and v.get("kind", "speech") == "speech"]
    files = o2r.read_all(src)
    os.makedirs(os.path.join(out, "clips"), exist_ok=True)

    def load(p):
        s = o2r.smp_parse(files[p])
        bits = 4 if s["codec"] == 0 else 2
        x = vadpcm.decode(s["data"], {"order": s["order"], "npred": s["npred"], "book": s["book"]}, bits=bits)
        x = x[:S[p]["nframes"]].astype(np.float32) / 32768
        sr = S[p]["rate"]
        return np.interp(np.arange(0, len(x) * HZ / sr) * sr / HZ, np.arange(len(x)), x).astype(np.float32)

    def wr(path, x):
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(HZ)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())

    beep = (0.2 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * HZ)) / HZ)).astype(np.float32)
    tracks = {}
    lines = ["Voice practice script: record in this order, 2-3 takes each, in character.",
             "Play practice_<character>_call_and_response.wav and speak after each beep.", ""]
    for i, (p, v) in enumerate(L, 1):
        name = os.path.basename(p)[:-5]
        x = load(p)
        wr(os.path.join(out, "clips", f"{i:03d}_{name.replace('!', '').replace('?', '')}.wav"), x)
        gap = np.zeros(int((len(x) / HZ * 1.5 + 1.5) * HZ), np.float32)
        tracks.setdefault(v["who"], []).extend([x, np.zeros(int(0.3 * HZ), np.float32), beep, gap])
        lines.append(f"{i:03d}  {v['who']:11s} {name:42s} max {S[p]['nframes'] / S[p]['rate']:.1f}s  \"{v.get('text', '')}\"")
    for who, parts in tracks.items():
        wr(os.path.join(out, f"practice_{who}_call_and_response.wav"), np.concatenate(parts))
    lines += ["", "Record each character's track in one take (phone or mic, quiet room), save as",
              "  <character>.m4a/.wav, then:  CLEANROOM_GAME=games/oot python -m cleanroom.voice.takes cut <file> <character> <takes dir>/<character>",
              "These clips come from your own ROM: practice only, do not share or commit them."]
    open(os.path.join(out, "SCRIPT.txt"), "w", encoding="utf8").write("\n".join(lines))
    print(f"practice pack: {len(L)} clips, tracks {sorted(tracks)} -> {out}")


if __name__ == "__main__":
    main(sys.argv)
