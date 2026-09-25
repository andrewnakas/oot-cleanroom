"""Local dev server: static files with COOP/COEP headers, plus POST /upload?name=x
which saves the request body to <upload dir>/x (used to pull files out of a page's
virtual FS, e.g. an in-browser extraction result; dev only).

    python ports/wasm/devserve.py <site dir> <port> [upload dir]
"""
import http.server
import os
import sys
import urllib.parse

UPLOAD = None


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = os.path.basename(q.get("name", ["upload.bin"])[0])
        n = int(self.headers.get("Content-Length", 0))
        with open(os.path.join(UPLOAD, name), "wb") as f:
            left = n
            while left:
                b = self.rfile.read(min(left, 1 << 20))
                if not b:
                    break
                f.write(b)
                left -= len(b)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


Handler.extensions_map.update({".wasm": "application/wasm", ".js": "text/javascript", ".data": "application/octet-stream"})

if __name__ == "__main__":
    site = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8064
    UPLOAD = os.path.abspath(sys.argv[3] if len(sys.argv) > 3 else site)
    os.makedirs(UPLOAD, exist_ok=True)
    os.chdir(site)
    print(f"serving {site} on http://localhost:{port}/ (uploads -> {UPLOAD})", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
