import socket


def local_ip() -> str:
    """IP ของเครื่องนี้บน LAN (ใช้บอกให้ iPad ใส่ปลายทาง)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # ไม่ได้ส่งข้อมูลจริง
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
