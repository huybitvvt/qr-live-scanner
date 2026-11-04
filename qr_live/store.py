import csv
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


class History:
    def __init__(self, root: Path):
        self.connection = sqlite3.connect(root / 'history.db')
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS scans '
            '(id INTEGER PRIMARY KEY, at TEXT NOT NULL, text TEXT NOT NULL, engine TEXT NOT NULL)')
        self.prune()

    def append(self, text, engine):
        at = datetime.now(timezone.utc).isoformat()
        with self.connection:
            cursor = self.connection.execute('INSERT INTO scans(at,text,engine) VALUES(?,?,?)', (at, text, engine))
        return cursor.lastrowid, at, text, engine

    def recent(self):
        return self.connection.execute('SELECT id,at,text,engine FROM scans ORDER BY id DESC LIMIT 200').fetchall()

    def prune(self):
        with self.connection:
            self.connection.execute("DELETE FROM scans WHERE at < strftime('%Y-%m-%dT%H:%M:%S','now','-90 days') "
                'OR id <= (SELECT coalesce(max(id),0)-100000 FROM scans)')
        self.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    def export(self, path):
        with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Thời gian (Việt Nam)', 'Nội dung QR', 'Bộ đọc'])
            for at, text, engine in self.connection.execute('SELECT at,text,engine FROM scans ORDER BY id'):
                # CSV cells must not execute spreadsheet formulas from untrusted QR payloads.
                safe = "'"+text if text.lstrip().startswith(('=', '+', '-', '@')) else text
                from datetime import timedelta
                local = datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=7)))
                writer.writerow([local.strftime('%Y-%m-%d %H:%M:%S'), safe, engine])

    def close(self):
        self.connection.close()
