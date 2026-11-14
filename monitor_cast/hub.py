"""ที่เก็บเฟรมล่าสุด (JPEG) ให้ viewer / web อ่านพร้อมกันได้"""
import threading
import time


class FrameHub:
    def __init__(self):
        self._cond = threading.Condition()
        self._jpeg = None
        self._seq = 0
        self.source_name = "-"
        self.connected = False
        self._times = []

    def publish(self, jpeg: bytes):
        now = time.monotonic()
        with self._cond:
            self._jpeg = jpeg
            self._seq += 1
            self._times.append(now)
            self._times = [t for t in self._times if now - t < 2.0]
            self.connected = True
            self._cond.notify_all()

    def set_connected(self, value: bool):
        with self._cond:
            self.connected = value
            if not value:
                self._times = []
            self._cond.notify_all()

    def latest(self):
        with self._cond:
            return self._jpeg

    def wait_next(self, last_seq: int, timeout: float = 1.0):
        """รอเฟรมใหม่ คืน (seq, jpeg) หรือ (last_seq, None) ถ้า timeout"""
        with self._cond:
            if self._seq == last_seq:
                self._cond.wait(timeout)
            if self._seq == last_seq:
                return last_seq, None
            return self._seq, self._jpeg

    @property
    def fps(self) -> float:
        with self._cond:
            if len(self._times) < 2:
                return 0.0
            span = self._times[-1] - self._times[0]
            return (len(self._times) - 1) / span if span > 0 else 0.0
