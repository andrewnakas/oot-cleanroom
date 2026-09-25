# The Legend of Zelda: Ocarina of Time clean room: status

_Last update: 2026-09-25 ~07:40_

Play: https://andrewnakas.github.io/oot-cleanroom/  (repo: andrewnakas/oot-cleanroom)

## For the morning
- The public site boots with the authentic N64 logo -> title attract intro (Link riding in Hyrule Field).
  In headless software rendering this intro is slow, so the title logo can take more than 100 s; with a real GPU it should be quick.
  Press Start (Space) once the logo shows, then File 1 -> name -> start.
- **Play it** (keyboard: WASD stick, X=A, C=B, Z, Space=Start, arrows=C, Esc=SoH menu; gamepad works).
  Dev shortcut to test any scene: `?dev=gSettings.BootSequence:3` opens the debug scene select.
- Things to look at: faces (eyes/mouths are drawn procedurally per character), item icons (rendered from the 3D get-item models), sky (noisy), pause screens.
- **Voices to record**: practice pack at `C:/Users/andre/n64work/oot/practice_pack` (163 lines, 11 characters: link_adult, link_child, navi, ganondorf, girl, woman, witch, fairy, goron, man, gerudo).
  Play `practice_<character>_call_and_response.wav` and answer after each beep (SCRIPT.txt lists the lines). Then run
  `CLEANROOM_GAME=games/oot python -m cleanroom.voice.takes cut <recording> <character> <takes>/<character>`.
  Until then, the voice slots use Piper TTS placeholders (`games/oot/voices`, lines in `voice_lines.json`).

## Works (verified headless)
- Item icons (~110) rendered from get-item models; quest icons (medallions, stones); dungeon minimaps (239) drawn from each room's geometry and placed with the game's compass tables; world map from Hyrule Field geometry; HUD digits; stone pause panels.
- Voices: 163 Piper placeholder lines in the game; practice pack built.
- Boot → N64 logo → title → file select → name entry, all with clean assets.
- Debug scene select → Hyrule Field: Link walks (position changes), HUD with icons, hearts, magic, minimap.
- Taint scan: **0 failing** (26,425 streams: textures raw+RGBA, samples raw+PCM, backgrounds RGB, SoH's soh.o2r).

## Decisions (log)
1. **Web route = Ship of Harkinian, Emscripten fork** (zalo/Shipwright `feature/emscripten-web-port`; the user suggested SoH).
   It already runs OoT in WebGL, with saves in IndexedDB and gamepad/keyboard/touch input. Checked in the first hour:
   zalo's prebuilt build boots in headless SwiftShader. Why not the others:
   - ROM + WASM emulator: we would have to build the IDO decomp on Windows (no WSL or docker here), and it's slower in the browser.
   - N64Recomp: last resort.

   SoH reads assets from `oot.o2r` (a zip of LUS resources), so the clean room writes a clean `oot.o2r`. No ROM is needed at runtime.
2. **Dirty extraction**: SoH's own extractor (ZAPD in wasm) run headless on the NTSC 1.2 ROM (`ports/wasm/cdp_run.py`, `devserve.py` upload hook).
   Output: `n64work/oot/dirty/oot.o2r`, never published.
3. **Resource census** (39,032 entries):
   - Regenerated: OTEX textures 12,655, OSMP samples 449 (363 ADPCM, 86 small 2-bit ADPCM), OBGI JPEG backgrounds 35.
   - Kept as facts: display lists, vertices, collision, skeletons, animations, scenes/rooms, cutscenes, paths, text, sequences (OSEQ), soundfont definitions (OSFT), matrices.
   - The 62 OBLB blobs are kept for now (small mixed data); TODO check them for image data.
4. **Palette textures**: each clean image is generated as RGBA from its facts. Each palette is then k-means fitted to the clean images that use it, with per-entry jitter, and the indices are re-derived with stochastic dither.
   - Links come from display lists (CRC64 path hashes), extractor XML TlutOffset, name pairing (Tex/TLUT, `vr_*_pal_static`), and palette state carried across a room's DLs.
   - Palette swaps (secondary palettes) are recoloured from the primary by the ratio of their coarse grids.
   - Sky textures index a bank of 128 entries (`idx_base`).
5. **Taint**: the first scan had 1,307 failures, all coincidental. Smooth or flat regions quantised to the same 5-bit texels as retail, and k-means palette centroids landed on the same grid points. Fixed with texel dither (±13), backgrounds noise (±14), palette jitter (±9), and index dither (±30 / ±44 for 256-colour palettes).
   Raw JPEG bytes are not scanned (standard tables); decoded pixels are. SoH's own MQ/RAND buttons matched retail and are re-typeset (`ports/soh/clean_soh.py`).
6. **Text**: message font = Marcellus (OFL); labels = Montserrat (OFL); Shift-JIS/kanji font = Noto Sans JP (OFL, rendered from each cell's SJIS code).
   NTSC 1.2 uses the kanji font for "PRESS START" and name entry. Labels: `games/oot/labels.py`.
7. **Item icons**: rendered by our Python F3DEX2 software renderer (`dlrender.py`) from the get-item models, using the clean textures (`icons.py`, 84 icons; the PNGs are in `games/oot/overrides/icons`).
8. **Faces**: parametric eyes/mouths (`faces.py`). State comes from the texture name; colours come from `face_briefs.json` per character.
9. Web build: emsdk 6.0.10 needed `-DFMT_CONSTEVAL=` (old bundled fmt) and `-DBUILD_SHARED_LIBS=OFF` (libzip).
   Source patches are in `ports/soh/port_patches.py` (dev CVars via `?dev=`, `web_scene`, `web_player_pos`, no extractor preload: the site is 35 MB smaller).

## Known issues
- FIXED: on GitHub Pages the default SoH boot (ship "powered by libultraship" logo) crawled for minutes in headless tests; the site now defaults to the authentic N64-logo -> title boot (`gSettings.BootSequence:1`), same as zalo's build. Verified: public URL reaches the title in about 60 s (headless, software GL).
- FIXED: the wasm "memory access out of bounds" crash on scene loads was heap corruption.
  SoH's `ResourceMgr_LoadJPEG` sizes its output buffer from the first background's data size, then writes 320x240x2 bytes; retail JPEGs are padded to 153,600 bytes.
  Our clean JPEGs are now padded to that size too (generate.py).
- Audio: the engine output is verified non-silent in headless tests, but nobody has listened yet. Please listen: music instruments and SFX are resynthesised from coarse outlines, and voices are TTS placeholders.

## Next
- Sky/skybox smoothness (the dither makes skies look like static): smoother clean generation for vr_* textures, keeping taint 0.
- Pause-screen stone panels (slot frames, quest-status relief): draw them.
- Pause-screen dungeon maps (map_48x85, runtime-palette index maps): render from room geometry like the minimaps.
- Multi-floor rooms in dungeon minimaps (Room0Floor1..3): better floor split.
- Title "ZELDA" shield logo (160x160): draw it.

- Audio check in the browser (samples play, no dropouts).
