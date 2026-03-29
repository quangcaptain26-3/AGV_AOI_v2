"""
agv_log.py
Ứng dụng Desktop theo dõi tác vụ AGV (Automated Guided Vehicle)
Đọc file .log và .ini để thống kê số lượt Cấp liệu / Thu hồi theo từng chuyền
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import configparser
import json
import re
import os
import glob
from collections import defaultdict
from datetime import datetime
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import math


# ─── Hằng số màu sắc ─────────────────────────────────────────────────────────
COLOR_BG         = "#F0F4F8"   # Nền tổng thể
COLOR_HEADER_BG  = "#1A3C5E"   # Nền thanh tiêu đề
COLOR_HEADER_FG  = "#FFFFFF"   # Chữ tiêu đề
COLOR_SUPPLY     = "#2E7D32"   # Xanh lá – Cấp liệu
COLOR_RETRIEVE   = "#1565C0"   # Xanh dương – Thu hồi
COLOR_TOTAL      = "#4A4A4A"   # Xám đậm – Tổng
COLOR_ROW_EVEN   = "#FFFFFF"
COLOR_ROW_ODD    = "#EBF3FB"
COLOR_BTN        = "#1565C0"
COLOR_BTN_FG     = "#FFFFFF"
COLOR_STATUS_OK  = "#2E7D32"
COLOR_STATUS_ERR = "#C62828"
FONT_TITLE   = ("Segoe UI", 13, "bold")
FONT_LABEL   = ("Segoe UI", 10)
FONT_LABEL_B = ("Segoe UI", 10, "bold")
FONT_TABLE   = ("Segoe UI", 10)
FONT_BTN     = ("Segoe UI", 10, "bold")


# ─── Lớp đọc & phân tích cấu hình ────────────────────────────────────────────
class ConfigLoader:
    """Đọc file .ini và xây dựng bản đồ điểm -> tên máy."""

    def __init__(self, ini_path: str):
        self.ini_path   = ini_path
        self.server_ip  = ""
        self.port       = ""
        # Bản đồ: mã điểm (str) -> {"name": tên máy, "type": "down"|"recv"}
        self.point_map: dict[str, dict] = {}
        self.machine_names: list[str]   = []
        self._load()

    def _load(self):
        cfg = configparser.ConfigParser()
        # utf-8-sig tự động loại bỏ BOM nếu file được lưu bằng Notepad Windows
        cfg.read(self.ini_path, encoding="utf-8-sig")

        # Đọc thông tin kết nối
        self.server_ip = cfg.get("Settings", "server_ip", fallback="N/A")
        self.port      = cfg.get("Settings", "port",      fallback="N/A")

        # Duyệt từng section (bỏ qua Settings và PATH)
        skip = {"settings", "path"}
        for section in cfg.sections():
            if section.lower() in skip:
                continue

            machine_name = section  # Tên máy chính là tên section

            # Lấy down_point (Cấp liệu) – có thể nhiều giá trị, phân cách phẩy
            if cfg.has_option(section, "down_point"):
                for pt in cfg.get(section, "down_point").split(","):
                    pt = pt.strip()
                    if pt:
                        self.point_map[pt] = {"name": machine_name, "type": "down"}

            # Lấy recv_up_point (Thu hồi)
            if cfg.has_option(section, "recv_up_point"):
                for pt in cfg.get(section, "recv_up_point").split(","):
                    pt = pt.strip()
                    if pt:
                        self.point_map[pt] = {"name": machine_name, "type": "recv"}

            if machine_name not in self.machine_names:
                self.machine_names.append(machine_name)


# ─── Lớp xử lý file .log ─────────────────────────────────────────────────────
class LogParser:
    """Quét tất cả file .log trong thư mục và thống kê tác vụ."""

    # Regex tách một cặp [timestamp] + khối JSON ngay sau
    _BLOCK_RE = re.compile(
        r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*'   # [timestamp]
        r'POST\s+\S+\s*'                                        # POST http://...
        r'\[(?:\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*'  # [timestamp] lần 2
        r'(\{.*?\})\s*(?=\[|$)',                                # khối JSON
        re.DOTALL
    )

    def __init__(self, log_dir: str, config: ConfigLoader):
        self.log_dir  = log_dir
        self.config   = config
        # Kết quả: {machine_name: {"down": int, "recv": int}}
        self.stats: dict[str, dict] = defaultdict(lambda: {"down": 0, "recv": 0})
        self.total_tasks    = 0
        self.skipped_errors = 0
        self.files_read: list[str] = []
        self.time_series: list[dict] = []

    def parse_files(self, log_files: list[str]):
        """Quét các file .log được lựa chọn và trả về DataFrame thống kê."""
        self.stats          = defaultdict(lambda: {"down": 0, "recv": 0})
        self.total_tasks    = 0
        self.skipped_errors = 0
        self.files_read     = []
        self.time_series    = []

        for fpath in log_files:
            self.files_read.append(os.path.basename(fpath))
            self._parse_file(fpath)

        return self._build_dataframe()

    def _parse_file(self, fpath: str):
        """Đọc một file .log, tách từng tác vụ và phân loại điểm."""
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            self.skipped_errors += 1
            return

        # Tách nội dung thành các cặp: (timestamp, json_str)
        # File log có dạng:
        #   [2026-03-18 00:32:52] POST http://...
        #   [2026-03-18 00:32:52] { ... }
        # Ta dùng regex đơn giản hơn: tìm tất cả khối JSON sau timestamp

        # Bước 1: Tách theo pattern "[timestamp] POST ..." rồi lấy phần JSON phía sau
        segments = re.split(
            r'(\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*POST\s+[^\r\n]+)',
            content
        )

        # segments sẽ là: ['', header1, json_text1, header2, json_text2, ...]
        i = 1
        while i < len(segments) - 1:
            header   = segments[i]
            json_raw = segments[i + 1]
            i += 2

            # Trích xuất thời gian từ header
            dt = datetime.now()
            time_match = re.search(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]', header)
            if time_match:
                try:
                    dt = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            # Tìm khối JSON đầu tiên trong json_raw
            # (bắt đầu từ dấu '{' đầu tiên sau [timestamp])
            # json_raw có thể chứa [timestamp] thứ hai ở đầu
            json_match = re.search(r'(\{.*)', json_raw, re.DOTALL)
            if not json_match:
                self.skipped_errors += 1
                continue

            json_str = json_match.group(1).strip()

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Cố gắng cắt bớt nếu JSON bị nối nhiều record
                # Tìm vị trí kết thúc JSON hợp lệ đầu tiên
                data = self._try_extract_json(json_str)
                if data is None:
                    self.skipped_errors += 1
                    continue

            self._process_task(data, dt)

    def _try_extract_json(self, text: str):
        """Cố trích xuất JSON hợp lệ từ chuỗi có thể bị cắt hoặc nối."""
        depth = 0
        start = text.find('{')
        if start == -1:
            return None
        for idx, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:idx + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    def _process_task(self, data: dict, dt: datetime):
        """Duyệt danh sách points trong một tác vụ, cập nhật thống kê."""
        points = data.get("points", [])
        if not isinstance(points, list):
            return

        self.total_tasks += 1

        # Tập hợp máy đã được đếm trong tác vụ này để tránh đếm trùng
        # (nếu một tác vụ có nhiều điểm cùng máy thì vẫn đếm từng điểm)
        for item in points:
            pt_code = str(item.get("point", "")).strip()
            if pt_code in self.config.point_map:
                info = self.config.point_map[pt_code]
                mname = info["name"]
                ptype = info["type"]
                if ptype == "down":
                    self.stats[mname]["down"] += 1
                else:
                    self.stats[mname]["recv"] += 1
                self.time_series.append({"time": dt, "machine": mname, "type": ptype})

    def _build_dataframe(self) -> pd.DataFrame:
        """Chuyển dict thống kê thành DataFrame có đủ cột."""
        rows = []
        for mname in self.config.machine_names:
            d = self.stats.get(mname, {"down": 0, "recv": 0})
            rows.append({
                "Tên Chuyền": mname,
                "Cấp liệu":  d["down"],
                "Thu hồi":   d["recv"],
                "Tổng cộng": d["down"] + d["recv"],
            })

        # Thêm các máy xuất hiện trong log nhưng không có trong ini
        for mname, d in self.stats.items():
            if mname not in self.config.machine_names:
                rows.append({
                    "Tên Chuyền": mname + " (*)",
                    "Cấp liệu":  d["down"],
                    "Thu hồi":   d["recv"],
                    "Tổng cộng": d["down"] + d["recv"],
                })

        return pd.DataFrame(rows, columns=["Tên Chuyền", "Cấp liệu", "Thu hồi", "Tổng cộng"])


# ─── Giao diện chính ──────────────────────────────────────────────────────────
class AGVLogApp(tk.Tk):
    """Cửa sổ chính của ứng dụng theo dõi tác vụ AGV."""

    def __init__(self):
        super().__init__()
        self.title("AGV Task Monitor")
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)
        self.minsize(780, 520)

        # Đường dẫn mặc định: cùng thư mục với file script
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.ini_path = os.path.join(self.base_dir, "setting.ini")

        # Nạp cấu hình
        self.config_loader = ConfigLoader(self.ini_path)
        self.log_parser    = LogParser(self.base_dir, self.config_loader)

        # Xây dựng giao diện
        self._build_ui()

        # Tự động refresh khi khởi động
        self.after(100, self.refresh)

    # ── Xây dựng toàn bộ layout ──────────────────────────────────────────────
    def _build_ui(self):
        """Chia layout thành 4 vùng chính bằng grid."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)  # Header – cố định
        self.rowconfigure(1, weight=1)  # Bảng – co giãn
        self.rowconfigure(2, weight=1)  # Biểu đồ - co giãn
        self.rowconfigure(3, weight=0)  # Footer – cố định

        self._build_header()   # Hàng 0
        self._build_table()    # Hàng 1
        self._build_chart()    # Hàng 2
        self._build_footer()   # Hàng 3

    # ── Vùng header: thông tin Server ────────────────────────────────────────
    def _build_header(self):
        frame = tk.Frame(self, bg=COLOR_HEADER_BG, pady=10)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)

        # Tiêu đề ứng dụng
        tk.Label(
            frame, text="🤖  AGV Task Monitor",
            font=FONT_TITLE, bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG
        ).grid(row=0, column=0, sticky="w", padx=18, pady=2)

        # Panel thông tin server (bên phải)
        info_frame = tk.Frame(frame, bg=COLOR_HEADER_BG)
        info_frame.grid(row=0, column=1, sticky="e", padx=18)

        tk.Label(
            info_frame, text="Server IP:", font=FONT_LABEL_B,
            bg=COLOR_HEADER_BG, fg="#A8C8E8"
        ).grid(row=0, column=0, sticky="e")

        self.lbl_ip = tk.Label(
            info_frame, text=self.config_loader.server_ip,
            font=FONT_LABEL, bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG
        )
        self.lbl_ip.grid(row=0, column=1, sticky="w", padx=(4, 18))

        tk.Label(
            info_frame, text="Port:", font=FONT_LABEL_B,
            bg=COLOR_HEADER_BG, fg="#A8C8E8"
        ).grid(row=0, column=2, sticky="e")

        self.lbl_port = tk.Label(
            info_frame, text=self.config_loader.port,
            font=FONT_LABEL, bg=COLOR_HEADER_BG, fg=COLOR_HEADER_FG
        )
        self.lbl_port.grid(row=0, column=3, sticky="w", padx=(4, 0))

        # Dòng ghi chú cấu hình
        tk.Label(
            frame,
            text=f"Config: {os.path.basename(self.ini_path)}  |  "
                 f"Machines: {len(self.config_loader.machine_names)}",
            font=("Segoe UI", 8), bg=COLOR_HEADER_BG, fg="#7FB3D3"
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=18)

    # ── Vùng giữa: Bảng thống kê Treeview ────────────────────────────────────
    def _build_table(self):
        outer = tk.Frame(self, bg=COLOR_BG)
        outer.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        # Tiêu đề bảng + legend màu
        legend_frame = tk.Frame(outer, bg=COLOR_BG)
        legend_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        tk.Label(
            legend_frame, text="Thống kê tác vụ theo chuyền",
            font=FONT_LABEL_B, bg=COLOR_BG, fg=COLOR_TOTAL
        ).pack(side="left")

        # Legend
        for color, label in [(COLOR_SUPPLY, "Cấp liệu"), (COLOR_RETRIEVE, "Thu hồi")]:
            dot = tk.Frame(legend_frame, bg=color, width=12, height=12)
            dot.pack(side="left", padx=(16, 3), pady=3)
            tk.Label(
                legend_frame, text=label, font=("Segoe UI", 9),
                bg=COLOR_BG, fg=color
            ).pack(side="left")

        # Frame chứa Treeview + Scrollbar
        tv_frame = tk.Frame(outer, bg=COLOR_BG)
        tv_frame.grid(row=1, column=0, sticky="nsew")
        tv_frame.columnconfigure(0, weight=1)
        tv_frame.rowconfigure(0, weight=1)

        # Scrollbar dọc
        vsb = ttk.Scrollbar(tv_frame, orient="vertical")
        vsb.grid(row=0, column=1, sticky="ns")

        # Treeview – định nghĩa 4 cột
        cols = ("Tên Chuyền", "Cấp liệu", "Thu hồi", "Tổng cộng")
        self.tree = ttk.Treeview(
            tv_frame, columns=cols, show="headings",
            yscrollcommand=vsb.set, selectmode="browse"
        )
        vsb.config(command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Định dạng heading và cột
        col_cfg = {
            "Tên Chuyền": {"width": 180, "anchor": "w",   "fg": COLOR_TOTAL},
            "Cấp liệu":   {"width": 100, "anchor": "center", "fg": COLOR_SUPPLY},
            "Thu hồi":    {"width": 100, "anchor": "center", "fg": COLOR_RETRIEVE},
            "Tổng cộng":  {"width": 100, "anchor": "center", "fg": COLOR_TOTAL},
        }
        for col, cfg in col_cfg.items():
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=cfg["width"], anchor=cfg["anchor"], minwidth=60)

        # Tag màu sắc cho từng dòng
        self.tree.tag_configure("even", background=COLOR_ROW_EVEN)
        self.tree.tag_configure("odd",  background=COLOR_ROW_ODD)

        # Style Treeview tổng thể
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            font=FONT_TABLE, rowheight=26,
            background=COLOR_ROW_EVEN, fieldbackground=COLOR_ROW_EVEN,
            foreground=COLOR_TOTAL
        )
        style.configure(
            "Treeview.Heading",
            font=FONT_LABEL_B, background="#D6E4F0",
            foreground=COLOR_HEADER_BG, relief="flat"
        )
        style.map("Treeview", background=[("selected", "#BBDEFB")])

        # Biến sắp xếp
        self._sort_col = None
        self._sort_asc = True

    # ── Vùng giữa: Biểu đồ đường (Line Chart) ───────────────────────────────
    def _build_chart(self):
        self.chart_frame = tk.Frame(self, bg=COLOR_BG)
        self.chart_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.chart_frame.columnconfigure(0, weight=1)
        self.chart_frame.rowconfigure(1, weight=1)

        # Header nhỏ giới thiệu biểu đồ
        header_frame = tk.Frame(self.chart_frame, bg=COLOR_BG)
        header_frame.grid(row=0, column=0, sticky="w", pady=(5, 5))
        tk.Label(
            header_frame, text="📊 Biểu đồ Thống kê Nhịp độ Hoạt động (Theo Ngày từng Chuyền)",
            font=FONT_LABEL_B, bg=COLOR_BG, fg=COLOR_HEADER_BG
        ).pack(side="left")

        # Cấu trúc cho phép cuộn nội dung Canvas (vì có nhiều grid subplots)
        self.chart_canvas = tk.Canvas(self.chart_frame, bg=COLOR_BG, highlightthickness=0)
        self.chart_vsb = ttk.Scrollbar(self.chart_frame, orient="vertical", command=self.chart_canvas.yview)
        
        self.chart_canvas.grid(row=1, column=0, sticky="nsew")
        self.chart_vsb.grid(row=1, column=1, sticky="ns")
        self.chart_canvas.configure(yscrollcommand=self.chart_vsb.set)

        self.inner_chart_frame = tk.Frame(self.chart_canvas, bg=COLOR_BG)
        self.canvas_window_id = self.chart_canvas.create_window((0, 0), window=self.inner_chart_frame, anchor="nw")

        def _on_frame_configure(event):
            self.chart_canvas.configure(scrollregion=self.chart_canvas.bbox("all"))
        self.inner_chart_frame.bind("<Configure>", _on_frame_configure)

        def _on_canvas_configure(event):
            self.chart_canvas.itemconfig(self.canvas_window_id, width=event.width)
        self.chart_canvas.bind("<Configure>", _on_canvas_configure)

        # Hỗ trợ scroll chuột giữa
        def _on_mousewheel(event):
            self.chart_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_mouse(_):
            self.chart_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mouse(_):
            self.chart_canvas.unbind_all("<MouseWheel>")
            
        self.chart_canvas.bind("<Enter>", _bind_mouse)
        self.chart_canvas.bind("<Leave>", _unbind_mouse)

        self.fig = Figure(figsize=(9, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.inner_chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _update_chart(self):
        self.fig.clf() # Xóa toàn bộ figure để vẽ lại các grid

        if not self.log_parser.time_series:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "Không có dữ liệu thời gian", ha='center', va='center', fontdict={'fontsize': 10})
            self.canvas.draw()
            return

        df = pd.DataFrame(self.log_parser.time_series)
        df['time'] = pd.to_datetime(df['time'])

        # Lấy danh sách các máy
        machines = sorted(df['machine'].unique())
        n_machines = len(machines)
        
        cols = 3 if n_machines >= 3 else (2 if n_machines == 2 else 1)
        rows = math.ceil(n_machines / cols)
        
        # Điều chỉnh chiều cao linh hoạt theo số hàng (rows)
        fig_height = max(3.5, rows * 2.5)
        self.fig.set_size_inches(9, fig_height)
        
        self.plot_lines = []
        
        for i, mname in enumerate(machines):
            ax = self.fig.add_subplot(rows, cols, i + 1)
            m_df = df[df['machine'] == mname]
            
            # Resample theo Daily cho riêng máy này
            m_df_idx = m_df.set_index('time')
            m_df_down = m_df_idx[m_df_idx['type'] == 'down'].resample('D').size()
            m_df_recv = m_df_idx[m_df_idx['type'] == 'recv'].resample('D').size()

            has_data = False
            if not m_df_down.empty:
                line_down = ax.plot(m_df_down.index, m_df_down.values, marker='o', color=COLOR_SUPPLY, label='Cấp liệu')[0]
                self.plot_lines.append((line_down, mname, 'Cấp liệu'))
                has_data = True
            if not m_df_recv.empty:
                line_recv = ax.plot(m_df_recv.index, m_df_recv.values, marker='s', color=COLOR_RETRIEVE, label='Thu hồi')[0]
                self.plot_lines.append((line_recv, mname, 'Thu hồi'))
                has_data = True
                
            ax.set_title(f"Chuyền: {mname}", fontdict={'fontsize': 10, 'fontweight': 'bold'})
            
            # Label ngày/tháng
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
            for label in ax.get_xticklabels():
                label.set_rotation(30)
                label.set_ha('right')
                label.set_fontsize(8)
            for label in ax.get_yticklabels():
                label.set_fontsize(8)

            ax.grid(True, linestyle='--', alpha=0.6)
            if i == 0 and has_data:
                ax.legend(fontsize=8)
                
        self.fig.tight_layout()
        
        # --- Bắt đầu phần Hover Annotate ---
        annot = self.fig.text(0, 0, "", bbox=dict(boxstyle="round,pad=0.4", fc="#FFFFE0", ec="#333333", alpha=0.9), visible=False, zorder=100, fontdict={'fontsize': 9})
        
        def _on_hover(event):
            vis = annot.get_visible()
            if event.inaxes:
                for line, mname, ltype in self.plot_lines:
                    if line.axes == event.inaxes:
                        cont, ind = line.contains(event)
                        if cont:
                            idx = ind["ind"][0] # Lấy index của điểm được hover
                            x_val = line.get_xdata()[idx]
                            y_val = line.get_ydata()[idx]
                            
                            date_str = mdates.num2date(x_val).strftime("%d/%m/%Y")
                            text = f"Máy: {mname}\n{ltype}: {int(y_val)} lần\nNgày: {date_str}"
                            
                            annot.set_text(text)
                            
                            # Tính tọa độ tương đối từ 0-1 cho fig.text
                            x_fig = event.x / self.fig.bbox.width
                            y_fig = event.y / self.fig.bbox.height
                            
                            # Dịch tooltip lệch một chút để không che chuột
                            annot.set_position((x_fig + 0.015, y_fig + 0.015))
                            annot.set_visible(True)
                            self.canvas.draw_idle()
                            return
            
            if vis:
                annot.set_visible(False)
                self.canvas.draw_idle()

        if hasattr(self, 'cid_hover'):
            self.fig.canvas.mpl_disconnect(self.cid_hover)
        self.cid_hover = self.fig.canvas.mpl_connect("motion_notify_event", _on_hover)
        # --- Kết thúc phần Hover Annotate ---

        self.canvas.draw()

        # Ép Widget thay đổi chiều cao để tk.Canvas cập nhật ScrollRegion
        self.canvas.get_tk_widget().configure(height=int(fig_height * self.fig.dpi))
        self.inner_chart_frame.update_idletasks()
        self.chart_canvas.configure(scrollregion=self.chart_canvas.bbox("all"))

    # ── Vùng footer: nút bấm + trạng thái ───────────────────────────────────
    def _build_footer(self):
        frame = tk.Frame(self, bg="#DDE8F0", pady=8)
        frame.grid(row=3, column=0, sticky="ew")
        frame.columnconfigure(2, weight=1)

        # Nút Chọn Files
        self.btn_select = tk.Button(
            frame, text="📂  Chọn Files",
            font=FONT_BTN, bg="#E65100", fg=COLOR_BTN_FG,
            relief="flat", padx=14, pady=5,
            activebackground="#BF360C", activeforeground="white",
            cursor="hand2",
            command=self.select_files
        )
        self.btn_select.grid(row=0, column=0, padx=(14, 5))

        # Nút Refresh
        self.btn_refresh = tk.Button(
            frame, text="🔄  Refresh",
            font=FONT_BTN, bg=COLOR_BTN, fg=COLOR_BTN_FG,
            relief="flat", padx=14, pady=5,
            activebackground="#0D47A1", activeforeground="white",
            cursor="hand2",
            command=self.refresh
        )
        self.btn_refresh.grid(row=0, column=1, padx=(5, 14))

        # Nhãn trạng thái
        self.lbl_status = tk.Label(
            frame, text="Vui lòng chọn file log...",
            font=("Segoe UI", 9), bg="#DDE8F0", fg="#555555",
            anchor="w"
        )
        self.lbl_status.grid(row=0, column=2, sticky="ew", padx=6)

        # Nhãn thời gian cập nhật
        self.lbl_time = tk.Label(
            frame, text="",
            font=("Segoe UI", 8), bg="#DDE8F0", fg="#888888"
        )
        self.lbl_time.grid(row=0, column=3, sticky="e", padx=14)
        
        self.selected_files = []

    def select_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Chọn các file .log",
            filetypes=[("Log Files", "*.log"), ("All Files", "*.*")]
        )
        if file_paths:
            self.selected_files = list(file_paths)
            self.refresh()

    # ── Hành động Refresh ────────────────────────────────────────────────────
    def refresh(self):
        """Quét lại log được chọn và cập nhật bảng."""
        if not hasattr(self, 'selected_files') or not self.selected_files:
            return

        self.btn_refresh.config(state="disabled", text="⏳  Đang tải...")
        self.update_idletasks()

        try:
            df = self.log_parser.parse_files(self.selected_files)
            self._update_table(df)
            self._update_chart()
            self._set_status_ok(df)
        except Exception as exc:
            self._set_status_error(str(exc))
        finally:
            self.btn_refresh.config(state="normal", text="🔄  Refresh")

    def _update_table(self, df: pd.DataFrame):
        """Xóa dữ liệu cũ và điền dữ liệu mới vào Treeview."""
        # Xóa toàn bộ dòng cũ
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Chèn dữ liệu mới
        for idx, row in df.iterrows():
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert(
                "", "end",
                values=(
                    row["Tên Chuyền"],
                    row["Cấp liệu"],
                    row["Thu hồi"],
                    row["Tổng cộng"],
                ),
                tags=(tag,)
            )

        # Thêm dòng tổng cuối bảng
        total_supply  = df["Cấp liệu"].sum()
        total_recover = df["Thu hồi"].sum()
        total_all     = df["Tổng cộng"].sum()
        self.tree.insert(
            "", "end",
            values=("── TỔNG ──", total_supply, total_recover, total_all),
            tags=("total",)
        )
        self.tree.tag_configure("total", background="#D0E8FF", font=FONT_LABEL_B)

    def _set_status_ok(self, df: pd.DataFrame):
        """Cập nhật thanh trạng thái khi thành công."""
        files = ", ".join(self.log_parser.files_read) or "(không có)"
        skipped = self.log_parser.skipped_errors
        msg = (
            f"✅  Đã đọc: {files}  |  "
            f"Tổng tác vụ: {self.log_parser.total_tasks}  |  "
            f"Lỗi bỏ qua: {skipped}"
        )
        self.lbl_status.config(text=msg, fg=COLOR_STATUS_OK)
        self.lbl_time.config(
            text=f"Cập nhật lúc: {datetime.now().strftime('%H:%M:%S  %d/%m/%Y')}"
        )

    def _set_status_error(self, msg: str):
        """Cập nhật thanh trạng thái khi có lỗi."""
        self.lbl_status.config(text=f"❌  Lỗi: {msg}", fg=COLOR_STATUS_ERR)

    # ── Sắp xếp cột ─────────────────────────────────────────────────────────
    def _sort_by(self, col: str):
        """Sắp xếp bảng theo cột được click (bỏ qua dòng TỔNG)."""
        items = list(self.tree.get_children())
        if not items:
            return

        # Tách dòng TỔNG ra khỏi danh sách sắp xếp
        total_item = None
        sort_items = []
        for item in items:
            val = self.tree.item(item, "values")
            if val and str(val[0]).startswith("──"):
                total_item = item
            else:
                sort_items.append(item)

        # Đảo chiều nếu click lần 2
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        cols = ("Tên Chuyền", "Cấp liệu", "Thu hồi", "Tổng cộng")
        col_idx = cols.index(col)

        def sort_key(item):
            val = self.tree.item(item, "values")[col_idx]
            try:
                return (0, int(val))
            except (ValueError, TypeError):
                return (1, str(val).lower())

        sort_items.sort(key=sort_key, reverse=not self._sort_asc)

        for i, item in enumerate(sort_items):
            self.tree.move(item, "", i)
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.item(item, tags=(tag,))

        # Đặt dòng TỔNG xuống cuối
        if total_item:
            self.tree.move(total_item, "", "end")


# ─── Điểm khởi chạy ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AGVLogApp()
    app.mainloop()