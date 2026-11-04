"""Fetch only public OpenCV model assets at a pinned revision. Verify upstream IDs."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'b1af2a783943be8f52303c65eafda80ff7447462'
REPOSITORY = 'opencv/qrcode_wechatqrcode'
NAMES = ['detect_2021nov.prototxt', 'detect_2021nov.caffemodel',
         'sr_2021nov.prototxt', 'sr_2021nov.caffemodel', 'LICENSE']


def main():
    folder = ROOT / 'assets/models'
    folder.mkdir(parents=True, exist_ok=True)
    base = f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/'
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{REPOSITORY}/tree/{REVISION}', timeout=30) as response:
        metadata = {entry['path']: entry for entry in json.load(response)}
    hashes = {}
    for name in NAMES:
        with urllib.request.urlopen(base+name, timeout=60) as response:
            content = response.read()
        entry = metadata[name]
        if entry.get('lfs'):
            actual, expected = hashlib.sha256(content).hexdigest(), entry['lfs']['oid']
        else:
            actual = hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()
            expected = entry['oid']
        if actual != expected:
            raise RuntimeError(f'Upstream checksum mismatch: {name}')
        (folder / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
        print(name, len(content), hashes[name])
    (folder / 'manifest.json').write_text(json.dumps({'repository': REPOSITORY,
        'revision': REVISION, 'files': hashes}, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
