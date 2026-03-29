"""
main_bu.py — Bản dự phòng (Backup) của main.py
Không dùng matplotlib, thay bằng tkinter.Canvas để vẽ biểu đồ.
Logic xử lý dữ liệu và cấu trúc UI giữ nguyên 100%.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import math

import aoi
import agv


# =============================================================================
# MODULE VẼ BIỂU ĐỒ BẰNG TKINTER CANVAS (thay thế matplotlib)
# =============================================================================

class CanvasChart:
    """Lớp vẽ biểu đồ dòng (line) và cột (bar) thuần tkinter.Canvas."""

    PADDING = {"top": 40, "bottom": 60, "left": 65, "right": 20}
    COLORS = {
        "red":    "#c0392b",
        "orange": "#f39c12",
        "dark_orange": "#d35400",
        "green":  "#27ae60",
        "blue":   "#2980b9",
        "grey":   "#bdc3c7",
        "dark":   "#2c3e50",
        "white":  "#ffffff",
        "grid":   "#ecf0f1",
    }

    def __init__(self, parent, width=480, height=320):
        self.canvas = tk.Canvas(parent, bg="white", width=width, height=height,
                                highlightthickness=1, highlightbackground="#ddd")
        self.canvas.pack(fill='both', expand=True, padx=8, pady=8)
        self.width = width
        self.height = height

    def _plot_area(self):
        p = self.PADDING
        x0 = p["left"]
        y0 = p["top"]
        x1 = self.width - p["right"]
        y1 = self.height - p["bottom"]
        return x0, y0, x1, y1

    def clear(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or self.width
        h = self.canvas.winfo_height() or self.height
        self.width = w
        self.height = h

    def _draw_axes(self, title, xlabel, ylabel):
        x0, y0, x1, y1 = self._plot_area()
        # Vùng nền
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="#fafafa", outline="#ccc")
        # Tiêu đề
        cx = (x0 + x1) / 2
        self.canvas.create_text(cx, y0 - 20, text=title, font=("Arial", 9, "bold"),
                                fill=self.COLORS["dark"], anchor="center")
        # Nhãn trục X
        self.canvas.create_text(cx, self.height - 8, text=xlabel, font=("Arial", 8),
                                fill="#7f8c8d", anchor="center")
        # Nhãn trục Y (xoay bằng cách xếp chữ dọc)
        self.canvas.create_text(12, (y0 + y1) / 2, text=ylabel, font=("Arial", 8),
                                fill="#7f8c8d", angle=90, anchor="center")

    def _scale(self, values, x0, y0, x1, y1):
        """Trả về hàm chuyển đổi (index, value) -> (px, py)."""
        n = len(values)
        max_v = max(values) if max(values) != 0 else 1
        w = x1 - x0
        h = y1 - y0

        def to_px(i, v):
            px = x0 + (i / max(n - 1, 1)) * w if n > 1 else x0 + w / 2
            py = y1 - (v / max_v) * h
            return px, py

        return to_px, max_v

    def _grid_lines(self, max_v, x0, y0, x1, y1, steps=5):
        h = y1 - y0
        for i in range(steps + 1):
            ratio = i / steps
            py = y1 - ratio * h
            val = max_v * ratio
            self.canvas.create_line(x0, py, x1, py, fill=self.COLORS["grid"], dash=(4, 3))
            label = f"{val:.0f}" if val >= 1 else f"{val:.2f}"
            self.canvas.create_text(x0 - 5, py, text=label, font=("Arial", 7),
                                    fill="#7f8c8d", anchor="e")

    # ------------------------------------------------------------------
    def draw_line(self, labels, values, title="", xlabel="", ylabel="",
                  color="red", marker='o'):
        """Vẽ biểu đồ đường (line chart)."""
        self.clear()
        if not values:
            self._draw_empty(title)
            return
        self._draw_axes(title, xlabel, ylabel)
        x0, y0, x1, y1 = self._plot_area()
        to_px, max_v = self._scale(values, x0, y0, x1, y1)
        self._grid_lines(max_v, x0, y0, x1, y1)

        col = self.COLORS.get(color, color)
        n = len(values)
        points = [to_px(i, v) for i, v in enumerate(values)]

        # Vẽ đường nối
        for i in range(len(points) - 1):
            self.canvas.create_line(points[i][0], points[i][1],
                                    points[i+1][0], points[i+1][1],
                                    fill=col, width=2)
        # Vẽ điểm và nhãn
        r = 4
        for i, (px, py) in enumerate(points):
            self.canvas.create_oval(px - r, py - r, px + r, py + r,
                                    fill=col, outline="white", width=1)
            # Nhãn giá trị trên điểm
            self.canvas.create_text(px, py - 12, text=str(values[i]),
                                    font=("Arial", 7, "bold"), fill=col)
            # Nhãn X (cắt ngắn nếu dài)
            lbl = str(labels[i])
            if len(lbl) > 10:
                lbl = lbl[:9] + "…"
            step = (x1 - x0) / max(n - 1, 1) if n > 1 else 0
            every = max(1, math.ceil(n / 8))
            if i % every == 0:
                self.canvas.create_text(px, y1 + 10, text=lbl, font=("Arial", 7),
                                        fill="#555", angle=30, anchor="nw")

    # ------------------------------------------------------------------
    def draw_bar(self, labels, values, title="", xlabel="", ylabel="",
                 color="orange"):
        """Vẽ biểu đồ cột đơn (bar chart)."""
        self.clear()
        if not values:
            self._draw_empty(title)
            return
        self._draw_axes(title, xlabel, ylabel)
        x0, y0, x1, y1 = self._plot_area()
        n = len(values)
        max_v = max(values) if max(values) != 0 else 1
        self._grid_lines(max_v, x0, y0, x1, y1)

        col = self.COLORS.get(color, color)
        w = (x1 - x0)
        slot = w / n
        bar_w = slot * 0.6

        for i, (lbl, val) in enumerate(zip(labels, values)):
            cx = x0 + slot * i + slot / 2
            bar_h = (val / max_v) * (y1 - y0)
            bx0 = cx - bar_w / 2
            bx1 = cx + bar_w / 2
            by0 = y1 - bar_h
            by1 = y1
            self.canvas.create_rectangle(bx0, by0, bx1, by1,
                                         fill=col, outline="white", width=1)
            # Nhãn trên cột
            self.canvas.create_text(cx, by0 - 8, text=str(val),
                                    font=("Arial", 7, "bold"), fill="#333")
            # Nhãn X
            s = str(lbl)
            if len(s) > 8:
                s = s[:7] + "…"
            self.canvas.create_text(cx, y1 + 10, text=s, font=("Arial", 7),
                                    fill="#555", angle=30, anchor="nw")

    # ------------------------------------------------------------------
    def draw_stacked_bar(self, labels, bottom_vals, top_vals,
                         bottom_label="PASS", top_label="FAIL",
                         title="", xlabel="", ylabel="",
                         bottom_color="green", top_color="red"):
        """Vẽ biểu đồ cột xếp chồng (stacked bar)."""
        self.clear()
        combined = [b + t for b, t in zip(bottom_vals, top_vals)]
        if not combined or max(combined) == 0:
            self._draw_empty(title)
            return
        self._draw_axes(title, xlabel, ylabel)
        x0, y0, x1, y1 = self._plot_area()
        n = len(labels)
        max_v = max(combined)
        self._grid_lines(max_v, x0, y0, x1, y1)

        bc = self.COLORS.get(bottom_color, bottom_color)
        tc = self.COLORS.get(top_color, top_color)
        w = x1 - x0
        slot = w / n
        bar_w = slot * 0.6

        for i, (lbl, bv, tv) in enumerate(zip(labels, bottom_vals, top_vals)):
            cx = x0 + slot * i + slot / 2
            h_scale = (y1 - y0) / max_v
            # Phần bottom (PASS)
            bh = bv * h_scale
            self.canvas.create_rectangle(cx - bar_w/2, y1 - bh,
                                         cx + bar_w/2, y1,
                                         fill=bc, outline="white")
            if bv > 0:
                self.canvas.create_text(cx, y1 - bh/2, text=str(bv),
                                        font=("Arial", 7), fill="white")
            # Phần top (FAIL)
            if tv > 0:
                th = tv * h_scale
                self.canvas.create_rectangle(cx - bar_w/2, y1 - bh - th,
                                             cx + bar_w/2, y1 - bh,
                                             fill=tc, outline="white")
                self.canvas.create_text(cx, y1 - bh - th/2, text=str(tv),
                                        font=("Arial", 7), fill="white")
            # Nhãn X
            s = str(lbl)
            if len(s) > 8:
                s = s[:7] + "…"
            self.canvas.create_text(cx, y1 + 10, text=s, font=("Arial", 7),
                                    fill="#555", angle=30, anchor="nw")

        # Legend đơn giản
        lx = x0 + 5
        ly = y0 + 5
        self.canvas.create_rectangle(lx, ly, lx+12, ly+10, fill=bc)
        self.canvas.create_text(lx+16, ly+5, text=bottom_label, font=("Arial", 7), anchor="w")
        self.canvas.create_rectangle(lx+60, ly, lx+72, ly+10, fill=tc)
        self.canvas.create_text(lx+76, ly+5, text=top_label, font=("Arial", 7), anchor="w")

    # ------------------------------------------------------------------
    def _draw_empty(self, title=""):
        w = self.canvas.winfo_width() or self.width
        h = self.canvas.winfo_height() or self.height
        self.canvas.create_text(w/2, h/2, text="[ Chưa có dữ liệu ]",
                                font=("Arial", 12), fill="#bdc3c7")
        if title:
            self.canvas.create_text(w/2, 20, text=title, font=("Arial", 9, "bold"),
                                    fill="#95a5a6")


# =============================================================================
# ỨNG DỤNG CHÍNH (Giữ nguyên hoàn toàn logic từ main.py)
# =============================================================================

class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bảng Điều Khiển Giám Sát AGV & AOI")
        self.geometry("1100x800")

        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')

        # Lưu trữ dữ liệu pandas
        self.df_offline = pd.DataFrame()
        self.df_api = pd.DataFrame()
        self.df_aoi = pd.DataFrame()
        self.coverage = None

        self.selected_log_files = []
        self.selected_image_files = []

        self.build_ui()

    # =========================================================================
    # XÂY DỰNG GIAO DIỆN
    # =========================================================================
    def build_ui(self):
        # ------------------------------------------------------------------
        # PANE 1: HEADER & NÚT ĐIỀU CHỈNH
        # ------------------------------------------------------------------
        header_frame = tk.Frame(self, bg="#ecf0f1", pady=15, padx=20)
        header_frame.pack(fill='x', side='top')

        lbl_title = tk.Label(
            header_frame,
            text="HỆ THỐNG GIÁM SÁT VẬN HÀNH & CHẤT LƯỢNG",
            font=('Arial', 18, 'bold'),
            fg="#2c3e50", bg="#ecf0f1"
        )
        lbl_title.pack(side='left')

        btn_aoi = tk.Button(
            header_frame,
            text="📷 Tải Ảnh Trạng Thái AOI",
            command=self.load_aoi,
            font=('Arial', 11, 'bold'),
            bg="#3498db", fg="white", relief=tk.FLAT, padx=10, pady=5
        )
        btn_aoi.pack(side='right', padx=(10, 0))

        btn_agv = tk.Button(
            header_frame,
            text="📄 Tải Log Lỗi Xe AGV",
            command=self.load_agv,
            font=('Arial', 11, 'bold'),
            bg="#e67e22", fg="white", relief=tk.FLAT, padx=10, pady=5
        )
        btn_agv.pack(side='right')

        # ------------------------------------------------------------------
        # PANE 2: KPI TỔNG QUAN
        # ------------------------------------------------------------------
        kpi_frame = tk.Frame(self, bg="#ffffff", pady=20, padx=10)
        kpi_frame.pack(fill='x')

        self.kpis = {}
        self.kpis['agv'] = self.create_kpi_box(
            kpi_frame, col=0,
            title="AGV BỊ RỚT MẠNG",
            initial_val="0 Lần",
            desc="Tổng số lần xe AGV bị rớt mạng\ntrong toàn bộ thời gian đo."
        )
        self.kpis['api'] = self.create_kpi_box(
            kpi_frame, col=1,
            title="GỌI API THẤT BẠI",
            initial_val="0 Lỗi",
            desc="Số lần xe gọi đến máy chủ API\nbị mất kết nối, lỗi mạng."
        )
        self.kpis['aoi'] = self.create_kpi_box(
            kpi_frame, col=2,
            title="TỈ LỆ ẢNH ĐẠT (PASS)",
            initial_val="0.0 %",
            desc="Lượng linh kiện/ảnh đạt (PASS)\ntrên tổng số lượng chụp."
        )
        self.kpis['cov'] = self.create_kpi_box(
            kpi_frame, col=3,
            title="TỔNG THỜI GIAN THEO DÕI",
            initial_val="0 Giờ",
            desc="Được tính từ lúc file log đầu tiên\nđến file log cuối cùng."
        )

        for i in range(4):
            kpi_frame.columnconfigure(i, weight=1)

        # ------------------------------------------------------------------
        # PANE 3: KHU VỰC BIỂU ĐỒ (Notebook)
        # ------------------------------------------------------------------
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=15, pady=10)

        self.tab_agv = tk.Frame(self.notebook, bg="white")
        self.tab_api = tk.Frame(self.notebook, bg="white")
        self.tab_aoi = tk.Frame(self.notebook, bg="white")

        self.notebook.add(self.tab_agv, text=" Phân Tích Xe AGV Rớt Mạng ")
        self.notebook.add(self.tab_api, text=" Phân Tích Lỗi Server API ")
        self.notebook.add(self.tab_aoi, text=" Thống Kê Điểm Chất Lượng AOI ")

        # ----- Tab AGV: 2 biểu đồ ngang -----
        agv_inner = tk.Frame(self.tab_agv, bg="white")
        agv_inner.pack(fill='both', expand=True)
        agv_inner.columnconfigure(0, weight=1)
        agv_inner.columnconfigure(1, weight=1)
        agv_inner.rowconfigure(0, weight=1)

        left_agv = tk.Frame(agv_inner, bg="white")
        left_agv.grid(row=0, column=0, sticky='nsew')
        right_agv = tk.Frame(agv_inner, bg="white")
        right_agv.grid(row=0, column=1, sticky='nsew')

        self.chart_agv_trend = CanvasChart(left_agv)
        self.chart_agv_top   = CanvasChart(right_agv)

        # ----- Tab API: 1 biểu đồ -----
        self.chart_api_trend = CanvasChart(self.tab_api)

        # ----- Tab AOI: 2 biểu đồ ngang -----
        aoi_inner = tk.Frame(self.tab_aoi, bg="white")
        aoi_inner.pack(fill='both', expand=True)
        aoi_inner.columnconfigure(0, weight=1)
        aoi_inner.columnconfigure(1, weight=1)
        aoi_inner.rowconfigure(0, weight=1)

        left_aoi = tk.Frame(aoi_inner, bg="white")
        left_aoi.grid(row=0, column=0, sticky='nsew')
        right_aoi = tk.Frame(aoi_inner, bg="white")
        right_aoi.grid(row=0, column=1, sticky='nsew')

        self.chart_aoi_bar  = CanvasChart(left_aoi)
        self.chart_aoi_rate = CanvasChart(right_aoi)

        # Vẽ trạng thái rỗng ban đầu
        self.chart_agv_trend._draw_empty("BIỂU ĐỒ 1: TẦN SUẤT XE BỊ RỚT MẠNG THEO THỜI GIAN")
        self.chart_agv_top._draw_empty("BIỂU ĐỒ 2: NHỮNG XE AGV RỚT MẠNG NHIỀU NHẤT")
        self.chart_api_trend._draw_empty("SỐ LƯỢNG YÊU CẦU API SERVER BỊ TỪ CHỐI / LỖI")
        self.chart_aoi_bar._draw_empty("1. SẢN LƯỢNG ẢNH TỐT / HỎNG THEO TỪNG LÔ NGÀY")
        self.chart_aoi_rate._draw_empty("2. TỈ LỆ ẢNH TỐT CHIẾM PHẦN TRĂM (%)")

    # =========================================================================
    # HÀM TẠO KPI BOX (giữ nguyên)
    # =========================================================================
    def create_kpi_box(self, parent, col, title, initial_val, desc):
        box = tk.Frame(parent, bg="#fdfdfd", bd=1, relief=tk.SOLID)
        box.grid(row=0, column=col, padx=10, sticky='nsew')

        lbl_title = tk.Label(box, text=title, font=('Arial', 11, 'bold'),
                             bg="#fdfdfd", fg="#7f8c8d")
        lbl_title.pack(pady=(15, 0))

        lbl_val = tk.Label(box, text=initial_val, font=('Arial', 26, 'bold'),
                           bg="#fdfdfd", fg="#2c3e50")
        lbl_val.pack(pady=10)

        lbl_desc = tk.Label(box, text=desc, font=('Arial', 9),
                            bg="#fdfdfd", fg="#95a5a6", justify='center')
        lbl_desc.pack(pady=(0, 15))

        return {"val": lbl_val, "desc": lbl_desc}

    # =========================================================================
    # XỬ LÝ SỰ KIỆN (giữ nguyên)
    # =========================================================================
    def load_agv(self):
        files = filedialog.askopenfilenames(
            title="Chọn file txt log AGV",
            filetypes=[("Log Files", "*.txt")]
        )
        if not files:
            return
        try:
            self.df_offline, self.df_api, system_events, self.coverage = agv.parse_agv_logs(files)
            self.update_kpi()
            self.draw_agv_charts()
            self.draw_api_charts()
            messagebox.showinfo("Thành công", f"Đã đọc xong {len(files)} file log AGV.")
        except Exception as e:
            messagebox.showerror("Lỗi hệ thống", f"Không thể đọc file AGV:\n{e}")

    def load_aoi(self):
        files = filedialog.askopenfilenames(
            title="Chọn file ảnh AOI",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")]
        )
        if not files:
            return
        try:
            self.df_aoi = aoi.parse_aoi_images(files)
            self.update_kpi()
            self.draw_aoi_charts()
            messagebox.showinfo("Thành công", f"Đã tổng hợp {len(files)} ảnh AOI.")
        except Exception as e:
            messagebox.showerror("Lỗi hệ thống", f"Không thể lấy dữ liệu ảnh AOI:\n{e}")

    # =========================================================================
    # CẬP NHẬT KPI (giữ nguyên hoàn toàn)
    # =========================================================================
    def update_kpi(self):
        # 1. AGV Offline
        if not self.df_offline.empty:
            total_off = int(self.df_offline['Count'].sum())
            agv_count = self.df_offline['AGV'].nunique()
            self.kpis['agv']['val'].config(
                text=f"{total_off} Lần",
                fg="#e74c3c" if total_off > 0 else "#27ae60"
            )
            self.kpis['agv']['desc'].config(
                text=f"Phát hiện có {total_off} sự cố rớt mạng\nxảy ra trên {agv_count} hệ thống xe khác nhau."
            )
        else:
            self.kpis['agv']['val'].config(text="0 Lần", fg="#2c3e50")
            self.kpis['agv']['desc'].config(
                text="Không tìm thấy sự cố rớt mạng nào\ntrong tập dữ liệu log đã quét."
            )

        # 2. API Errors
        if not self.df_api.empty:
            total_api = int(self.df_api['Count'].sum())
            self.kpis['api']['val'].config(
                text=f"{total_api} Lỗi",
                fg="#e67e22" if total_api > 0 else "#27ae60"
            )
            self.kpis['api']['desc'].config(
                text=f"Ghi nhận hệ thống gọi API\nbị mất kết nối tổng cộng {total_api} lần."
            )
        else:
            self.kpis['api']['val'].config(text="0 Lỗi", fg="#2c3e50")
            self.kpis['api']['desc'].config(
                text="Không có dấu hiệu ghi nhận lỗi\nliên kết máy chủ. Code API ổn định."
            )

        # 3. AOI Rating
        if not self.df_aoi.empty:
            pass_val = self.df_aoi.get('PASS', 0).sum()
            fail_val = self.df_aoi.get('FAIL', 0).sum()
            total = pass_val + fail_val
            rate = (pass_val / total * 100) if total > 0 else 0
            self.kpis['aoi']['val'].config(
                text=f"{rate:.1f} %",
                fg="#27ae60" if rate > 95 else "#c0392b"
            )
            self.kpis['aoi']['desc'].config(
                text=f"Có {pass_val} hình ĐẠT / {total} tổng hình chụp.\nTỉ lệ lỗi đang chiếm khoảng {100 - rate:.1f}%."
            )

        # 4. Time Coverage
        if self.coverage:
            start_ts = self.coverage.get('ts_min')
            end_ts = self.coverage.get('ts_max')
            if start_ts and end_ts:
                hours = (end_ts - start_ts).total_seconds() / 3600
                self.kpis['cov']['val'].config(text=f"{hours:.1f} Giờ")
                self.kpis['cov']['desc'].config(
                    text=f"Bắt đầu: {start_ts.strftime('%d/%m %H:%M')}\nKết thúc: {end_ts.strftime('%d/%m %H:%M')}"
                )

    # =========================================================================
    # VẼ BIỂU ĐỒ (thay matplotlib bằng CanvasChart)
    # =========================================================================
    def draw_agv_charts(self):
        if not self.df_offline.empty:
            # Biểu đồ 1: Trend theo giờ
            trend = self.df_offline.groupby('Hour')['Count'].sum().reset_index()
            labels = [str(h) for h in trend['Hour']]
            values = list(trend['Count'].astype(int))
            self.chart_agv_trend.draw_line(
                labels, values,
                title="BIỂU ĐỒ 1: TẦN SUẤT XE BỊ RỚT MẠNG THEO THỜI GIAN",
                xlabel="Thời Gian (Ngày / Giờ)",
                ylabel="SỐ LẦN ĐỨT KẾT NỐI",
                color="red"
            )

            # Biểu đồ 2: Top xe hay hỏng nhất
            top = (
                self.df_offline.groupby('AGV')['Count']
                .sum().reset_index()
                .sort_values('Count', ascending=False)
                .head(10)
            )
            self.chart_agv_top.draw_bar(
                list(top['AGV'].astype(str)),
                list(top['Count'].astype(int)),
                title="BIỂU ĐỒ 2: NHỮNG XE AGV RỚT MẠNG NHIỀU NHẤT",
                xlabel="Định Danh (ID) Của Xe",
                ylabel="TỔNG SỐ LẦN HỎNG",
                color="orange"
            )
        else:
            self.chart_agv_trend._draw_empty("BIỂU ĐỒ 1: TẦN SUẤT XE BỊ RỚT MẠNG THEO THỜI GIAN")
            self.chart_agv_top._draw_empty("BIỂU ĐỒ 2: NHỮNG XE AGV RỚT MẠNG NHIỀU NHẤT")

    def draw_api_charts(self):
        if not self.df_api.empty:
            trend = self.df_api.groupby('Hour')['Count'].sum().reset_index()
            labels = [str(h) for h in trend['Hour']]
            values = list(trend['Count'].astype(int))
            self.chart_api_trend.draw_line(
                labels, values,
                title="SỐ LƯỢNG YÊU CẦU API SERVER BỊ TỪ CHỐI / LỖI",
                xlabel="Thời Gian (Ngày / Giờ)",
                ylabel="SỐ CHUỖI LỖI GHI NHẬN",
                color="dark_orange"
            )
        else:
            self.chart_api_trend._draw_empty("SỐ LƯỢNG YÊU CẦU API SERVER BỊ TỪ CHỐI / LỖI")

    def draw_aoi_charts(self):
        if not self.df_aoi.empty:
            dates = list(self.df_aoi['Date'].astype(str))
            p_vals = list(self.df_aoi.get('PASS', pd.Series(0, index=self.df_aoi.index)).astype(int))
            f_vals = list(self.df_aoi.get('FAIL', pd.Series(0, index=self.df_aoi.index)).astype(int))

            # Biểu đồ 1: Stacked bar PASS/FAIL
            self.chart_aoi_bar.draw_stacked_bar(
                dates, p_vals, f_vals,
                bottom_label="Số ảnh tốt (PASS)",
                top_label="Số ảnh hỏng (FAIL)",
                title="1. SẢN LƯỢNG ẢNH TỐT / HỎNG THEO TỪNG LÔ NGÀY",
                xlabel="Ngày Sản Xuất",
                ylabel="SỐ LƯỢNG",
                bottom_color="green",
                top_color="red"
            )

            # Biểu đồ 2: Tỉ lệ Pass (%)
            totals = [p + f for p, f in zip(p_vals, f_vals)]
            rates_raw = [(p / t * 100) if t > 0 else 0 for p, t in zip(p_vals, totals)]
            rates = [round(r, 1) for r in rates_raw]
            self.chart_aoi_rate.draw_line(
                dates, rates,
                title="2. TỈ LỆ ẢNH TỐT CHIẾM PHẦN TRĂM (%)",
                xlabel="Ngày Sản Xuất",
                ylabel="MỨC ĐỘ VƯỢT (% CHUẨN THÀNH PHẨM)",
                color="blue"
            )
        else:
            self.chart_aoi_bar._draw_empty("1. SẢN LƯỢNG ẢNH TỐT / HỎNG THEO TỪNG LÔ NGÀY")
            self.chart_aoi_rate._draw_empty("2. TỈ LỆ ẢNH TỐT CHIẾM PHẦN TRĂM (%)")


if __name__ == "__main__":
    app = DashboardApp()
    app.mainloop()