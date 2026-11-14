import argparse
import signal
import time

from . import sources
from .hub import FrameHub
from .net import local_ip
from .web import start_web


def build_parser():
    p = argparse.ArgumentParser(prog="monitor_cast",
                                description="รับ cast หน้าจอ iPad แบบ realtime")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--web-port", type=int, default=8080, help="พอร์ตเว็บ viewer (0 = ปิด)")
    common.add_argument("--no-window", action="store_true", help="ไม่เปิดหน้าต่างบนเครื่อง (ดูผ่านเว็บอย่างเดียว)")
    common.add_argument("--width", type=int, help="ย่อภาพไม่เกินความกว้างนี้ (ลด latency/แบนด์วิธ)")
    common.add_argument("--fps", type=int, help="จำกัด fps")
    sub = p.add_subparsers(dest="mode", required=True)

    r = sub.add_parser("rtmp", parents=[common], help="รับ RTMP จากแอพ broadcast บน iPad (เช่น Larix)")
    r.add_argument("--host", default="0.0.0.0")
    r.add_argument("--port", type=int, default=1935)
    r.add_argument("--key", default="ipad", help="stream key")
    s = sub.add_parser("srt", parents=[common], help="รับ SRT (latency ต่ำกว่า RTMP)")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=9000)
    a = sub.add_parser("airplay", parents=[common], help="AirPlay Screen Mirroring ผ่าน UxPlay")
    a.add_argument("--name", default="MonitorCast", help="ชื่อที่ iPad จะเห็น")
    d = sub.add_parser("usb", parents=[common], help="iPad เสียบสาย USB (macOS เห็นเป็น capture device)")
    d.add_argument("--device", help='ชื่อ/ลำดับอุปกรณ์ เช่น "1" หรือ "iPad"')
    d.add_argument("--list", action="store_true", help="แสดงรายการอุปกรณ์แล้วออก")
    u = sub.add_parser("url", parents=[common], help="ดึงจาก URL ใด ๆ ที่ ffmpeg อ่านได้")
    u.add_argument("url")
    return p


def main():
    args = build_parser().parse_args()
    if args.mode == "usb" and args.list:
        sources.require_ffmpeg()
        return sources.list_devices()
    if args.mode != "airplay":
        sources.require_ffmpeg()

    hub = FrameHub()
    kw = dict(width=args.width, fps=args.fps)
    if args.mode == "rtmp":
        src = sources.rtmp_source(hub, args.host, args.port, args.key, **kw)
    elif args.mode == "srt":
        src = sources.srt_source(hub, args.host, args.port, **kw)
    elif args.mode == "airplay":
        src = sources.AirPlaySource(hub, args.name)
    elif args.mode == "usb":
        if not args.device:
            raise SystemExit("ระบุ --device (ดูรายการด้วย: usb --list)")
        src = sources.device_source(hub, args.device, **kw)
    else:
        src = sources.url_source(hub, args.url, **kw)

    ip = local_ip()
    if args.web_port:
        start_web(hub, "0.0.0.0", args.web_port)
        print(f"เว็บ viewer: http://{ip}:{args.web_port}/")
    if args.mode in ("rtmp", "srt"):
        port = args.port
        print(f"IP เครื่องนี้: {ip}  → ปลายทางบน iPad: "
              + (f"rtmp://{ip}:{port}/live/{args.key}" if args.mode == "rtmp" else f"srt://{ip}:{port}"))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    src.start()

    try:
        if args.no_window:
            while True:
                time.sleep(3600)
        else:
            try:
                from .viewer import run_window
                run_window(hub)
            except ImportError:
                print("ไม่มี opencv-python — ใช้โหมดเว็บอย่างเดียว (pip install -r requirements.txt)")
                while True:
                    time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        src.stop()


if __name__ == "__main__":
    main()
