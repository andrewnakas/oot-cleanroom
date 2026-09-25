"""Split one recording made against ALL_characters_call_and_response.wav into
per-character recordings, for cleanroom.voice.takes.

    python -m games.oot.split_all <recording> <ALL_characters_layout.json> <out dir> [--offset seconds]

--offset: how many seconds into the recording the practice track started
playing (default 0: recording and playback started together). Each piece
keeps 2 s of margin on both sides; takes.py does the fine alignment.
"""
import json
import os
import sys
import wave

import numpy as np

from cleanroom.voice.takes import load_audio


def main(argv):
    rec, layout, out = argv[1:4]
    off = float(argv[argv.index("--offset") + 1]) if "--offset" in argv else 0.0
    x, sr = load_audio(rec)
    L = json.load(open(layout))
    os.makedirs(out, exist_ok=True)
    for s in L["sections"]:
        a = max(0, int((off + s["start_s"] - 2.0) * sr))
        b = min(len(x), int((off + s["start_s"] + s["length_s"] + 2.0) * sr))
        piece = np.concatenate([np.zeros(max(0, int((2.0 - off - s["start_s"]) * sr)), np.float32), x[a:b]])
        with wave.open(os.path.join(out, s["character"] + ".wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(piece, -1, 1) * 32767).astype("<i2").tobytes())
        print(f"{s['character']:11s} {len(piece) / sr / 60:.1f} min")


if __name__ == "__main__":
    main(sys.argv)
