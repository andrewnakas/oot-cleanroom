"""Assemble the web site from the SoH web build + clean archives.

    python ports/soh/make_site.py <soh build dir (build-web/soh)> <soh.o2r> <clean oot.o2r> <site dir>

The page loads soh.o2r and oot.o2r from the site itself (no ROM, no upload),
through the shell's own #soh=/#oot= URL loader.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    build, soh_o2r, oot_o2r, site = argv[1:5]
    os.makedirs(site, exist_ok=True)
    for f in ("soh.js", "soh.wasm", "soh.data"):
        if os.path.exists(os.path.join(build, f)):
            shutil.copyfile(os.path.join(build, f), os.path.join(site, f))
    shutil.copyfile(soh_o2r, os.path.join(site, "soh.o2r"))
    shutil.copyfile(oot_o2r, os.path.join(site, "oot.o2r"))
    html = open(os.path.join(build, "soh.html"), encoding="utf-8").read()
    ver = str(int(os.path.getmtime(os.path.join(site, "oot.o2r"))))
    boot = ("<script>try{var _dv=new URLSearchParams(location.search).get('dev');if(_dv)window._devCvars=_dv;}catch(e){}</script>"
            "<script>if(!location.hash||location.hash.length<2){history.replaceState(null,'',"
            "location.pathname+location.search+'#soh=soh.o2r%3Fv%3D" + ver + "&oot=oot.o2r%3Fv%3D" + ver + "');}</script>")
    html = html.replace("<head>", "<head>" + boot, 1)
    html = re.sub(r"<title>[^<]*</title>", "<title>Ocarina of Time Clean Room</title>", html)
    html = html.replace("<h1>Ship of Harkinian</h1>", "<h1>Ocarina of Time &mdash; Clean Room</h1>")
    html = html.replace("WebAssembly Port", "Ship of Harkinian web build &middot; every ROM asset regenerated")
    extra = os.path.join(HERE, "site_extra.html")
    if os.path.exists(extra):
        html = html.replace("</body>", open(extra, encoding="utf-8").read() + "</body>")
    open(os.path.join(site, "index.html"), "w", encoding="utf-8").write(html)
    print("site:", sorted(os.listdir(site)))


if __name__ == "__main__":
    main(sys.argv)
