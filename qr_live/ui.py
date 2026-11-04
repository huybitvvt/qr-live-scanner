import json
import logging
import os
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, timezone, timedelta

import cv2
from PIL import Image, ImageTk
import psutil

from . import __version__
from .paths import assets_root
from .runtime import Runtime
from .store import History

BG, CARD, INK, MUTED, BLUE = '#F3F6FA', '#FFFFFF', '#152238', '#526179', '#155DE9'


class Application:
    def __init__(self, root, args):
        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)
        self.folder, self.args = root, args
        self.window = tk.Tk()
        self.window.title(f'QR Live Scanner {__version__}')
        screen_w, screen_h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        self.window.geometry(f'{min(1120, screen_w-40)}x{min(820, screen_h-80)}+20+20')
        self.window.minsize(min(880, screen_w-40), min(640, screen_h-80))
        self.window.configure(bg=BG)
        try:
            self.window.iconbitmap(str(assets_root() / 'app.ico'))
        except tk.TclError:
            pass
        self.settings = self._load_settings()
        self.history = History(root)
        self.runtime = Runtime(assets_root() / 'models', root)
        self.frame_sequence = 0
        self.frame = None
        self.last_text = ''
        self.history_id = None
        self.started = time.monotonic()
        self.last_stats = self.last_history = 0
        self.last_cpu = (self.started, 0)
        self.metrics = {}
        self.drag = self.drag_box = None
        self.selecting = False
        self.closed = False
        self._layout()
        self._reload_history()
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<F5>', lambda _: self.open_camera())
        self.window.bind('<Escape>', lambda _: self.cancel_selection())
        self.window.after(150, self.open_camera)
        self.window.after(50, self._tick)
        if args.quit_after:
            self.window.after(round(args.quit_after*1000), self.close)

    def _load_settings(self):
        try:
            value = json.loads((self.folder / 'settings.json').read_text('utf-8'))
            if value.get('backend') not in {'DirectShow', 'Media Foundation'}:
                raise ValueError('Invalid backend')
            if not isinstance(value.get('camera'), int) or not 0 <= value['camera'] <= 9:
                raise ValueError('Invalid camera')
            from .engine import validate_roi
            value['roi'] = validate_roi(value.get('roi'))
            return value
        except (OSError, ValueError, TypeError, KeyError):
            return {'camera': 0, 'backend': 'DirectShow', 'roi': [0, 0, 1, 1]}

    def _save_settings(self):
        path = self.folder / 'settings.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.settings, indent=2), encoding='utf-8')
        temporary.replace(path)

    def _layout(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=INK, font=('Segoe UI', 11))
        style.configure('TButton', font=('Segoe UI', 11), padding=(12, 9), borderwidth=0)
        style.configure('Primary.TButton', background=BLUE, foreground='white')
        style.map('Primary.TButton', background=[('active', '#0E46B2')])
        style.configure('Treeview', rowheight=31, font=('Segoe UI', 10), background=CARD, fieldbackground=CARD)
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=7)
        style.map('Treeview', background=[('selected', '#DDE9FF')], foreground=[('selected', INK)])
        shell = tk.Frame(self.window, bg=BG)
        shell.pack(fill='both', expand=True, padx=24, pady=20)
        header = tk.Frame(shell, bg=BG)
        header.pack(fill='x')
        tk.Label(header, text='QR LIVE', bg=BG, fg=INK, font=('Segoe UI', 23, 'bold')).pack(side='left')
        tk.Label(header, text='QUÉT TỰ ĐỘNG · OFFLINE', bg=BG, fg=MUTED, font=('Segoe UI', 10, 'bold')).pack(side='left', padx=18)
        tk.Label(header, text=f'v{__version__}', bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(side='right')
        tk.Label(shell, text='Đưa tem vào camera. Mã được xác nhận và ghi lịch sử tự động.',
                 bg=BG, fg=MUTED, anchor='w', font=('Segoe UI', 11)).pack(fill='x', pady=(2, 15))
        toolbar = tk.Frame(shell, bg=BG)
        toolbar.pack(fill='x', pady=(0, 12))
        self.camera_var = tk.StringVar(value=f"Camera {self.settings['camera']}")
        self.backend_var = tk.StringVar(value=self.settings['backend'])
        ttk.Combobox(toolbar, textvariable=self.camera_var, state='readonly', width=12,
                     values=[f'Camera {i}' for i in range(10)]).pack(side='left', padx=(0, 8))
        ttk.Combobox(toolbar, textvariable=self.backend_var, state='readonly', width=19,
                     values=['DirectShow', 'Media Foundation']).pack(side='left', padx=(0, 8))
        ttk.Button(toolbar, text='Mở camera', command=self.open_camera, style='Primary.TButton').pack(side='left', padx=(0, 8))
        ttk.Button(toolbar, text='Dừng', command=self.stop_camera).pack(side='left')
        self.sound_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text='Âm báo', variable=self.sound_var).pack(side='right')
        body = tk.Frame(shell, bg=BG)
        body.pack(fill='both', expand=True)
        sidebar = tk.Frame(body, bg=BG)
        sidebar.pack(side='right', fill='both', padx=(16, 0))
        camera_panel = tk.Frame(body, bg=BG)
        camera_panel.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(camera_panel, bg='#101B2D', highlightthickness=0, height=120, width=300)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<ButtonPress-1>', self._select_start)
        self.canvas.bind('<B1-Motion>', self._select_move)
        self.canvas.bind('<ButtonRelease-1>', self._select_end)
        self.canvas.create_text(350, 150, text='ĐANG MỞ CAMERA…', fill='#CDD8E8', font=('Segoe UI', 15))
        camera_footer = tk.Frame(camera_panel, bg=BG)
        camera_footer.pack(fill='x', pady=(8, 10))
        self.status_var = tk.StringVar(value='Đang khởi động…')
        tk.Label(shell, textvariable=self.status_var, bg=BG, fg=INK, anchor='w', font=('Segoe UI', 10)).pack(fill='x', pady=(8, 0))
        ttk.Button(camera_footer, text='Toàn khung', command=self.reset_roi).pack(side='right')
        ttk.Button(camera_footer, text='Chọn vùng QR', command=self.select_roi).pack(side='right', padx=8)
        result = tk.Frame(sidebar, bg=CARD, padx=14, pady=10)
        result.pack(fill='x')
        result_top = tk.Frame(result, bg=CARD)
        result_top.pack(fill='x')
        tk.Label(result_top, text='MÃ VỪA XÁC NHẬN', bg=CARD, fg=MUTED, font=('Segoe UI', 9, 'bold')).pack(side='left')
        self.engine_var = tk.StringVar(value='Chờ QR xuất hiện')
        tk.Label(result_top, textvariable=self.engine_var, bg=CARD, fg=MUTED, font=('Segoe UI', 9)).pack(side='right')
        self.code = tk.Text(result, height=4, width=1, wrap='word', bg=CARD, fg=INK,
                            font=('Consolas', 16), relief='flat', borderwidth=0, takefocus=True)
        self.code.insert('1.0', '—')
        self.code.configure(state='disabled')
        self.code.pack(fill='x', pady=(5, 0))
        ttk.Button(result, text='Sao chép', command=self.copy).pack(anchor='e', pady=(5, 0))
        history_bar = tk.Frame(sidebar, bg=BG)
        history_bar.pack(fill='x', pady=(12, 7))
        tk.Label(history_bar, text='LỊCH SỬ QUÉT', bg=BG, fg=INK, font=('Segoe UI', 10, 'bold')).pack(side='left')
        ttk.Button(history_bar, text='Xuất CSV', command=self.export).pack(side='right')
        table = tk.Frame(sidebar, bg=CARD)
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('time', 'code', 'engine'), show='headings', height=3)
        for column, text, width in [('time', 'Thời gian', 100), ('code', 'Nội dung QR', 170), ('engine', 'Bộ đọc', 90)]:
            self.tree.heading(column, text=text)
            self.tree.column(column, width=width, minwidth=65, stretch=column == 'code')
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<Double-1>', lambda _: self.copy_selected())
        self.tree.bind('<Control-c>', lambda _: self.copy_selected())
        self.stats_var = tk.StringVar(value='ZXing-C++ + WeChatQRCode  |  Dữ liệu chỉ lưu trên máy')
        tk.Label(shell, textvariable=self.stats_var, bg=BG, fg=MUTED, anchor='w', font=('Segoe UI', 9)).pack(fill='x', pady=(10, 0))

    def open_camera(self):
        try:
            previous = (self.settings['camera'], self.settings['backend'])
            profiles = self.settings.setdefault('profiles', {})
            profiles[f'{previous[0]}:{previous[1]}'] = self.settings['roi']
            self.settings['camera'] = int(self.camera_var.get().split()[-1])
            self.settings['backend'] = self.backend_var.get()
            current = (self.settings['camera'], self.settings['backend'])
            if current != previous:
                self.settings['roi'] = profiles.get(f'{current[0]}:{current[1]}', [0, 0, 1, 1])
            self._save_settings()
            source = self.args.source if self.args.source is not None else self.settings['camera']
            if isinstance(source, str) and source.isdigit():
                source = int(source)
            self.runtime.start(source, self.settings['backend'], self.settings['roi'])
            self.frame_sequence = 0
            self.status_var.set('Đang kết nối camera và nạp bộ đọc…')
            logging.info('Camera started: index=%s driver=%s', self.settings['camera'], self.settings['backend'])
        except Exception as exc:
            logging.exception('Camera start failed')
            messagebox.showerror('Không mở được camera', str(exc), parent=self.window)

    def stop_camera(self):
        self.runtime.stop()
        self.frame = None
        self.canvas.delete('all')
        self.canvas.create_text(self.canvas.winfo_width()/2, self.canvas.winfo_height()/2,
            text='CAMERA ĐÃ DỪNG', fill='#CDD8E8', font=('Segoe UI', 15))
        self.status_var.set('Đã dừng camera và bộ đọc')

    def select_roi(self):
        if self.frame is not None:
            self.selecting = True
            self.canvas.configure(cursor='crosshair')
            self.status_var.set('Kéo chuột khoanh vùng tem QR. Esc để hủy.')

    def cancel_selection(self):
        self.selecting = False
        self.drag = None
        self.canvas.configure(cursor='')

    def reset_roi(self):
        self.settings['roi'] = [0, 0, 1, 1]
        self._save_settings()
        if self.runtime.running:
            self.open_camera()

    def _select_start(self, event):
        if self.selecting:
            self.drag = (event.x, event.y)

    def _select_move(self, event):
        if self.selecting and self.drag:
            self.drag_box = (*self.drag, event.x, event.y)

    def _select_end(self, event):
        if not self.selecting or not self.drag or not hasattr(self, 'geometry'):
            return
        x, y, width, height = self.geometry
        ax, ay = self.drag
        bx, by = event.x, event.y
        roi = [max(0, min(1, (min(ax, bx)-x)/width)), max(0, min(1, (min(ay, by)-y)/height)),
               max(0, min(1, (max(ax, bx)-x)/width)), max(0, min(1, (max(ay, by)-y)/height))]
        from .engine import validate_roi
        try:
            self.settings['roi'] = validate_roi(roi)
        except ValueError:
            self.status_var.set('Vùng quá nhỏ; chọn lại toàn bộ tem và viền trắng')
            return
        self.cancel_selection()
        self.drag_box = None
        self._save_settings()
        self.open_camera()

    def _draw(self):
        if self.frame is None:
            return
        h, w = self.frame.shape[:2]
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        scale = min(cw/w, ch/h)
        width, height = max(1, round(w*scale)), max(1, round(h*scale))
        x, y = (cw-width)/2, (ch-height)/2
        self.geometry = x, y, width, height
        preview = cv2.resize(self.frame, (width, height), interpolation=cv2.INTER_AREA)
        image = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        self.photo = ImageTk.PhotoImage(Image.fromarray(image))
        self.canvas.delete('all')
        self.canvas.create_image(x, y, anchor='nw', image=self.photo)
        a, b, c, d = self.settings['roi']
        self.canvas.create_rectangle(x+a*width, y+b*height, x+c*width, y+d*height, outline='#5AA7FF', width=2)
        result = self.runtime.latest_result
        if result and time.monotonic()-result['at'] < .7:
            for detection in result['detections']:
                coordinates = [(x+px*scale, y+py*scale) for px, py in detection['points']]
                self.canvas.create_polygon(coordinates, fill='', outline='#29E0A3', width=3)
        if self.drag_box:
            self.canvas.create_rectangle(*self.drag_box, outline='#FFE18D', width=3, dash=(5, 3))

    def _reload_history(self):
        rows = self.history.recent()
        latest = rows[0][0] if rows else 0
        if latest == self.history_id:
            return
        old_id = self.history_id
        self.history_id = latest
        self.tree.delete(*self.tree.get_children())
        for row_id, at, text, engine in rows:
            local = datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=7)))
            self.tree.insert('', 'end', iid=str(row_id), values=(local.strftime('%d/%m %H:%M:%S'), text[:500], engine))
        if rows:
            _, at, self.last_text, engine = rows[0]
            self.code.configure(state='normal')
            self.code.delete('1.0', 'end')
            self.code.insert('1.0', self.last_text)
            self.code.configure(state='disabled')
            local = datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=7)))
            self.engine_var.set(f'{engine} · {local:%H:%M:%S}')
            if old_id is not None and self.sound_var.get():
                self.window.bell()

    def copy(self):
        if self.last_text:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.last_text)
            self.status_var.set('Đã sao chép mã QR')

    def copy_selected(self):
        selection = self.tree.selection()
        if selection:
            row = self.history.connection.execute('SELECT text FROM scans WHERE id=?', (int(selection[0]),)).fetchone()
            if row:
                self.window.clipboard_clear()
                self.window.clipboard_append(row[0])

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension='.csv',
            initialfile=f'QR-{datetime.now():%Y%m%d-%H%M%S}.csv', filetypes=[('CSV', '*.csv')])
        if path:
            try:
                self.history.export(path)
                self.status_var.set('Đã xuất lịch sử CSV')
            except OSError as exc:
                messagebox.showerror('Không xuất được CSV', str(exc), parent=self.window)

    def _statistics(self, now):
        cpu_seconds = memory = 0
        parent = psutil.Process()
        for process in [parent, *parent.children(recursive=True)]:
            try:
                times = process.cpu_times()
                cpu_seconds += times.user+times.system
                memory += process.memory_info().rss
            except psutil.Error:
                pass
        previous_time, previous_cpu = self.last_cpu
        cpu = max(0, (cpu_seconds-previous_cpu)/max(.01, now-previous_time)*100/(psutil.cpu_count() or 1))
        self.last_cpu = now, cpu_seconds
        elapsed = int(now-self.started)
        result = self.runtime.latest_result or {}
        self.metrics = {'uptime_seconds': elapsed, 'cpu_percent': round(cpu, 1),
                        'rss_mb': round(memory/1024**2, 1), **self.runtime.diagnostics,
                        'last_decode_ms': result.get('elapsed_ms'), 'scans': result.get('scans', 0),
                        'fallbacks': result.get('fallbacks', 0), 'running': self.runtime.running}
        self.stats_var.set(f"CPU {cpu:.1f}%   |   RAM {memory/1024**2:.0f} MB   |   "
            f"Đọc {result.get('elapsed_ms', 0):.0f} ms   |   WeChat {result.get('fallbacks', 0)}/{result.get('scans', 0)} lượt   |   "
            f"{elapsed//3600:02}:{elapsed//60%60:02}:{elapsed%60:02}   |   OFFLINE")
        temporary = self.folder / 'health.tmp'
        temporary.write_text(json.dumps(self.metrics), encoding='utf-8')
        temporary.replace(self.folder / 'health.json')

    def _tick(self):
        if self.closed:
            return
        try:
            for item in self.runtime.poll():
                text = item.get('fatal') or item.get('error') or item.get('camera') or item.get('decoder')
                if text:
                    self.status_var.set(text)
                    logging.info('%s', text)
            if self.runtime.running and self.window.state() != 'iconic':
                item = self.runtime.shared.read(self.frame_sequence)
                if item:
                    self.frame_sequence, stamp, self.frame = item
                    self._draw()
            now = time.monotonic()
            if now-self.last_history > .3:
                self._reload_history()
                self.last_history = now
            if now-self.last_stats > 2:
                self.last_stats = now
                self._statistics(now)
        except Exception:
            logging.exception('UI update failed')
            self.status_var.set('Lỗi xử lý; xem app.log trong thư mục dữ liệu')
        self.window.after(50, self._tick)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.runtime.stop()
        self.history.close()
        logging.info('Application stopped normally')
        self.window.destroy()

    def run(self):
        self.window.mainloop()
