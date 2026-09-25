"""Write games/oot/voice_lines.json (placeholder TTS lines for voice samples)
and add playback rates (32 kHz x soundfont tuning) to spec/samples.json.

    python -m games.oot.make_voice_lines

Words come from the sample names (the community's labels): yells become
short interjections. Our own performances; no original audio.
"""
import json
import os
import re

HERE = os.path.dirname(__file__)

CHARS = {
    "link_adult": {"tts": {"model": "en_US-ryan-high", "semitones": 1.0, "length": 0.9}},
    "link_child": {"tts": {"model": "en_US-amy-medium", "semitones": 3.0, "length": 0.9}},
    "navi": {"tts": {"model": "en_US-kristin-medium", "semitones": 6.0, "length": 0.8}},
    "ganondorf": {"tts": {"model": "en_US-joe-medium", "semitones": -4.0, "length": 1.1}},
    "girl": {"tts": {"model": "en_US-amy-medium", "semitones": 2.0, "length": 0.9}},
    "woman": {"tts": {"model": "en_US-kristin-medium", "semitones": 0.0, "length": 0.9}},
    "witch": {"tts": {"model": "en_US-hfc_female-medium", "semitones": 3.0, "length": 0.9}},
    "fairy": {"tts": {"model": "en_US-hfc_female-medium", "semitones": 1.0, "length": 1.0}},
    "goron": {"tts": {"model": "en_US-joe-medium", "semitones": -3.0, "length": 1.0}},
    "man": {"tts": {"model": "en_US-joe-medium", "semitones": 0.0, "length": 0.9}},
    "gerudo": {"tts": {"model": "en_US-hfc_female-medium", "semitones": -1.0, "length": 0.9}},
}

WHO = [("Adult Link", "link_adult"), ("Child Link", "link_child"), ("Navi", "navi"), ("Ganondorf", "ganondorf"),
       ("Girl", "girl"), ("Woman", "woman"), ("Witch", "witch"), ("Twinrova", "witch"), ("Great Fairy", "fairy"),
       ("Goron", "goron"), ("Ingo", "man"), ("Talon", "man"), ("Gerudo", "gerudo")]

# action words in the name -> what our actor says
SAY = [(r"Strong Attack", "Hyaaah!"), (r"Attack", "Hyah!"), (r"Cast", "Hah!"), (r"Hup", "Hup!"), (r"Climb", "Hnn!"),
       (r"Hurt|Knocked|Painful|Strangled|Choking", "Ugh!"), (r"Falling", "Waaah!"), (r"Dangling|Grunt|Lift|Effort", "Nngh!"),
       (r"Gasp|Startled|Surprised|Discombobulated", "Hah!"), (r"Pant|Wheeze|Panting", "Hah, hah."), (r"Sigh", "Haah."),
       (r"Glug|Gulp", "Glug."), (r"Sneez", "Achoo!"), (r"Spur", "Hyah!"), (r"Yawn|Stretch|Refreshed|Awakening", "Ahh."),
       (r"Moan|Shivers", "Ohh."), (r"Dying", "Ahh..."), (r"Laugh|Chuckles|Cackles|Titters|Delighted", "Ha ha ha!"),
       (r"Scream|Yowls|Yells|Howls", "Aaah!"), (r"Inquir|Inquires", "Hmm?"), (r"Disappointed", "Aww."),
       (r"Scared|Fearful|Distressed", "Eek!"), (r"Snoring", "Zzz."), (r"Recognizes", "Oh!"), (r"Oh", "Oh!"),
       (r"Exclaims", "Hey!"), (r"Hyah", "Hyah!"), (r"Hyeaaaaugh", "Hyeaaah!"), (r"Rebuffs|Defiance|Curse", "Grr!"),
       (r"Vomits|Gurgling|Breath", "Hrrgh."), (r"Recovers|Breathes", "Hmm."), (r"Arguing", "Hmph!"),
       (r"Vanquished", "Aaagh."), (r"Unsettled", "Hmm..."), (r"Sweat", "Phew."), (r"Heat", "Hhh...")]

NAVI = {"Navi - Hello!": "Hello!", "Navi - Hey!": "Hey!", "Navi - Listen!": "Listen!", "Navi - Look!": "Look!",
        "Navi - Watch Out!": "Watch out!"}


def main():
    spec = os.path.join(HERE, "spec")
    S = json.load(open(os.path.join(spec, "samples.json")))
    tun = json.load(open(os.path.join(spec, "tunings.json")))
    for p, d in S.items():
        t = max(tun.get(p, [1.0]))
        d["rate"] = 32000.0 * t
    json.dump(S, open(os.path.join(spec, "samples.json"), "w"), separators=(",", ":"))
    out = {"_doc": "Placeholder TTS lines for voice sample slots (words from the sample names). "
                   "who -> _characters[who].tts (Piper model, pitch lift, speed).", "_characters": CHARS}
    for p in S:
        name = p.rsplit("/", 1)[1][:-5]
        who = next((w for k, w in WHO if name.startswith(k)), None)
        if not who:
            continue
        if name in NAVI:
            text = NAVI[name]
        else:
            text = next((say for rx, say in SAY if re.search(rx, name)), None)
        if text:
            out[p] = {"who": who, "text": text}
    json.dump(out, open(os.path.join(HERE, "voice_lines.json"), "w"), indent=1)
    n = len([k for k in out if not k.startswith("_")])
    print(f"voice lines: {n}; rates added to {len(S)} samples")


if __name__ == "__main__":
    main()
