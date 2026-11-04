"""Native camera and inference isolation. No frame queues, network or image archives."""
import ctypes
import json
import multiprocessing as mp
from pathlib import Path
import queue
import time

import cv2
import numpy as np

from .engine import Decoder
from .store import History


class StopSignal:
    """Lock-free stop flag: a killed child must never poison Event.set()."""
    def __init__(self, context):
        self.flag = context.Value('b', False, lock=False)

    def set(self):
        self.flag.value = True

    def is_set(self):
        return bool(self.flag.value)

    def wait(self, seconds):
        end = time.monotonic()+seconds
        while not self.is_set() and time.monotonic() < end:
            time.sleep(min(.025, max(0, end-time.monotonic())))
        return self.is_set()


class Mailbox:
    """Bounded latest JSON value; timed locks avoid hangs after forced termination.

    Unlike a multiprocessing.Queue, no pipe or feeder can be left half-written.
    Scan history is committed independently in SQLite before publishing results.
    """
    def __init__(self, context, capacity=262144):
        self.buffer = context.RawArray(ctypes.c_ubyte, capacity)
        self.meta = context.RawArray(ctypes.c_int64, 2)
        self.lock = context.Lock()
        self.consumed = 0

    def put_nowait(self, value):
        content = json.dumps(value, ensure_ascii=False).encode('utf-8')
        if len(content) > len(self.buffer):
            raise ValueError('IPC message too large')
        if not self.lock.acquire(timeout=.02):
            return
        try:
            np.frombuffer(self.buffer, np.uint8)[:len(content)] = np.frombuffer(content, np.uint8)
            self.meta[1] = len(content)
            self.meta[0] += 1
        finally:
            self.lock.release()

    def get_nowait(self):
        if not self.lock.acquire(timeout=.01):
            raise queue.Empty
        try:
            version, size = self.meta
            if version == self.consumed:
                raise queue.Empty
            content = bytes(self.buffer[:size])
            self.consumed = version
        finally:
            self.lock.release()
        return json.loads(content)


class SharedFrame:
    def __init__(self, context):
        self.bytes = context.RawArray(ctypes.c_ubyte, 1920*1080*3)
        self.meta = context.RawArray(ctypes.c_double, 4)  # sequence, timestamp, height, width
        self.lock = context.Lock()

    def write(self, frame):
        h, w = frame.shape[:2]
        if h > 1080 or w > 1920:
            ratio = min(1920/w, 1080/h)
            frame = cv2.resize(frame, (round(w*ratio), round(h*ratio)))
        frame = np.ascontiguousarray(frame, dtype=np.uint8)
        if not self.lock.acquire(timeout=.1):
            return
        try:
            np.frombuffer(self.bytes, np.uint8)[:frame.size] = frame.ravel()
            self.meta[0] += 1
            self.meta[1:] = [time.monotonic(), frame.shape[0], frame.shape[1]]
        finally:
            self.lock.release()

    def read(self, after=0):
        if not self.lock.acquire(timeout=.02):
            return None
        try:
            seq, stamp, h, w = self.meta
            if seq <= after or not h or not w:
                return None
            frame = np.frombuffer(self.bytes, np.uint8)[:int(h*w*3)].reshape(int(h), int(w), 3).copy()
            return int(seq), stamp, frame
        finally:
            self.lock.release()


def publish(channel, value):
    try:
        channel.put_nowait(value)
    except queue.Full:
        pass


def camera_worker(shared, stop, heartbeat, messages, source, backend):
    cv2.setNumThreads(1)
    cap = None
    delay = 1.
    try:
        if isinstance(source, str) and Path(source).suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp'}:
            image = cv2.imread(source)
            if image is None:
                raise RuntimeError('Không mở được ảnh nguồn')
            publish(messages, {'camera': 'Đang phát ảnh kiểm chứng'})
            while not stop.wait(1/30):
                heartbeat.value = time.monotonic()
                shared.write(image)
            return
        while not stop.is_set():
            heartbeat.value = time.monotonic()
            driver = cv2.CAP_DSHOW if backend == 'DirectShow' else cv2.CAP_MSMF
            cap = cv2.VideoCapture(source, driver) if isinstance(source, int) else cv2.VideoCapture(source)
            if not cap.isOpened():
                cap.release()
                publish(messages, {'camera': 'Chưa mở được camera. Đang kết nối lại…'})
                stop.wait(delay)
                delay = min(delay*2, 8.)
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            publish(messages, {'camera': 'Camera đang hoạt động'})
            failures = 0
            video_delay = 1/max(1, cap.get(cv2.CAP_PROP_FPS)) if isinstance(source, str) else 0
            while not stop.is_set():
                loop_started = time.monotonic()
                heartbeat.value = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= 5:
                        break
                    stop.wait(.1)
                    continue
                failures, delay = 0, 1.
                shared.write(frame)
                if video_delay:
                    stop.wait(max(0, video_delay-(time.monotonic()-loop_started)))
            cap.release()
            if isinstance(source, str):
                publish(messages, {'camera': 'Đã kết thúc video', 'ended': True})
                stop.wait(1)
                return
            if not stop.is_set():
                publish(messages, {'camera': 'Camera mất hình. Đang kết nối lại…'})
                stop.wait(delay)
    except Exception as exc:
        publish(messages, {'error': f'Camera: {exc}'})
    finally:
        if cap is not None:
            cap.release()


