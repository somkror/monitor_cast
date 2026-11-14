"""เว็บ viewer (MJPEG) — เปิดดูจากเบราว์เซอร์เครื่องไหนใน LAN ก็ได้"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .hub import FrameHub

PAGE = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Monitor Cast</title>
<style>html,body{margin:0;height:100%;background:#000;color:#9aa;font:14px sans-serif}
img{width:100%;height:100%;object-fit:contain;display:block}
#s{position:fixed;top:8px;left:8px;background:#000a;padding:4px 8px;border-radius:6px}</style>
<img src=/stream><div id=s>…</div>
<script>
setInterval(async()=>{try{const j=await (await fetch('/status')).json();
document.getElementById('s').textContent=(j.connected?'● '+j.fps.toFixed(0)+' fps':'○ รอสัญญาณ')+' · '+j.source}
catch(e){}},1000);
document.body.ondblclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
</script>"""


def make_handler(hub: FrameHub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.encode())
            elif path == "/status":
                body = json.dumps({"connected": hub.connected, "fps": hub.fps,
                                   "source": hub.source_name}).encode()
                self._send(200, "application/json", body)
            elif path == "/snapshot.jpg":
                jpg = hub.latest()
                if jpg:
                    self._send(200, "image/jpeg", jpg)
                else:
                    self._send(503, "text/plain", b"no frame yet")
            elif path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                seq = 0
                try:
                    while True:
                        seq, jpg = hub.wait_next(seq, 1.0)
                        if jpg is None:
                            continue
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: %d\r\n\r\n" % len(jpg))
                        self.wfile.write(jpg + b"\r\n")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
            else:
                self._send(404, "text/plain", b"not found")

    return Handler


class ThreadedServer(ThreadingHTTPServer):
    daemon_threads = True


def start_web(hub: FrameHub, host: str, port: int):
    srv = ThreadedServer((host, port), make_handler(hub))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
