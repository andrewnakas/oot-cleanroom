"""Dev tool: drive a page in headless Edge/Chrome over CDP with a step script.

    python ports/wasm/cdp_run.py <url> <steps.json> [--out dir] [--webgl] [--timeout 600]

steps.json is a list of steps:
  {"wait": "<js expr>", "timeout": 60}   poll until the expression is truthy
  {"eval": "<js expr>"}                   evaluate (awaits promises), print result
  {"sleep": 2.5}
  {"shot": "name"}                        Page.captureScreenshot -> <out>/name.png
  {"key": "KeyX", "down": 0.1}            press a key (code) for `down` seconds
  {"keys": [["KeyX", 0.1], ["Enter", 0.1]], "gap": 0.3}
  {"press_until": "<js expr>", "key": "KeyX", "every": 3, "timeout": 60}   press a key until true
Console lines are printed (trimmed) and saved to <out>/console.txt.
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

import websocket

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]

KEYINFO = {"Enter": ("Enter", 13), "Space": (" ", 32), "Escape": ("Escape", 27),
           "ArrowUp": ("ArrowUp", 38), "ArrowDown": ("ArrowDown", 40),
           "ArrowLeft": ("ArrowLeft", 37), "ArrowRight": ("ArrowRight", 39),
           "ShiftLeft": ("Shift", 16), "ShiftRight": ("Shift", 16), "Tab": ("Tab", 9)}


def keyinfo(code):
    if code in KEYINFO:
        return KEYINFO[code]
    if code.startswith("Key"):
        return code[3].lower(), ord(code[3])
    if code.startswith("Digit"):
        return code[5], ord(code[5])
    return code, 0


class Page:
    def __init__(self, ws, quiet):
        self.ws, self.n, self.console, self.quiet = ws, 0, [], quiet

    def _handle(self, m):
        meth = m.get("method")
        if meth == "Runtime.consoleAPICalled":
            s = " ".join(str(x.get("value", x.get("description", ""))) for x in m["params"]["args"])
            self.console.append(s)
            if not self.quiet:
                print("  |", s[:200], flush=True)
        elif meth == "Runtime.exceptionThrown":
            ed = m["params"]["exceptionDetails"]
            s = "EXCEPTION: " + (ed.get("exception", {}).get("description", "") or ed.get("text", ""))[:300]
            self.console.append(s)
            print("  |", s.split("\n")[0], flush=True)

    def call(self, method, timeout=600, **params):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                m = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if m.get("id") == mid:
                return m.get("result", m)
            self._handle(m)
        raise TimeoutError(method)

    def pump(self, secs):
        end = time.time() + secs
        while time.time() < end:
            try:
                self._handle(json.loads(self.ws.recv()))
            except websocket.WebSocketTimeoutException:
                pass

    def eval(self, expr, timeout=600):
        r = self.call("Runtime.evaluate", timeout=timeout, expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            return "EXC: " + r["exceptionDetails"].get("exception", {}).get("description", str(r["exceptionDetails"]))[:300]
        return r.get("result", {}).get("value")

    def key(self, code, down):
        k, vk = keyinfo(code)
        base = {"code": code, "key": k, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
        self.call("Input.dispatchKeyEvent", type="keyDown", **base)
        self.pump(down)
        self.call("Input.dispatchKeyEvent", type="keyUp", **base)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("steps")
    ap.add_argument("--out", default=".")
    ap.add_argument("--webgl", action="store_true")
    ap.add_argument("--port", type=int, default=9334)
    ap.add_argument("--size", default="1280,960")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    steps = json.load(open(a.steps))
    os.makedirs(a.out, exist_ok=True)
    exe = next(b for b in BROWSERS if os.path.exists(b))
    prof = tempfile.mkdtemp(prefix="cdprun_")
    args = [exe, "--headless=new", f"--user-data-dir={prof}", f"--remote-debugging-port={a.port}",
            "--remote-allow-origins=*", "--no-first-run", "--autoplay-policy=no-user-gesture-required",
            f"--window-size={a.size}"]
    if a.webgl:
        args += ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist"]
    p = subprocess.Popen(args + ["about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{a.port}/json"))
                break
            except OSError:
                time.sleep(0.2)
        tab = next(t for t in tabs if t.get("type") == "page")
        ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30, max_size=None)
        ws.settimeout(0.5)
        pg = Page(ws, a.quiet)
        pg.call("Runtime.enable")
        pg.call("Page.enable")
        pg.call("Page.navigate", url=a.url)
        for st in steps:
            t0 = time.time()
            if "wait" in st:
                end = time.time() + st.get("timeout", 60)
                ok = False
                while time.time() < end:
                    if pg.eval(st["wait"], timeout=30) is True:
                        ok = True
                        break
                    pg.pump(0.5)
                print(f"wait {'ok' if ok else 'TIMEOUT'} ({time.time()-t0:.1f}s): {st['wait'][:80]}", flush=True)
                if not ok and st.get("required", True):
                    break
            elif "press_until" in st:
                end = time.time() + st.get("timeout", 60)
                ok = False
                while time.time() < end:
                    if pg.eval(st["press_until"], timeout=30) is True:
                        ok = True
                        break
                    pg.key(st.get("key", "KeyX"), st.get("down", 0.2))
                    pg.pump(st.get("every", 3.0))
                print(f"press_until {'ok' if ok else 'TIMEOUT'} ({time.time()-t0:.1f}s): {st['press_until'][:60]}", flush=True)
            elif "eval" in st:
                v = pg.eval(st["eval"], timeout=st.get("timeout", 600))
                print(f"eval -> {str(v)[:400]}", flush=True)
            elif "sleep" in st:
                pg.pump(st["sleep"])
            elif "shot" in st:
                r = pg.call("Page.captureScreenshot", format="png")
                with open(os.path.join(a.out, st["shot"] + ".png"), "wb") as f:
                    f.write(base64.b64decode(r["data"]))
                print(f"shot {st['shot']}", flush=True)
            elif "key" in st:
                pg.key(st["key"], st.get("down", 0.1))
            elif "keys" in st:
                for code, down in st["keys"]:
                    pg.key(code, down)
                    pg.pump(st.get("gap", 0.3))
        with open(os.path.join(a.out, "console.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(pg.console))
    finally:
        p.kill()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    main()
