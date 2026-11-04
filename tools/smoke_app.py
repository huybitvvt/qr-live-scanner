"""Exercise an actual source/frozen window using public synthetic inputs only."""
import argparse
import ctypes
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from PIL import ImageGrab


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe')
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--video', action='store_true')
    parser.add_argument('--name', default='smoke')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    root = project / 'artifacts' / args.name
    root.mkdir(parents=True, exist_ok=False)
    source = project / 'artifacts' / ('cycle.avi' if args.video else 'reference.png')
    command = [str(Path(args.exe).resolve())] if args.exe else [sys.executable, '-m', 'qr_live']
    command += ['--source', str(source), '--data-dir', str(root), '--quit-after', str(args.seconds)]
    process = subprocess.Popen(command, cwd=project)
    samples = []
    saved = False
    try:
        deadline = time.monotonic()+args.seconds+20
        while process.poll() is None and time.monotonic() < deadline:
            path = root / 'health.json'
            if path.is_file():
                value = json.loads(path.read_text('utf-8'))
                if not samples or value['uptime_seconds'] != samples[-1]['uptime_seconds']:
                    samples.append(value)
                if value['uptime_seconds'] >= 10 and not saved:
                    window = ctypes.windll.user32.FindWindowW(None, 'QR Live Scanner 1.0.0')
                    if window:
                        ImageGrab.grab(window=window).save(root / 'window.png')
                        saved = True
            time.sleep(.5)
        assert process.poll() == 0, f'Application exit: {process.poll()}'
        with sqlite3.connect(root / 'history.db') as connection:
            rows = connection.execute('SELECT text,engine FROM scans ORDER BY id').fetchall()
        expected = [f'QR-LIVE-{i:03}' for i in range(1, 9)] if args.video else ['QR-LIVE-FACTORY-001']
        assert [row[0] for row in rows] == expected, rows
        assert len(samples) >= 4
        log = (root / 'app.log').read_text('utf-8')
        assert 'ERROR' not in log and 'Traceback' not in log, log
        warm = [s for s in samples if s['uptime_seconds'] >= 10]
        report = {'exit_code': process.returncode, 'source': 'synthetic-video' if args.video else 'synthetic-image',
                  'duration_seconds': args.seconds, 'codes': rows,
                  'cpu_percent_mean': round(sum(s['cpu_percent'] for s in warm)/len(warm), 2),
                  'rss_mb_min': min(s['rss_mb'] for s in warm), 'rss_mb_max': max(s['rss_mb'] for s in warm),
                  'last': samples[-1], 'samples': samples, 'screenshot': saved}
        (root / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k != 'samples'}, indent=2))
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(10)


if __name__ == '__main__':
    main()
