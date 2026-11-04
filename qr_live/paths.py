import os
from pathlib import Path
import sys


def assets_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets'


def data_root(override=None):
    root = Path(override) if override else Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'QRLiveScanner'
    root.mkdir(parents=True, exist_ok=True)
    return root
