"""Native UI controls against the real inference process and synthetic camera."""
from argparse import Namespace
import json
from pathlib import Path
from types import SimpleNamespace
import tkinter.filedialog

from qr_live.ui import Application


def main():
    project = Path(__file__).resolve().parents[1]
    root = project / 'artifacts/controls'
    root.mkdir(parents=True, exist_ok=False)
    app = Application(root, Namespace(source=str(project / 'artifacts/reference.png'), quit_after=None))
    failures, verified = [], []

    def check():
        try:
            assert app.last_text == 'QR-LIVE-FACTORY-001', app.last_text
            app.copy()
            assert app.window.clipboard_get() == app.last_text
            verified.append('clipboard')
            tkinter.filedialog.asksaveasfilename = lambda **kw: str(root / 'history.csv')
            app.export()
            assert 'QR-LIVE-FACTORY-001' in (root / 'history.csv').read_text('utf-8-sig')
            verified.append('csv')
            x, y, width, height = app.geometry
            app.select_roi()
            app._select_start(SimpleNamespace(x=x+.25*width, y=y+.15*height))
            app._select_end(SimpleNamespace(x=x+.8*width, y=y+.9*height))
            assert all(abs(a-b) < .001 for a, b in zip(app.settings['roi'], [.25, .15, .8, .9]))
            verified.append('roi-save-and-worker-restart')
            app.window.after(2500, finish)
        except Exception as exc:
            failures.append(repr(exc))
            app.close()

    def finish():
        try:
            assert app.runtime.latest_result and app.runtime.latest_result['detections']
            verified.append('real-qr-after-roi')
            app.stop_camera()
            assert not app.runtime.running
            app.reset_roi()
            assert app.settings['roi'] == [0, 0, 1, 1]
            verified.extend(['stop', 'roi-reset'])
        except Exception as exc:
            failures.append(repr(exc))
        finally:
            app.close()

    app.window.after(5000, check)
    app.run()
    assert not failures, failures
    print(json.dumps({'verified': verified}))


if __name__ == '__main__':
    main()
