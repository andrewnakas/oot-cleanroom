# The Legend of Zelda: Ocarina of Time clean room: status

_Last update: 2026-09-25 night 1_

## For the morning
- (in progress) nothing to record yet; the voice practice pack will be listed here.

## Decisions (log)
1. **Web route = Ship of Harkinian, Emscripten fork** (zalo/Shipwright `feature/emscripten-web-port`, the user suggested SoH).
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
4. **Palette textures**: each clean image is generated as RGBA from its facts. Each palette is then k-means fitted to the clean images that use it, and the indices are re-derived.
   - Links come from display lists (CRC64 path hashes), extractor XML TlutOffset, name pairing (Tex/TLUT, `vr_*_pal_static`), and palette state carried across a room's DLs.
   - Palette swaps (secondary palettes) are recoloured from the primary by the ratio of their coarse grids.
   - Sky textures index a bank of 128 entries (`idx_base`).
5. **Spec** (`games/oot/spec`, committed): facts only (grid, 2-bit alpha, sizes, sample outlines).
   `kept.o2r` (geometry etc. with every texel/sample/JPEG blanked) stays local in `n64work/oot/spec_local`.
6. Web build: emsdk 6.0.10 needed `-DFMT_CONSTEVAL=` (old bundled fmt) and `-DBUILD_SHARED_LIBS=OFF` (libzip). See `n64work/oot/webbuild.sh`.

## Works
- Dirty extraction, spec, and generation of all textures. The clean-texture archive boots to the title screen in zalo's build.

## Next
- Fonts (nes_font_static / message_static glyphs), title logo, "PRESS START", ©, file select, pause-menu item/map names: re-typeset.
- Faces (Link and NPC eyes/mouths): facepaint briefs.
- Pause dungeon maps (runtime palette, index maps): render from collision.
- soh.o2r (SoH's own assets): taint-check it against the dirty archive.
- Taint scan, own web build, site, publish.
