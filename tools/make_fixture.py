"""Public synthetic input, never uses camera or factory data."""
from pathlib import Path
import sys
import numpy as np
import cv2
import qrcode


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'artifacts')
    root.mkdir(parents=True, exist_ok=True)
    frame = np.full((720, 1280, 3), 238, np.uint8)
    qr = np.array(qrcode.make('QR-LIVE-FACTORY-001').convert('RGB'))
    h, w = qr.shape[:2]
    frame[180:180+h, 450:450+w] = cv2.cvtColor(qr, cv2.COLOR_RGB2BGR)
    cv2.putText(frame, 'QR LIVE / OFFLINE', (440, 130), cv2.FONT_HERSHEY_SIMPLEX, 1, (45, 65, 80), 2)
    cv2.imwrite(str(root / 'reference.png'), frame)
    blank = np.full_like(frame, 238)
    writer = cv2.VideoWriter(str(root / 'cycle.avi'), cv2.VideoWriter_fourcc(*'MJPG'), 15, (1280, 720))
    for index in range(8):
        current = blank.copy()
        qr = np.array(qrcode.make(f'QR-LIVE-{index+1:03}').convert('RGB'))
        h, w = qr.shape[:2]
        current[180:180+h, 450:450+w] = qr
        for _ in range(30):
            writer.write(blank)
        for _ in range(45):
            writer.write(current)
    writer.release()
    print(root / 'reference.png')


if __name__ == '__main__':
    main()