def decoder_worker(shared, stop, heartbeat, messages, results, models, root, roi):
    history = None
    try:
        decoder = Decoder(Path(models), roi)
        history = History(Path(root))
        publish(messages, {'decoder': 'Hai bộ đọc đã sẵn sàng'})
        sequence = 0
        last_prune = time.monotonic()
        written = 0
        while not stop.is_set():
            heartbeat.value = time.monotonic()
            began = time.monotonic()
            item = shared.read(sequence)
            if item is None:
                stop.wait(.025)
                continue
            sequence, stamp, frame = item
            if began-stamp > .75:
                continue
            result = decoder.scan(frame)
            # Never accept results from a camera frame that took too long.
            if time.monotonic()-stamp > 2.5:
                decoder.confirmation.states.clear()
                publish(messages, {'decoder': 'Bỏ kết quả cũ; đang lấy khung hình mới'})
                continue
            for text in result['accepted']:
                engine = next(d['engine'] for d in result['detections'] if d['text'] == text)
                history.append(text, engine)
                written += 1
            if written >= 100 or began-last_prune > 3600:
                history.prune()
                written, last_prune = 0, began
            publish(results, {**result, 'sequence': sequence, 'frame_at': stamp, 'at': time.monotonic()})
            heartbeat.value = time.monotonic()
            stop.wait(max(0, .1-(time.monotonic()-began)))
    except Exception as exc:
        publish(messages, {'fatal': f'Bộ đọc: {exc}'})
    finally:
        if history:
            history.close()


class Runtime:
    def __init__(self, models, root):
        self.context = mp.get_context('spawn')
        self.models, self.root = str(models), str(root)
        self.running = False
        self.camera = self.decoder = None
        self.restarts = []
        self.latest_result = None
        self.diagnostics = {'camera_restarts': 0, 'decoder_restarts': 0}
        self.last_health = 0

    def start(self, source=0, backend='DirectShow', roi=None, *, recovery=False):
        self.stop()
        if not recovery:
            self.restarts.clear()
        self.source, self.backend, self.roi = source, backend, roi
        ctx = self.context
        self.shared = SharedFrame(ctx)
        self.camera_messages, self.results = Mailbox(ctx), Mailbox(ctx)
        self.stop_event, self.decode_stop = StopSignal(ctx), StopSignal(ctx)
        self.camera_heartbeat = ctx.Value('d', time.monotonic(), lock=False)
        self.decode_heartbeat = ctx.Value('d', time.monotonic(), lock=False)
        self.camera = ctx.Process(target=camera_worker, args=(self.shared, self.stop_event,
            self.camera_heartbeat, self.camera_messages, source, backend), daemon=True)
        self.running = True
        self.started = time.monotonic()
        self.latest_result = None
        self.camera.start()
        self._start_decoder()

    def _start_decoder(self):
        self.decode_stop = StopSignal(self.context)
        self.decode_messages = Mailbox(self.context)
        self.decode_heartbeat.value = time.monotonic()
        self.decoder_started = time.monotonic()
        self.decoder = self.context.Process(target=decoder_worker, args=(self.shared, self.decode_stop,
            self.decode_heartbeat, self.decode_messages, self.results, self.models, self.root, self.roi), daemon=True)
        self.decoder.start()

    @staticmethod
    def _finish(process, event):
        if process is None:
            return
        if process.is_alive():
            event.set()
        process.join(.25)
        if process.is_alive():
            process.terminate()
            process.join(.5)
        if process.is_alive():
            process.kill()
            process.join(.5)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self._finish(self.decoder, self.decode_stop)
        self._finish(self.camera, self.stop_event)
        self.camera = self.decoder = None

    def poll(self):
        if not self.running:
            return []
        messages = []
        for channel, target in ((self.camera_messages, messages), (self.decode_messages, messages), (self.results, None)):
            for _ in range(32):
                try:
                    item = channel.get_nowait()
                except queue.Empty:
                    break
                if target is not None:
                    target.append(item)
                else:
                    self.latest_result = item
        if any('fatal' in item or item.get('ended') for item in messages):
            self.stop()
            return messages
        now = time.monotonic()
        if now-self.last_health < .5:
            return messages
        self.last_health = now
        last_frame = self.shared.meta[1]
        camera_bad = (not self.camera.is_alive() or now-self.camera_heartbeat.value > 12
                      or (last_frame > 0 and now-last_frame > 12))
        decoder_bad = (not self.decoder.is_alive()
                       or (now-self.decoder_started > 15 and now-self.decode_heartbeat.value > 8))
        if now-self.started < 15:
            return messages
        if camera_bad or decoder_bad:
            self.restarts = [value for value in self.restarts if now-value < 60]
            if len(self.restarts) >= 3:
                messages.append({'fatal': 'Đã dừng sau nhiều lỗi liên tiếp. Kiểm tra camera rồi bấm Mở camera.'})
                self.stop()
            else:
                self.restarts.append(now)
                if camera_bad:
                    self.diagnostics['camera_restarts'] += 1
                    messages.append({'camera': 'Đang phục hồi camera bị treo…'})
                    self.start(self.source, self.backend, self.roi, recovery=True)
                else:
                    self.diagnostics['decoder_restarts'] += 1
                    messages.append({'decoder': 'Đang phục hồi bộ đọc bị treo…'})
                    self._finish(self.decoder, self.decode_stop)
                    # Replace IPC as a killed writer may leave its queue unusable.
                    self.results = Mailbox(self.context)
                    self._start_decoder()
        return messages
