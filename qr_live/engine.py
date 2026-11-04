"""Two offline readers, bounded fallback scheduling and temporal confirmation."""
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
import zxingcpp


class Confirmation:
    def __init__(self):
        self.states = OrderedDict()

    def observe(self, codes, now):
        accepted = []
        for code in dict.fromkeys(codes):
            if not code or len(code) > 8192:
                continue
            item = self.states.get(code)
            if item is None or now - item['seen'] > 1.5:
                item = {'seen': now, 'hits': 0, 'emitted': False}
            if now - item['seen'] > 1.4:
                item['hits'] = 0
            item['hits'] += 1
            item['seen'] = now
            if item['hits'] >= 2 and not item['emitted']:
                item['emitted'] = True
                accepted.append(code)
            self.states[code] = item
            self.states.move_to_end(code)
        for code in list(self.states):
            if now - self.states[code]['seen'] > 60:
                del self.states[code]
        while len(self.states) > 256:
            self.states.popitem(last=False)
        return accepted


def validate_roi(value):
    if value is None:
        return [0., 0., 1., 1.]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError('Vùng quét không hợp lệ')
    x1, y1, x2, y2 = map(float, value)
    if not all(np.isfinite(v) and 0 <= v <= 1 for v in (x1, y1, x2, y2)) or x2-x1 < .02 or y2-y1 < .02:
        raise ValueError('Vùng quét quá nhỏ hoặc nằm ngoài ảnh')
    return [x1, y1, x2, y2]


class Decoder:
    def __init__(self, models: Path, roi=None):
        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)
        manifest = json.loads((models / 'manifest.json').read_text('utf-8'))
        for name, expected in manifest['files'].items():
            path = models / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'Thiếu hoặc sai checksum model: {name}. Hãy cài lại bộ cài đầy đủ.')
        self.wechat = cv2.wechat_qrcode_WeChatQRCode(*[str(models / name) for name in (
            'detect_2021nov.prototxt', 'detect_2021nov.caffemodel',
            'sr_2021nov.prototxt', 'sr_2021nov.caffemodel')])
        self.roi = validate_roi(roi)
        self.confirmation = Confirmation()
        self.last_fallback = -100.
        self.last_success = -100.
        self.last_motion = time.monotonic()
        self.previous = None
        self.scans = self.fallbacks = 0

    def scan(self, frame, *, now=None, mode='hybrid'):
        now = time.monotonic() if now is None else now
        h, w = frame.shape[:2]
        a, b, c, d = self.roi
        left, top, right, bottom = int(a*w), int(b*h), max(int(c*w), 1), max(int(d*h), 1)
        crop = frame[top:bottom, left:right]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (64, 36))
        if self.previous is None or float(np.mean(cv2.absdiff(small, self.previous))) > 3:
            self.last_motion = now
        self.previous = small
        # Retain original pixels for decoding; restrict work to QR only.
        found = []
        started = time.monotonic()
        if mode != 'wechat':
            for code in zxingcpp.read_barcodes(gray, formats=zxingcpp.BarcodeFormat.QRCode,
                    try_rotate=True, try_downscale=True, try_invert=True):
                if code.valid and code.text:
                    p = code.position
                    points = [[v.x+left, v.y+top] for v in (p.top_left, p.top_right, p.bottom_right, p.bottom_left)]
                    found.append({'text': code.text, 'points': points, 'engine': 'ZXing-C++'})
        used_fallback = False
        # Empty, static scenes must NOT run both engines on every scan.
        cooldown = 1.0 if now-self.last_motion < 5 else 5.0
        if mode == 'wechat' or (mode == 'hybrid' and not found and now-self.last_fallback >= cooldown
                                and now-self.last_success >= .7):
            self.last_fallback = now
            self.fallbacks += 1
            used_fallback = True
            values, points = self.wechat.detectAndDecode(crop)
            for text, polygon in zip(values, points):
                if text:
                    shifted = np.asarray(polygon).reshape(4, 2) + [left, top]
                    found.append({'text': text, 'points': shifted.tolist(), 'engine': 'WeChatQRCode'})
        # Bound information sent to the interface, even for scenes full of labels.
        unique = {item['text']: item for item in found if len(item['text']) <= 8192}
        found = list(unique.values())[:16]
        if found:
            self.last_success = now
            # Keep fallback active long enough to confirm a QR that ZXing misses,
            # including a small QR in an otherwise static image.
            self.last_motion = now
        accepted = self.confirmation.observe([item['text'] for item in found], now)
        self.scans += 1
        return {'detections': found, 'accepted': accepted, 'fallback': used_fallback,
                'elapsed_ms': round((time.monotonic()-started)*1000, 1),
                'scans': self.scans, 'fallbacks': self.fallbacks}
