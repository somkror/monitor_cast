# monitor_cast

รับภาพหน้าจอ iPad แบบ realtime มาแสดงบนคอมพิวเตอร์ (Python + ffmpeg)
ดูได้ทั้งในหน้าต่างบนเครื่อง และผ่านเว็บเบราว์เซอร์ (`http://<IP>:8080/`) จากเครื่องอื่นใน LAN

## ติดตั้ง

```bash
pip install -r requirements.txt
# ต้องมี ffmpeg:  brew install ffmpeg | sudo apt install ffmpeg | winget install ffmpeg
```

## วิธีรับภาพจาก iPad

| โหมด | ฝั่ง iPad | หมายเหตุ |
|---|---|---|
| `rtmp` | แอพที่ทำ Broadcast จอได้ เช่น **Larix Broadcaster** (เลือก Screen capture) หรือ Prism | ใช้ได้ทุกเครื่อง ผ่าน Wi-Fi เดียวกัน ทดสอบแล้ว |
| `srt` | Larix Broadcaster (SRT) | latency ต่ำกว่า RTMP (ต้อง ffmpeg ที่รองรับ SRT) |
| `airplay` | Control Center → Screen Mirroring → `MonitorCast` | ไม่ต้องลงแอพบน iPad ใช้ [UxPlay](https://github.com/FDH2/UxPlay) — **ยังไม่ได้ทดสอบกับ iPad จริง** |
| `usb` | เสียบสาย USB กด "เชื่อถือ" | macOS เห็น iPad เป็นอุปกรณ์วิดีโอ (`usb --list` ดูชื่อ) latency ต่ำสุด ไม่ผ่านเครือข่าย |
| `url` | – | ดึงจาก URL ใดก็ได้ที่ ffmpeg อ่านได้ |

### ตัวอย่าง (RTMP)

```bash
python -m monitor_cast rtmp
```

โปรแกรมจะแสดง IP เช่น `rtmp://192.168.1.20:1935/live/ipad` — นำไปใส่เป็นปลายทางในแอพ Larix แล้วกดเริ่ม
(ไฟร์วอลล์ต้องเปิดพอร์ต 1935 และ 8080)

```bash
python -m monitor_cast usb --list            # ดูรายการอุปกรณ์ (macOS)
python -m monitor_cast usb --device "1"
python -m monitor_cast srt --port 9000
python -m monitor_cast airplay --name MonitorCast
python -m monitor_cast rtmp --no-window --width 1280 --fps 30   # เว็บอย่างเดียว ลดแบนด์วิธ
```

คีย์ในหน้าต่าง: `f` เต็มจอ · `s` บันทึกภาพ · `q`/`Esc` ออก  
บนหน้าเว็บ: ดับเบิลคลิกเพื่อเต็มจอ, `/snapshot.jpg` ดึงภาพนิ่ง, `/status` ดูสถานะ

## ข้อจำกัดที่ควรรู้

- iPadOS ไม่มี API ให้เว็บแอพ/Safari จับหน้าจอ (`getDisplayMedia` ใช้ไม่ได้) จึงต้องใช้แอพ broadcast, AirPlay หรือ USB
- AirPlay ของ Apple เข้ารหัส (FairPlay) จึงรับตรง ๆ ด้วย Python ล้วนไม่ได้ ต้องพึ่ง UxPlay
- ถ้าสัญญาณหลุด โปรแกรมจะรอรับการเชื่อมต่อใหม่ให้อัตโนมัติ
