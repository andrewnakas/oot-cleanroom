# The Legend of Zelda: Ocarina of Time — clean room web build

Play: **https://andrewnakas.github.io/oot-cleanroom/**

Ocarina of Time running in the browser (the [Ship of Harkinian](https://github.com/HarbourMasters/Shipwright)
engine, [zalo's Emscripten/WebGL fork](https://github.com/zalo/Shipwright)), with **every asset the ROM
extraction would produce regenerated**: textures, fonts, icons, pictures, instrument and sound-effect
samples, prerendered backgrounds. No ROM is needed to play.

Controls: `W A S D` stick · `X` A · `C` B · `Z` Z · `Space` Start · arrow keys C buttons · `T F G H` D-pad ·
`Esc` SoH menu · gamepads work. Saves stay in the browser.

## What is kept, what is generated

The game reads its data from `oot.o2r`, the archive SoH normally extracts from your ROM. This project
extracts it **once, in a dirty room** (`games/oot/extract_spec.py`), keeps only coarse facts, and
builds a new archive from those facts (`games/oot/generate.py`):

| Asset (count) | Kept fact | Generated |
|---|---|---|
| Textures (12,655) | format, size, a 4×4 colour grid (16×16 for ≥128 px and skies), a 2-bit alpha outline, palette links | colour from the grid, our noise detail and dither; palettes are fitted to the clean images (k-means) and re-indexed |
| Message font (139), Shift-JIS font (3,974) | the character (from the decomp's names / Shift-JIS code) | typeset with OFL fonts (Marcellus, Noto Sans JP); button glyphs drawn |
| Text in textures: item/area/place names, action labels, file select, pause headers (~400) | the words (from the decomp's names and the game's text) | re-typeset (`labels.py`, `drawn.py`, Montserrat) |
| Eyes and mouths (≈300) | alpha outline, state from the name (open/half/closed/looking/shocked…) | painted from our own colour briefs (`face_briefs.json`, `faces.py`) |
| Item icons (84) | — | rendered from the game's own get-item 3D models with our textures (`dlrender.py`, `icons.py`) |
| Prerendered backgrounds (35 JPEG) | size, 16×16 colour grid | colour from the grid plus noise |
| Samples (449; ADPCM and 2-bit ADPCM) | length, loop points, codec, a coarse spectral outline, median pitch | resynthesised; our own 2-predictor VADPCM codebooks |
| Geometry, collision, animation, scenes, text, note sequences, soundfont definitions | kept (user scope) | — |

`games/oot/taint_report.py` scans every regenerated texture (raw and decoded RGBA), sample (raw and PCM)
and background (decoded RGB) against the retail extraction, plus SoH's own `soh.o2r`, for shared byte runs
of 32 bytes or more: **0 failing**.

## Build (Windows, Git Bash)

```sh
# engine: zalo/Shipwright feature/emscripten-web-port (+ submodules), emsdk
python -m ports.soh.port_patches sohweb          # dev hooks, no extractor preload
emcmake cmake -B build-web -S sohweb -G Ninja -DCMAKE_BUILD_TYPE=Release -DUSE_OPENGLES=ON \
   -DBUILD_SHARED_LIBS=OFF "-DCMAKE_CXX_FLAGS=-DFMT_CONSTEVAL=" ... && cmake --build build-web --target soh

# dirty room, once: extract oot.o2r from your own ROM (SoH's extractor), never published
python -m games.oot.extract_spec dirty/oot.o2r sohweb/soh/assets/xml/N64_NTSC_12 games/oot/spec spec_local

# clean room
python -m games.oot.generate games/oot/spec spec_local/kept.o2r clean/oot.o2r
python -m games.oot.icons clean/oot.o2r games/oot/overrides/icons     # then generate again (--only tex --base)
python -m ports.soh.clean_soh sohweb/soh/soh/web/soh.o2r clean/soh.o2r
python -m games.oot.taint_report dirty/oot.o2r clean/oot.o2r clean/soh.o2r
python ports/soh/make_site.py build-web/soh clean/soh.o2r clean/oot.o2r site
```

`spec_local/kept.o2r` holds the kept facts (geometry, text, sequences…) with every texel, sample and
JPEG blanked; it is made from your ROM and not in this repository.

## Legal note

This repository contains no ROM data other than the coarse facts in `games/oot/spec`. All textures, fonts,
icons, pictures and samples are generated. The engine is Ship of Harkinian (built on the zeldaret/oot
decompilation). The Legend of Zelda is a trademark of Nintendo; this project is not affiliated with Nintendo.
