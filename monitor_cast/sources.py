"""แหล่งสัญญาณภาพ: ทุกแบบถูกแปลงเป็นสตรีม JPEG แล้วส่งเข้า FrameHub"""
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time

from .hub import FrameHub

SOI, EOI = b"\xff\xd8", b"\xff\xd9"


def iter_jpegs(read):
    """แยกไฟล์ JPEG ต่อกัน ๆ จากสตรีมไบต์ (read(n) -> bytes)"""
    buf = bytearray()
    while True:
        chunk = read(65536)
        if not chunk:
            return
        buf += chunk
        while True:
            s = buf.find(SOI)
            if s < 0:
                buf.clear()
                break
            e = buf.find(EOI, s + 2)
            if e < 0:
                if s:
                    del buf[:s]
                break
            yield bytes(buf[s:e + 2])
            del buf[:e + 2]


def require_ffmpeg():
    if not shutil.which("ffmpeg"):
        sys.exit("ไม่พบ ffmpeg — ติดตั้งก่อน: brew install ffmpeg | apt install ffmpeg | winget install ffmpeg")


def ffmpeg_cmd(input_args, width=None, fps=None, quality=5):
    vf = []
    if fps:
        vf.append(f"fps={fps}")
    if width:
        vf.append(f"scale='min({width},iw)':-2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
           "-flags", "low_delay", *input_args, "-an"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-c:v", "mjpeg", "-q:v", str(quality), "-f", "image2pipe", "-"]
    return cmd


class Source:
    """รัน process ซ้ำเรื่อย ๆ (รอ iPad เชื่อมต่อใหม่ได้) แล้วดันเฟรมเข้า hub"""

    name = "source"
    hint = ""

    def __init__(self, hub: FrameHub):
        self.hub = hub
        self._stop = threading.Event()
        self._proc = None
        self.hub.source_name = self.name

    def command(self):
        raise NotImplementedError

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _run(self):
        while not self._stop.is_set():
            print(f"[{self.name}] รอสัญญาณ... {self.hint}", flush=True)
            try:
                self._proc = subprocess.Popen(
                    self.command(), stdout=subprocess.PIPE, bufsize=0)
            except FileNotFoundError as e:
                print(f"[{self.name}] เรียกโปรแกรมไม่ได้: {e}")
                return
            first = True
            for jpg in iter_jpegs(self._proc.stdout.read):
                if first:
                    print(f"[{self.name}] เชื่อมต่อแล้ว ✔", flush=True)
                    first = False
                self.hub.publish(jpg)
            self._proc.wait()
            self.hub.set_connected(False)
            if not self._stop.is_set():
                print(f"[{self.name}] สัญญาณหลุด รอเชื่อมต่อใหม่", flush=True)
                time.sleep(1)


class FfmpegSource(Source):
    """ffmpeg รับสัญญาณ (เป็น server รอ iPad ส่งมา หรือดึงจากอุปกรณ์/URL)"""

    def __init__(self, hub, label, input_args, hint="", width=None, fps=None):
        self.name, self.hint = label, hint
        self.input_args, self.width, self.fps = list(input_args), width, fps
        super().__init__(hub)

    def command(self):
        return ffmpeg_cmd(self.input_args, self.width, self.fps)


_LOW_LATENCY_IN = ["-probesize", "32768", "-analyzeduration", "0"]


def rtmp_source(hub, host, port, key, **kw):
    url = f"rtmp://{host}:{port}/live/{key}"
    shown = url.replace("0.0.0.0", "<IP เครื่องนี้>")
    return FfmpegSource(hub, "rtmp", ["-listen", "1", *_LOW_LATENCY_IN, "-i", url],
                        hint=f"ให้ iPad ส่ง RTMP ไปที่ {shown}", **kw)


def srt_source(hub, host, port, **kw):
    url = f"srt://{host}:{port}?mode=listener&latency=60000"
    return FfmpegSource(hub, "srt", [*_LOW_LATENCY_IN, "-i", url],
                        hint=f"ให้ iPad ส่ง SRT (caller) ไปที่ port {port}", **kw)


def url_source(hub, url, **kw):
    return FfmpegSource(hub, "url", [*_LOW_LATENCY_IN, "-i", url], hint=url, **kw)


def device_input_args(system, spec):
    if system == "Darwin":  # iPad เสียบสาย USB: macOS เห็นเป็นอุปกรณ์วิดีโอ
        return ["-f", "avfoundation", "-framerate", "30",
                "-capture_cursor", "0", "-i", f"{spec}:none"]
    if system == "Windows":
        return ["-f", "dshow", "-i", f"video={spec}"]
    return ["-f", "v4l2", "-i", spec]


def list_devices():
    system = platform.system()
    if system == "Darwin":
        cmd = ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""]
    elif system == "Windows":
        cmd = ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
    else:
        cmd = ["ffmpeg", "-hide_banner", "-sources", "v4l2"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    print(out.stderr + out.stdout)


def device_source(hub, spec, **kw):
    return FfmpegSource(hub, f"usb:{spec}", device_input_args(platform.system(), spec),
                        hint="เสียบสาย USB แล้วกด 'เชื่อถือ' บน iPad", **kw)


class AirPlaySource(Source):
    """ใช้ UxPlay (AirPlay receiver โอเพนซอร์ส) รับ Screen Mirroring จาก iPad
    แล้วส่งภาพกลับมาเป็น JPEG ผ่าน TCP ในเครื่อง  (ยังไม่ได้ทดสอบกับ iPad จริง)"""

    def __init__(self, hub, airplay_name="MonitorCast", bridge=False):
        self.bridge = bridge
        self.name = "airplay"
        self.hint = f"iPad: Control Center > Screen Mirroring > {airplay_name}"
        self.airplay_name = airplay_name
        self._srv = socket.socket()
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]
        super().__init__(hub)

    def start(self):
        if not shutil.which("uxplay"):
            sys.exit("ไม่พบ uxplay — ติดตั้ง: brew install uxplay | apt install uxplay "
                     "(Windows/อื่น ๆ: https://github.com/FDH2/UxPlay)")
        if self.bridge:
            threading.Thread(target=self._accept_loop, daemon=True).start()
        super().start()

    def command(self):
        if not self.bridge:  # โหมดมาตรฐาน: UxPlay แสดงหน้าต่างเอง
            return ["uxplay", "-n", self.airplay_name]
        sink = f"videoconvert ! jpegenc quality=80 ! tcpclientsink host=127.0.0.1 port={self.port}"
        return ["uxplay", "-n", self.airplay_name, "-vs", sink, "-as", "0"]

    def _accept_loop(self):
        while not self._stop.is_set():
            conn, _ = self._srv.accept()
            first = True
            for jpg in iter_jpegs(conn.recv):
                if first:
                    print("[airplay] เชื่อมต่อแล้ว ✔", flush=True)
                    first = False
                self.hub.publish(jpg)
            conn.close()
            self.hub.set_connected(False)

    def _run(self):  # uxplay พิมพ์ log ทาง stdout; ปล่อยผ่าน ไม่ต้อง parse
        while not self._stop.is_set():
            print(f"[airplay] {self.hint}", flush=True)
            self._proc = subprocess.Popen(self.command())
            self._proc.wait()
            if not self._stop.is_set():
                time.sleep(1)
