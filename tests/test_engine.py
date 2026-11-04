import json
import shutil
import time

import cv2
import numpy as np
import pytest
import qrcode

from qr_live.engine import Confirmation, Decoder, validate_roi
from qr_live.paths import assets_root


@pytest.fixture
def qr_frame():
    qr = qrcode.make('QR-LIVE-FACTORY-001').convert('RGB')
    image = np.full((720, 1280, 3), 245, np.uint8)
    image[150:150+qr.height, 400:400+qr.width] = cv2.cvtColor(np.array(qr), cv2.COLOR_RGB2BGR)
    return image


def test_real_zxing_and_wechat_decode(qr_frame):
    for mode in ('zxing', 'wechat'):
        decoder = Decoder(assets_root() / 'models')
        result = decoder.scan(qr_frame, mode=mode)
        assert [d['text'] for d in result['detections']] == ['QR-LIVE-FACTORY-001']
        result = decoder.scan(qr_frame, mode=mode)
        assert result['accepted'] == ['QR-LIVE-FACTORY-001']


def test_confirmation_rearms_after_disappearance():
    c = Confirmation()
    assert c.observe(['A'], 0) == []
    assert c.observe(['A'], .1) == ['A']
    assert c.observe(['A'], .2) == []
    c.observe([], 1)
    assert c.observe(['A'], 2) == []
    assert c.observe(['A'], 2.1) == ['A']


def test_wechat_confirmation_at_one_hz():
    c = Confirmation()
    assert c.observe(['A'], 1) == []
    assert c.observe(['A'], 2.01) == ['A']


def test_real_wechat_fallback_can_confirm_static_qr(qr_frame, monkeypatch):
    import qr_live.engine as engine
    monkeypatch.setattr(engine.zxingcpp, 'read_barcodes', lambda *a, **kw: [])
    decoder = Decoder(assets_root() / 'models')
    base = time.monotonic()
    first = decoder.scan(qr_frame, now=base)
    assert first['fallback'] and not first['accepted']
    second = decoder.scan(qr_frame, now=base+1.1)
    assert second['accepted'] == ['QR-LIVE-FACTORY-001']


def test_confirmation_is_bounded():
    c = Confirmation()
    for index in range(1000):
        c.observe([str(index)], index*.001)
    assert len(c.states) == 256
    c.observe([], 100)
    assert not c.states


def test_empty_scene_does_not_call_wechat_every_frame():
    decoder = Decoder(assets_root() / 'models')
    base = time.monotonic()
    image = np.full((360, 640, 3), 255, np.uint8)
    for i in range(100):
        decoder.scan(image, now=base+i*.1)
    assert decoder.scans == 100
    assert 1 <= decoder.fallbacks <= 7


@pytest.mark.parametrize('roi', [[0, 0, 0, 1], [0, 0, 2, 1], [float('nan'), 0, 1, 1], [0, 0, 1]])
def test_invalid_roi(roi):
    with pytest.raises(ValueError):
        validate_roi(roi)


def test_model_checksum_is_required(tmp_path):
    folder = assets_root() / 'models'
    manifest = json.loads((folder / 'manifest.json').read_text('utf-8'))
    for name in manifest['files']:
        shutil.copyfile(folder / name, tmp_path / name)
    shutil.copyfile(folder / 'manifest.json', tmp_path / 'manifest.json')
    (tmp_path / 'sr_2021nov.caffemodel').write_bytes(b'bad model')
    with pytest.raises(RuntimeError, match='checksum'):
        Decoder(tmp_path)
