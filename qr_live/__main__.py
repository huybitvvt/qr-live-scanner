import argparse
import ctypes
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing as mp
import sys

from .paths import data_root


def main():
    mp.freeze_support()
    parser = argparse.ArgumentParser(description='QR Live Scanner — offline ZXing + WeChat')
    parser.add_argument('--data-dir')
    parser.add_argument('--source', help='Camera index, image or video file')
    parser.add_argument('--quit-after', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = data_root(args.data_dir)
    instance = None
    if sys.platform == 'win32':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.restype = ctypes.c_void_p
        name = 'Local\\QRLiveScanner-'+hashlib.sha256(str(root.resolve()).lower().encode()).hexdigest()[:16]
        instance = kernel.CreateMutexW(None, False, name)
        if not instance:
            raise OSError('Cannot create application mutex')
        if ctypes.get_last_error() == 183:
            kernel.CloseHandle(ctypes.c_void_p(instance))
            from tkinter import messagebox
            messagebox.showinfo('QR Live Scanner', 'Ứng dụng đang mở. Chỉ chạy một cửa sổ cho mỗi thư mục dữ liệu.')
            return 0
    handler = RotatingFileHandler(root / 'app.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    logging.basicConfig(handlers=[handler], level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    from .ui import Application
    try:
        Application(root, args).run()
    except Exception:
        logging.exception('Application failed')
        from tkinter import messagebox
        messagebox.showerror('QR Live Scanner', f'Không mở được ứng dụng. Xem {root / "app.log"}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
