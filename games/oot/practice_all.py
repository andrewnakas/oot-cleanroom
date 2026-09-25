"""One call-and-response track with every character (for recording in one go).

    python -m games.oot.practice_all "<practice pack dir>"

Joins the per-character practice tracks (games.oot.practice) with a chime and
a spoken "Next: <character>" before each, and writes ALL_characters_layout.json
with each section's start time, so a single recording can be split per
character later (games.oot.split_all).
"""
import json
import os
import sys
import wave

import numpy as np

HZ = 22050
ORDER = ["navi", "link_child", "link_adult", "girl", "woman", "fairy", "witch", "gerudo", "goron", "man", "ganondorf"]
LABEL = {"navi": "Navi", "link_child": "Young Link", "link_adult": "Adult Link", "girl": "Girl", "woman": "Woman",
         "fairy": "Great Fairy", "witch": "Witches, Koume and Kotake", "gerudo": "Gerudo", "goron": "Goron",
         "man": "Ingo and Talon", "ganondorf": "Ganondorf"}
_V = None


def rd(p):
    with wave.open(p) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


def speak(text):
    global _V
    from piper import PiperVoice, SynthesisConfig
    if _V is None:
        _V = PiperVoice.load(os.path.join(os.environ.get("PIPER_VOICES", "C:/Users/andre/n64work/piper_voices"),
                                          "en_US-ryan-high.onnx"))
    x = np.concatenate([c.audio_float_array for c in _V.synthesize(text, syn_config=SynthesisConfig(length_scale=1.0))])
    sr = _V.config.sample_rate
    return np.interp(np.arange(0, len(x) * HZ / sr) * sr / HZ, np.arange(len(x)), x).astype(np.float32) * 0.8


def chime():
    t = np.arange(int(0.25 * HZ)) / HZ
    return np.concatenate([0.25 * np.sin(2 * np.pi * f * t) * np.exp(-6 * t) for f in (523, 659, 784)]).astype(np.float32)


def silence(s):
    return np.zeros(int(s * HZ), np.float32)


def main(argv):
    d = argv[1]
    parts, layout = [speak("Ocarina of Time voice practice. After each beep, repeat the line in character. Here we go."),
                     silence(1.5)], []
    for who in ORDER:
        parts += [chime(), silence(0.3), speak("Next: " + LABEL[who] + "."), silence(2.0)]
        start = sum(len(p) for p in parts) / HZ
        tr = rd(os.path.join(d, f"practice_{who}_call_and_response.wav"))
        parts += [tr, silence(1.5)]
        layout.append({"character": who, "start_s": round(start, 3), "length_s": round(len(tr) / HZ, 3)})
    parts += [chime(), speak("That's everything. Thank you!")]
    x = np.concatenate(parts)
    with wave.open(os.path.join(d, "ALL_characters_call_and_response.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(HZ)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    json.dump({"rate": HZ, "sections": layout}, open(os.path.join(d, "ALL_characters_layout.json"), "w"), indent=1)
    print(f"{len(x) / HZ / 60:.1f} min;", ", ".join(f"{s['character']}@{s['start_s'] / 60:.1f}m" for s in layout))


if __name__ == "__main__":
    main(sys.argv)
