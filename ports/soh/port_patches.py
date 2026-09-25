"""Source changes to the SoH Emscripten fork (zalo/Shipwright feature/emscripten-web-port).

    python -m ports.soh.port_patches <sohweb checkout>

Idempotent text patches. Build flags (see STATUS.md) are passed by the build
script: -DFMT_CONSTEVAL= (old bundled fmt vs new clang), -DBUILD_SHARED_LIBS=OFF.
"""
import os
import sys

PATCHES = [
    # 1. dev hooks: CVars from ?dev=name:value,... (applied when SoH applies its web config),
    #    current scene and player position for headless tests.
    ("soh/soh/web/web_main.cpp",
     "// Called from OTRGlobals.cpp after the CVar system is ready\nvoid web_apply_anchor_config() {\n    if (!web_has_anchor_config()) return;",
     """EM_JS(const char*, web_dev_cvars_get, (), {
    var s = (typeof window._devCvars === 'string') ? window._devCvars : '';
    var len = lengthBytesUTF8(s) + 1;
    var ptr = _malloc(len);
    stringToUTF8(s, ptr, len);
    return ptr;
});

static void web_apply_dev_cvars() {
    char* s = (char*)web_dev_cvars_get();
    char* save = NULL;
    for (char* tok = strtok_r(s, ",", &save); tok; tok = strtok_r(NULL, ",", &save)) {
        char* colon = strrchr(tok, ':');
        if (!colon) continue;
        *colon = 0;
        CVarSetInteger(tok, atoi(colon + 1));
        printf("[Web] dev cvar %s = %d\\n", tok, atoi(colon + 1));
    }
    free(s);
}

extern "C" PlayState* gPlayState;
static float s_web_pos[4];

extern "C" EMSCRIPTEN_KEEPALIVE int web_console(const char* cmd) {
    std::string out;
    return Ship::Context::GetInstance()->GetConsole()->Run(std::string(cmd), &out);
}

extern "C" EMSCRIPTEN_KEEPALIVE int web_scene(void) {
    return gPlayState ? gPlayState->sceneNum : -1;
}

extern "C" EMSCRIPTEN_KEEPALIVE float* web_player_pos(void) {
    if (gPlayState && GET_PLAYER(gPlayState)) {
        Player* p = GET_PLAYER(gPlayState);
        s_web_pos[0] = p->actor.world.pos.x;
        s_web_pos[1] = p->actor.world.pos.y;
        s_web_pos[2] = p->actor.world.pos.z;
        s_web_pos[3] = 1;
    } else {
        s_web_pos[3] = 0;
    }
    return s_web_pos;
}

// Called from OTRGlobals.cpp after the CVar system is ready
void web_apply_anchor_config() {
    web_apply_dev_cvars();
    if (!web_has_anchor_config()) return;"""),
    ("soh/CMakeLists.txt",
     "_web_wants_text_input,_malloc,_free",
     "_web_wants_text_input,_web_scene,_web_player_pos,_web_console,_malloc,_free"),
    # 2. the site ships a clean oot.o2r: no in-browser ROM extraction, no 35 MB extractor data
    ("soh/CMakeLists.txt",
     "                --preload-file=${CMAKE_CURRENT_SOURCE_DIR}/assets/xml@assets/xml\n"
     "                --preload-file=${CMAKE_CURRENT_SOURCE_DIR}/assets/extractor@assets\n", ""),
]


NL = chr(10)
INCLUDES = ("soh/soh/web/web_main.cpp", '#include "soh/Extractor/Extract.h"' + NL,
            NL.join(['#include "soh/Extractor/Extract.h"', 'extern "C" {', '#include "z64.h"',
                     '#include "functions.h"', '#include "macros.h"', '}', '']))


def main(argv):
    root = argv[1]
    done = 0
    for rel, old, new in PATCHES + [INCLUDES]:
        p = os.path.join(root, rel)
        s = open(p, encoding="utf-8").read()
        if (new and new in s) or (not new and old not in s):
            continue                            # already applied
        if old not in s:
            print("MISSING", rel, old[:60].replace(NL, " "))
            continue
        s = s.replace(old, new, 1)
        open(p, "w", encoding="utf-8", newline=NL).write(s)
        done += 1
    print(f"patches applied: {done}")


if __name__ == "__main__":
    main(sys.argv)
