"""หน้าต่างแสดงผลบนเครื่อง (OpenCV)  คีย์: q/Esc ออก, f เต็มจอ, s บันทึกภาพ"""
import time

from .hub import FrameHub

WIN = "Monitor Cast"


def run_window(hub: FrameHub):
    import cv2
    import numpy as np

    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    fullscreen, seq, shown = False, 0, False
    waiting = np.zeros((360, 640, 3), np.uint8)
    cv2.putText(waiting, "Waiting for iPad...", (150, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    cv2.imshow(WIN, waiting)
    while True:
        seq, jpg = hub.wait_next(seq, 0.03)
        if jpg is not None:
            frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                cv2.imshow(WIN, frame)
                shown = True
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27) or cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            break
        if key == ord("f"):
            fullscreen = not fullscreen
            cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
        if key == ord("s") and shown and hub.latest():
            name = time.strftime("capture_%Y%m%d_%H%M%S.jpg")
            open(name, "wb").write(hub.latest())
            print("บันทึก", name)
    cv2.destroyAllWindows()
