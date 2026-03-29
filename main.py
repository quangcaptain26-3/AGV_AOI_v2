import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import aoi
import agv

class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bảng Điều Khiển Giám Sát AGV & AOI")
        self.geometry("1100x800")
        
        # Cấu hình phong cách UI cơ bản bằng TTK (thay thế customtkinter)
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        # Các biến dùng trong hệ thống để lưu trữ data pandas
        self.df_offline = pd.DataFrame()
        self.df_api = pd.DataFrame()
        self.df_aoi = pd.DataFrame()
        self.coverage = None
        
        self.selected_log_files = []
        self.selected_image_files = []
        
        self.build_ui()
        
    def build_ui(self):
        # -------------------------------------------------------------
        # PANE 1: HEADER & NÚT ĐIỀU CHỈNH 
        # (Chỉ chứa tên phần mềm và chức năng nạp dữ liệu)
        # -------------------------------------------------------------
        header_frame = tk.Frame(self, bg="#ecf0f1", pady=15, padx=20)
        header_frame.pack(fill='x', side='top')
        
        lbl_title = tk.Label(
            header_frame, 
            text="HỆ THỐNG GIÁM SÁT VẬN HÀNH & CHẤT LƯỢNG",
            font=('Arial', 18, 'bold'),
            fg="#2c3e50",
            bg="#ecf0f1"
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

        # -------------------------------------------------------------
        # PANE 2: KPI TỔNG QUAN
        # (Hiển thị các chỉ số cốt lõi kèm theo câu chữ diễn giải rõ ràng)
        # -------------------------------------------------------------
        kpi_frame = tk.Frame(self, bg="#ffffff", pady=20, padx=10)
        kpi_frame.pack(fill='x')
        
        self.kpis = {}
        # Mỗi KPI box sẽ bao gồm Tiêu đề, Số To, Mô tả rõ nghĩa
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

        # -------------------------------------------------------------
        # PANE 3: KHU VỰC BIỂU ĐỒ (Tab Notebook cho khỏi rối mắt)
        # -------------------------------------------------------------
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=15, pady=10)
        
        self.tab_agv = tk.Frame(self.notebook, bg="white")
        self.tab_api = tk.Frame(self.notebook, bg="white")
        self.tab_aoi = tk.Frame(self.notebook, bg="white")
        
        # Chia các tab với tên tiếng việt rõ nghĩa
        self.notebook.add(self.tab_agv, text=" Phân Tích Xe AGV Rớt Mạng ")
        self.notebook.add(self.tab_api, text=" Phân Tích Lỗi Server API ")
        self.notebook.add(self.tab_aoi, text=" Thống Kê Điểm Chất Lượng AOI ")
        
        # ----- Khởi tạo sẵn Figure cho Tab AGV -----
        self.fig_agv, (self.ax_agv_trend, self.ax_agv_top) = plt.subplots(1, 2, figsize=(10, 4))
        self.canvas_agv = FigureCanvasTkAgg(self.fig_agv, master=self.tab_agv)
        self.canvas_agv.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
        # ----- Khởi tạo sẵn Figure cho Tab API -----
        self.fig_api, self.ax_api_trend = plt.subplots(figsize=(10, 4))
        self.canvas_api = FigureCanvasTkAgg(self.fig_api, master=self.tab_api)
        self.canvas_api.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
        # ----- Khởi tạo sẵn Figure cho Tab AOI -----
        self.fig_aoi, (self.ax_aoi_bar, self.ax_aoi_rate) = plt.subplots(1, 2, figsize=(10, 4))
        self.canvas_aoi = FigureCanvasTkAgg(self.fig_aoi, master=self.tab_aoi)
        self.canvas_aoi.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)

    # =========================================================================
    # CÁC HÀM XÂY DỰNG GIAO DIỆN PHỤ
    # =========================================================================
    def create_kpi_box(self, parent, col, title, initial_val, desc):
        """Hàm sinh ra một ô KPI đơn giản, viền mảnh, chữ rõ ràng dễ đọc"""
        box = tk.Frame(parent, bg="#fdfdfd", bd=1, relief=tk.SOLID)
        box.grid(row=0, column=col, padx=10, sticky='nsew')
        
        lbl_title = tk.Label(box, text=title, font=('Arial', 11, 'bold'), bg="#fdfdfd", fg="#7f8c8d")
        lbl_title.pack(pady=(15, 0))
        
        lbl_val = tk.Label(box, text=initial_val, font=('Arial', 26, 'bold'), bg="#fdfdfd", fg="#2c3e50")
        lbl_val.pack(pady=10)
        
        lbl_desc = tk.Label(box, text=desc, font=('Arial', 9), bg="#fdfdfd", fg="#95a5a6", justify='center')
        lbl_desc.pack(pady=(0, 15))
        
        return {"val": lbl_val, "desc": lbl_desc}

    # =========================================================================
    # HÀM XỬ LÝ SỰ KIỆN: KHI NGƯỜI DÙNG CHỌN FILE
    # =========================================================================
    def load_agv(self):
        files = filedialog.askopenfilenames(title="Chọn file txt log AGV", filetypes=[("Log Files", "*.txt")])
        if not files:
            return
            
        try:
            # Hàm parse_agv_logs trả về df_offline, df_api, system_events, coverage
            self.df_offline, self.df_api, system_events, self.coverage = agv.parse_agv_logs(files)
            self.update_kpi()
            self.draw_agv_charts()
            self.draw_api_charts()
            messagebox.showinfo("Thành công", f"Đã đọc xong {len(files)} file log AGV.")
        except Exception as e:
            messagebox.showerror("Lỗi hệ thống", f"Không thể đọc file AGV:\n{e}")

    def load_aoi(self):
        files = filedialog.askopenfilenames(title="Chọn file ảnh AOI", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if not files:
            return
            
        try:
            # Hàm parse_aoi_images trả về Dataframe summary cột: Date, PASS, FAIL
            self.df_aoi = aoi.parse_aoi_images(files)
            self.update_kpi()
            self.draw_aoi_charts()
            messagebox.showinfo("Thành công", f"Đã tổng hợp {len(files)} ảnh AOI.")
        except Exception as e:
            messagebox.showerror("Lỗi hệ thống", f"Không thể lấy dữ liệu ảnh AOI:\n{e}")

    # =========================================================================
    # CẬP NHẬT CÁC CON SỐ KPI THEO NGỮ NGHĨA CON NGƯỜI
    # =========================================================================
    def update_kpi(self):
        # 1. Update AGV Offline
        if not self.df_offline.empty:
            total_off = int(self.df_offline['Count'].sum())
            agv_count = self.df_offline['AGV'].nunique()
            self.kpis['agv']['val'].config(text=f"{total_off} Lần", fg="#e74c3c" if total_off > 0 else "#27ae60")
            self.kpis['agv']['desc'].config(text=f"Phát hiện có {total_off} sự cố rớt mạng\nxảy ra trên {agv_count} hệ thống xe khác nhau.")
        else:
            self.kpis['agv']['val'].config(text="0 Lần", fg="#2c3e50")
            self.kpis['agv']['desc'].config(text="Không tìm thấy sự cố rớt mạng nào\ntrong tập dữ liệu log đã quét.")

        # 2. Update API Errors
        if not self.df_api.empty:
            total_api = int(self.df_api['Count'].sum())
            self.kpis['api']['val'].config(text=f"{total_api} Lỗi", fg="#e67e22" if total_api > 0 else "#27ae60")
            self.kpis['api']['desc'].config(text=f"Ghi nhận hệ thống gọi API\nbị mất kết nối tổng cộng {total_api} lần.")
        else:
            self.kpis['api']['val'].config(text="0 Lỗi", fg="#2c3e50")
            self.kpis['api']['desc'].config(text="Không có dấu hiệu ghi nhận lỗi\nliên kết máy chủ. Code API ổn định.")

        # 3. Update AOI Rating (Yield)
        if not self.df_aoi.empty:
            pass_val = self.df_aoi.get('PASS', 0).sum()
            fail_val = self.df_aoi.get('FAIL', 0).sum()
            total = pass_val + fail_val
            rate = (pass_val / total * 100) if total > 0 else 0
            self.kpis['aoi']['val'].config(text=f"{rate:.1f} %", fg="#27ae60" if rate > 95 else "#c0392b")
            self.kpis['aoi']['desc'].config(text=f"Có {pass_val} hình ĐẠT / {total} tổng hình chụp.\nTỉ lệ lỗi đang chiếm khoảng {100 - rate:.1f}%.")
        
        # 4. Update Time Coverage
        if self.coverage:
            start_ts = self.coverage.get('ts_min')
            end_ts = self.coverage.get('ts_max')
            if start_ts and end_ts:
                hours = (end_ts - start_ts).total_seconds() / 3600
                self.kpis['cov']['val'].config(text=f"{hours:.1f} Giờ")
                self.kpis['cov']['desc'].config(text=f"Bắt đầu: {start_ts.strftime('%d/%m %H:%M')}\nKết thúc: {end_ts.strftime('%d/%m %H:%M')}")

    # =========================================================================
    # PHẦN VẼ BIỂU ĐỒ TRỰC QUAN (Sử dụng matplotlib native)
    # Cố gắng đặt tên biểu đồ dài và có chú thích rõ cho Label
    # =========================================================================
    def draw_agv_charts(self):
        self.ax_agv_trend.clear()
        self.ax_agv_top.clear()
        
        if not self.df_offline.empty:
            # A. Biểu đồ đường thời gian
            trend = self.df_offline.groupby('Hour')['Count'].sum().reset_index()
            self.ax_agv_trend.plot(trend['Hour'], trend['Count'], marker='o', color='#c0392b', linewidth=2)
            self.ax_agv_trend.set_title("BIỂU ĐỒ 1: TẦN SUẤT XE BỊ RỚT MẠNG THEO THỜI GIAN", pad=10)
            self.ax_agv_trend.set_xlabel("Thời Gian (Ngày / Giờ)")
            self.ax_agv_trend.set_ylabel("SỐ LẦN ĐỨT KẾT NỐI")
            self.ax_agv_trend.tick_params(axis='x', rotation=45)
            self.ax_agv_trend.grid(True, linestyle="--", alpha=0.5)
            
            # Gắn sẵn chỉ số vào các đỉnh của đường cho dễ nắm bắt
            for i, val in enumerate(trend['Count']):
                self.ax_agv_trend.text(i, val + (val*0.05), str(val), ha='center', fontsize=9)

            # B. Biểu đồ Top những chiếc hay hỏng nhất
            top = self.df_offline.groupby('AGV')['Count'].sum().reset_index().sort_values('Count', ascending=False).head(10)
            bars = self.ax_agv_top.bar(top['AGV'].astype(str), top['Count'], color='#f39c12')
            self.ax_agv_top.set_title("BIỂU ĐỒ 2: NHỮNG XE AGV RỚT MẠNG NHIỀU NHẤT", pad=10)
            self.ax_agv_top.set_xlabel("Định Danh (ID) Của Xe")
            self.ax_agv_top.set_ylabel("TỔNG SỐ LẦN HỎNG")
            
            self.ax_agv_top.bar_label(bars, padding=3, color='black', fontsize=9)

        self.fig_agv.tight_layout()
        self.canvas_agv.draw()

    def draw_api_charts(self):
        self.ax_api_trend.clear()
        
        if not self.df_api.empty:
            trend = self.df_api.groupby('Hour')['Count'].sum().reset_index()
            self.ax_api_trend.plot(trend['Hour'], trend['Count'], marker='s', color='#d35400', linewidth=2)
            self.ax_api_trend.set_title("SỐ LƯỢNG YÊU CẦU API SERVER BỊ TỪ CHỐI / LỖI", pad=10)
            self.ax_api_trend.set_xlabel("Thời Gian (Ngày / Giờ)")
            self.ax_api_trend.set_ylabel("SỐ CHUỖI LỖI GHI NHẬN")
            self.ax_api_trend.tick_params(axis='x', rotation=45)
            self.ax_api_trend.grid(True, linestyle="--", alpha=0.5)
            
            for i, val in enumerate(trend['Count']):
                self.ax_api_trend.text(i, val + (val*0.05), str(val), ha='center', fontsize=9)
            
        self.fig_api.tight_layout()
        self.canvas_api.draw()

    def draw_aoi_charts(self):
        self.ax_aoi_bar.clear()
        self.ax_aoi_rate.clear()
        
        if not self.df_aoi.empty:
            dates = self.df_aoi['Date']
            p_vals = self.df_aoi.get('PASS', pd.Series(0, index=dates.index))
            f_vals = self.df_aoi.get('FAIL', pd.Series(0, index=dates.index))
            
            # 1. Thống kê số ảnh ĐẠT và HỎNG hàng ngày
            b1 = self.ax_aoi_bar.bar(dates, p_vals, label='Số ảnh tốt (PASS)', color='#27ae60')
            b2 = self.ax_aoi_bar.bar(dates, f_vals, bottom=p_vals, label='Số ảnh hỏng (FAIL)', color='#c0392b')
            
            self.ax_aoi_bar.set_title("1. SẢN LƯỢNG ẢNH TỐT / HỎNG THEO TỪNG LÔ NGÀY", pad=10)
            self.ax_aoi_bar.set_xlabel("Ngày Sản Xuất")
            self.ax_aoi_bar.set_ylabel("SỐ LƯỢNG")
            self.ax_aoi_bar.legend()
            self.ax_aoi_bar.tick_params(axis='x', rotation=45)
            
            self.ax_aoi_bar.bar_label(b1, label_type='center', color='white', fontsize=9)
            if f_vals.sum() > 0:
                self.ax_aoi_bar.bar_label(b2, label_type='center', color='white', fontsize=9)

            # 2. Tỉ lệ Pass (Yield)
            totals = p_vals + f_vals
            rates = (p_vals / totals * 100).fillna(0)
            
            self.ax_aoi_rate.plot(dates, rates, marker='^', color='#2980b9', linewidth=2)
            self.ax_aoi_rate.set_title("2. TỈ LỆ ẢNH TỐT CHIẾM PHẦN TRĂM (%)", pad=10)
            self.ax_aoi_rate.set_xlabel("Ngày Sản Xuất")
            self.ax_aoi_rate.set_ylabel("MỨC ĐỘ VƯỢT (% CHUẨN THÀNH PHẨM)")
            self.ax_aoi_rate.set_ylim(0, 105)
            self.ax_aoi_rate.tick_params(axis='x', rotation=45)
            self.ax_aoi_rate.grid(True, linestyle="--", alpha=0.5)
            
            for i, r in enumerate(rates):
                self.ax_aoi_rate.text(i, r + 2, f"{r:.1f}%", ha='center', va='bottom', fontsize=9, color='black')
            
        self.fig_aoi.tight_layout()
        self.canvas_aoi.draw()

if __name__ == "__main__":
    app = DashboardApp()
    app.mainloop()