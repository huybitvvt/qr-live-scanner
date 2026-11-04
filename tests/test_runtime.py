import multiprocessing as mp
import sqlite3
import time

import cv2
import numpy as np
import qrcode

from qr_live.paths import assets_root
from qr_live.runtime import Runtime, SharedFrame
from qr_live.store import History


def test_shared_frame_keeps_only_latest():
    shared = SharedFrame(mp.get_context('spawn'))
    for number in range(20):
        shared.write(np.full((100, 150, 3), number, np.uint8))
    seq, stamp, frame = shared.read()
    assert seq == 20 and frame[0, 0, 0] == 19
    assert shared.read(seq) is None


def test_spawn_pipeline_and_decoder_recovery(tmp_path):
    image = np.array(qrcode.make('PIPELINE-OFFLINE-001').convert('RGB'))
    source = tmp_path / 'source.png'
    cv2.imwrite(str(source), image)
    runtime = Runtime(assets_root() / 'models', tmp_path)
    runtime.start(str(source))
    try:
        deadline = time.monotonic()+18
        while time.monotonic() < deadline:
            messages = runtime.poll()
            assert not any('fatal' in item for item in messages), messages
            if runtime.latest_result and runtime.latest_result['scans'] >= 4:
                break
            time.sleep(.05)
        assert runtime.latest_result and runtime.latest_result['scans'] >= 4
        with sqlite3.connect(tmp_path / 'history.db') as connection:
            assert connection.execute('SELECT text FROM scans').fetchall() == [('PIPELINE-OFFLINE-001',)]
        old_pid = runtime.decoder.pid
        runtime.decoder.terminate()
        runtime.decoder.join(2)
        runtime.started -= 20
        runtime.last_health = 0
        runtime.poll()
        assert runtime.decoder.pid != old_pid
        assert runtime.diagnostics['decoder_restarts'] == 1
    finally:
        camera, decoder = runtime.camera, runtime.decoder
        runtime.stop()
        assert (camera is None or not camera.is_alive()) and (decoder is None or not decoder.is_alive())


def test_history_csv_persistence_and_formula_escape(tmp_path):
    history = History(tmp_path)
    history.append('=CMD()', 'ZXing-C++')
    history.append('Mã thử tiếng Việt', 'WeChatQRCode')
    path = tmp_path / 'export.csv'
    history.export(path)
    assert "'=CMD()" in path.read_text('utf-8-sig')
    history.close()
    reopened = History(tmp_path)
    assert len(reopened.recent()) == 2
    reopened.close()
