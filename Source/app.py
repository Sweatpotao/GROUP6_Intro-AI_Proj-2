import sys
import os
import threading
import json

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QComboBox, QPushButton, QFrame, QScrollArea, 
    QGroupBox, QSlider, QMessageBox, QListWidget
)
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont, QPainter, QColor, QPen

sys.path.insert(0, os.path.dirname(__file__))

from core.parser  import load_all_puzzles
from core.logger  import save_output
from core.config  import STATUS_SOLVED, STATUS_TIMEOUT, STATUS_STEP_LIMIT, STATUS_UNSOLVABLE
from main         import _run_with_timeout, SOLVERS

INPUT_DIR  = os.path.join(os.path.dirname(__file__), "Inputs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Outputs")

class SolverSignals(QObject):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

class Cell(QLabel):
    def __init__(self, r, c):
        super().__init__("")
        self.r = r
        self.c = c
        self.setFixedSize(50, 50)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial", 16))
        self.setObjectName("cell")
        self.setProperty("status", "")

class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setVisible(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # nền blur giả lập
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # box giữa
        box_rect = self.rect().adjusted(
            self.width()//3, self.height()//3,
            -self.width()//3, -self.height()//3
        )

        painter.setBrush(QColor(255, 255, 255, 230))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(box_rect, 20, 20)

        # text
        painter.setPen(QPen(QColor("#8e44ad")))
        painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
        painter.drawText(box_rect, Qt.AlignCenter, "⚡ Solving...")

    def resize_to_parent(self):
        if self.parent():
            self.setGeometry(self.parent().rect())

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Futoshiki Solver")
        self.resize(1100, 960)

        self.puzzles = []
        self.puzzle = None
        self.cells = []
        self.current_steps = []
        self.solving = False

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.auto_step)
        self.is_auto_running = False

        self._build_ui()
        self._load_puzzles()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- BÊN TRÁI: AREA PUZZLE ---
        left_side = QVBoxLayout()
        
        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        t_layout = QHBoxLayout(toolbar)
        
        self.puzzle_box = QComboBox()
        self.algo_box = QComboBox()
        self.algo_box.addItems([name for name, _ in SOLVERS])
        self.load_btn = QPushButton("Reset Map")
        self.load_btn.setObjectName("loadBtn")
        self.run_btn = QPushButton("Solve")
        self.run_btn.setObjectName("solveBtn")
        self.load_data_btn = QPushButton("Load Data")
        self.load_data_btn.setObjectName("loadDataBtn")
        
        t_layout.addWidget(QLabel("Puzzle:"))
        t_layout.addWidget(self.puzzle_box)
        t_layout.addWidget(QLabel("Algo:"))
        t_layout.addWidget(self.algo_box)
        t_layout.addStretch()
        t_layout.addWidget(self.load_btn)
        t_layout.addWidget(self.load_data_btn)
        t_layout.addWidget(self.run_btn)
        left_side.addWidget(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("gridScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.grid_container = QWidget()
        self.grid_container.setObjectName("gridPanel")

        self.grid_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Layout cho grid
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setContentsMargins(20, 20, 20, 20)

        # Gắn vào scroll
        self.scroll_area.setWidget(self.grid_container)

        left_side.addWidget(self.scroll_area)

        # Khởi tạo Overlay (Sử dụng LoadingOverlay thay vì SolvingOverlay)
        self.overlay = LoadingOverlay(self.scroll_area)
        
        # Status Bar phía dưới cùng bên trái
        self.status_bar = QLabel("Ready.")
        left_side.addWidget(self.status_bar)
        
        # --- BÊN PHẢI: INFO PANEL ---
        right_side = QVBoxLayout()
        self.info_card = QFrame()
        self.info_card.setObjectName("infoPanel")
        self.info_card.setFixedWidth(300)
        
        info_layout = QVBoxLayout(self.info_card)
        self.result_info = QLabel("Ready.")
        self.result_info.setWordWrap(True)
        self.result_info.setObjectName("infoLabel")
        
        step_group = QGroupBox("Visualization Controls")
        step_vbox = QVBoxLayout()
        self.step_list = QListWidget()
        step_vbox.addWidget(self.step_list)
        step_group.setLayout(step_vbox)

        self.stats_btn = QPushButton("View Full Stats")
        self.stats_btn.setObjectName("resultBtn")

        info_layout.addWidget(QLabel("<b>STATISTICS</b>"))
        self.result_info.setFixedHeight(150)
        info_layout.addWidget(self.result_info)
        info_layout.addWidget(step_group, 1)

        # --- THÊM KHỐI AUTO RUN ---
        auto_group = QGroupBox("Auto Run")
        auto_vbox = QVBoxLayout(auto_group)

        btn_hbox = QHBoxLayout()
        self.btn_auto_run = QPushButton("Run")
        self.btn_auto_run.setObjectName("runAutoBtn")
        self.btn_auto_run.setProperty("state", "run")

        self.btn_auto_stop = QPushButton("Stop")
        self.btn_auto_stop.setObjectName("stopAutoBtn")
        self.btn_auto_stop.setProperty("state", "stop")
        self.btn_auto_stop.setEnabled(False) # Ẩn nút Stop khi chưa chạy

        btn_hbox.addWidget(self.btn_auto_run)
        btn_hbox.addWidget(self.btn_auto_stop)

        self.speed_label = QLabel("Speed: 10 step/s")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(3, 200) # Từ 3 đến 200 step/s
        self.speed_slider.setValue(10)

        auto_vbox.addLayout(btn_hbox)
        auto_vbox.addWidget(self.speed_label)
        auto_vbox.addWidget(self.speed_slider)

        info_layout.addWidget(auto_group)
        # --- KẾT THÚC KHỐI AUTO RUN ---

        info_layout.addWidget(self.stats_btn)
        right_side.addWidget(self.info_card)

        # Main assembly
        main_layout.addLayout(left_side, 3)
        main_layout.addLayout(right_side, 0)

        # Event connections
        self.puzzle_box.currentIndexChanged.connect(self.load_selected_puzzle)
        self.load_btn.clicked.connect(self.reload_input)
        self.load_data_btn.clicked.connect(self.load_data_from_json)
        self.run_btn.clicked.connect(self.run_solver)
        self.stats_btn.clicked.connect(self.show_stats)
        self.step_list.currentRowChanged.connect(self.go_to_step)
        self.btn_auto_run.clicked.connect(self.toggle_auto_run)
        self.btn_auto_stop.clicked.connect(self.toggle_pause)
        self.speed_slider.valueChanged.connect(self.update_speed)

    def _load_puzzles(self):
        if not os.path.exists(INPUT_DIR): return
        self.puzzles = load_all_puzzles(INPUT_DIR)
        self.puzzle_box.clear()
        for p in self.puzzles:
            self.puzzle_box.addItem(f"{p['id']} ({p['size']}x{p['size']})")
        if self.puzzles: self.load_selected_puzzle()

    def load_selected_puzzle(self):
        idx = self.puzzle_box.currentIndex()
        if idx < 0: return
        self.puzzle = self.puzzles[idx]
        self.current_steps = []
        self.step_list.clear()
        self.stop_auto_run()
        self.draw_grid()
        self.status_bar.setText(f"Loaded {self.puzzle['id']}")
        self.result_info.setText("Ready to solve.")

    # ------ Hiển thị list steps ------
    def populate_step_list(self):
        self.step_list.clear()
        if not self.current_steps: return
        
        for i, step in enumerate(self.current_steps):
            # Format chuẩn: [r, c, val, action]
            r, c, val, action = step
            if action == 0:
                act_str = "Given"
            elif action == 1:
                act_str = "Fill"
            else:
                act_str = "Remove"
                
            self.step_list.addItem(f"Step {i+1}: {act_str} '{val}' at ({r},{c})")

    # ------ Đọc JSON từ Outputs\ ------
    def load_data_from_json(self):
        if not self.puzzle: return
        
        # Chuyển input_XX thành output_XX
        input_id = self.puzzle['id']
        output_filename = input_id.replace("input_", "output_") + ".json"
        json_path = os.path.join(OUTPUT_DIR, output_filename)

        if not os.path.exists(json_path):
            QMessageBox.warning(self, "Not Found", f"Cannot find saved data at:\n{json_path}")
            return

        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            algo_name = self.algo_box.currentText()
            if algo_name not in data.get("algorithms", {}):
                QMessageBox.warning(self, "No Data", f"No data found for {algo_name} in JSON file.")
                return

            r = data["algorithms"][algo_name]

            # Cập nhật steps và UI
            self.current_steps = r.get("steps", [])
            self.populate_step_list()

            status_txt = "Solved" if r['status'] == 1 else "Failed/Timeout"
            mem = f"{r['memory_kb']} KB" if r.get('memory_kb') is not None else "N/A"

            info = (f"<b>[LOADED FROM JSON]</b><br>"
                    f"<b>Algorithm:</b> {algo_name}<br>"
                    f"<b>Status:</b> {status_txt}<br>"
                    f"<b>Time:</b> {r.get('time_ms', 0):.2f} ms<br>"
                    f"<b>Memory:</b> {mem}<br>"
                    f"<b>Inferences:</b> {r.get('inferences', 0)}<br>"
                    f"<b>Total Steps:</b> {len(self.current_steps)}")
            
            self.result_info.setText(info)
            self.status_bar.setText(f"Loaded from JSON for {algo_name}")

            # Tự động nhảy tới step cuối cùng để hiển thị kết quả
            if self.current_steps:
                self.step_list.setCurrentRow(len(self.current_steps) - 1)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse JSON:\n{e}")

    def reload_input(self):
        self.load_selected_puzzle()

    def draw_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        self.cells = []
        if not self.puzzle: return

        n = self.puzzle["size"]
        grid = self.puzzle["grid"]
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        for i in range(2 * n - 1):
            for j in range(2 * n - 1):
                if i % 2 == 0 and j % 2 == 0:
                    r, c = i // 2, j // 2
                    cell = Cell(r, c)
                    val = grid[r][c]
                    if val != 0:
                        cell.setText(str(val))
                        cell.setProperty("status", "given")
                    self.grid_layout.addWidget(cell, i, j)
                    self.cells.append(cell)
                elif i % 2 == 0 and j % 2 == 1:
                    val = hc[i // 2][j // 2]
                    text = "<" if val == 1 else ">" if val == -1 else ""
                    self.grid_layout.addWidget(QLabel(text), i, j, Qt.AlignCenter)
                elif i % 2 == 1 and j % 2 == 0:
                    val = vc[i // 2][j // 2]
                    text = "^" if val == 1 else "v" if val == -1 else ""
                    self.grid_layout.addWidget(QLabel(text), i, j, Qt.AlignCenter)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize_to_parent()

    def run_solver(self):
        if self.solving or not self.puzzle: return
        
        algo_name = self.algo_box.currentText()
        SolverClass = dict(SOLVERS)[algo_name]

        self.solving = True
        self.run_btn.setEnabled(False)
        self.status_bar.setText(f"Solving with {algo_name}...")

        self.overlay.resize_to_parent()
        self.overlay.setVisible(True)

        signals = SolverSignals()
        signals.finished.connect(self._on_solve_finished)
        signals.error.connect(self._on_solve_error)

        def worker():
            try:
                r = _run_with_timeout(SolverClass, self.puzzle)
                signals.finished.emit({algo_name: r})
            except Exception as e:
                signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_solve_finished(self, results):
        self.solving = False
        self.run_btn.setEnabled(True)
        self.overlay.setVisible(False)
        
        algo_name = list(results.keys())[0]
        r = results[algo_name]

        self.current_steps = r.get("steps") or []
        status_txt = {
            STATUS_SOLVED: "Solved", 
            STATUS_TIMEOUT: "Timeout", 
            STATUS_STEP_LIMIT: "Step limit",
            STATUS_UNSOLVABLE: "Unsolvable"
        }.get(r['status'], "Unknown")

        mem = f"{r['memory_kb']:.1f} KB" if r.get('memory_kb') is not None else "N/A"

        info = (f"<b>Algorithm:</b> {algo_name}<br>"
                f"<b>Status:</b> {status_txt}<br>"
                f"<b>Time:</b> {r['time_ms']:.2f} ms<br>"
                f"<b>Memory:</b> {mem}<br>"
                f"<b>Inferences:</b> {r.get('inferences', 0)}<br>"
                f"<b>Total Steps:</b> {len(self.current_steps)}")
        self.result_info.setText(info)
        self.status_bar.setText(f"Finished: {status_txt}")

        if self.current_steps:
            self.populate_step_list()
            self.step_list.setCurrentRow(len(self.current_steps) - 1)
        
        if r['status'] == STATUS_SOLVED and r.get('solution'):
            self._apply_solution_to_ui(r['solution'])

    def _apply_solution_to_ui(self, solution):
        for cell in self.cells:
            val = solution[cell.r][cell.c]
            if not cell.text():
                cell.setText(str(val))
                cell.setProperty("status", "fill")
                cell.style().unpolish(cell)
                cell.style().polish(cell)

    def go_to_step(self, row_idx):
        if not self.current_steps or row_idx < 0: return
        
        # Reset grid về trạng thái trống ban đầu
        initial_grid = self.puzzle["grid"]
        for cell in self.cells:
            if initial_grid[cell.r][cell.c] == 0:
                cell.setText("")
                cell.setProperty("status", "")
        
        # Áp dụng các steps từ đầu cho tới step đang chọn trong List (row_idx)
        for i in range(row_idx + 1):
            r, c, val, action = self.current_steps[i]
            target_cell = next((cell for cell in self.cells if cell.r == r and cell.c == c), None)
            
            if target_cell:
                # Dựa theo format JSON
                if action == 0 or action == 1:
                    target_cell.setText(str(val))
                    target_cell.setProperty("status", "fill" if action == 1 else "given")
                elif action == 2:
                    target_cell.setText("")
                    target_cell.setProperty("status", "remove")
        
        # Cập nhật giao diện
        for cell in self.cells:
            cell.style().unpolish(cell)
            cell.style().polish(cell)

    # ==================== AUTO RUN LOGIC ====================
    def update_speed(self):
        speed = self.speed_slider.value()
        self.speed_label.setText(f"Speed: {speed} step/s")
        # Cập nhật tốc độ ngay lập tức nếu đang chạy
        if self.is_auto_running and self.auto_timer.isActive():
            self.auto_timer.setInterval(int(1000 / speed))

    def toggle_auto_run(self):
        if not self.current_steps:
            return

        if not self.is_auto_running:
            # BẮT ĐẦU CHẠY
            self.is_auto_running = True
            
            # Đổi thành "End" (Đỏ)
            self.btn_auto_run.setText("End")
            self.btn_auto_run.setProperty("state", "end")
            self.btn_auto_run.style().unpolish(self.btn_auto_run)
            self.btn_auto_run.style().polish(self.btn_auto_run)

            # Reset nút kia về "Stop" (Đỏ)
            self.btn_auto_stop.setEnabled(True)
            self.btn_auto_stop.setText("Stop")
            self.btn_auto_stop.setProperty("state", "stop")
            self.btn_auto_stop.style().unpolish(self.btn_auto_stop)
            self.btn_auto_stop.style().polish(self.btn_auto_stop)

            # Bắt đầu chạy lại từ step 0
            self.step_list.setCurrentRow(0)

            speed = self.speed_slider.value()
            self.auto_timer.start(int(1000 / speed))
        else:
            # END
            # Nhảy tới step cuối
            self.step_list.setCurrentRow(len(self.current_steps) - 1)
            
            # Gọi hàm dừng auto
            self.stop_auto_run()

    def toggle_pause(self):
        if not self.is_auto_running:
            return
        
        if self.auto_timer.isActive():
            # STOP
            self.auto_timer.stop()
            
            # Đổi thành "Resume" (Xanh)
            self.btn_auto_stop.setText("▶ Resume")
            self.btn_auto_stop.setProperty("state", "resume")
            self.btn_auto_stop.style().unpolish(self.btn_auto_stop)
            self.btn_auto_stop.style().polish(self.btn_auto_stop)
        else:
            # RESUME
            speed = self.speed_slider.value()
            self.auto_timer.start(int(1000 / speed))
            
            # Đổi thành "Stop" (Đỏ)
            self.btn_auto_stop.setText("Stop")
            self.btn_auto_stop.setProperty("state", "stop")
            self.btn_auto_stop.style().unpolish(self.btn_auto_stop)
            self.btn_auto_stop.style().polish(self.btn_auto_stop)

    def stop_auto_run(self):
        self.is_auto_running = False
        self.auto_timer.stop()

        # Reset nút 1 về "Run" (Màu Xanh)
        self.btn_auto_run.setText("Run")
        self.btn_auto_run.setProperty("state", "run")
        self.btn_auto_run.style().unpolish(self.btn_auto_run)
        self.btn_auto_run.style().polish(self.btn_auto_run)

        # Reset nút 2 về "Stop" và vô hiệu hóa
        self.btn_auto_stop.setText("Stop")
        self.btn_auto_stop.setProperty("state", "stop")
        self.btn_auto_stop.setEnabled(False)
        self.btn_auto_stop.style().unpolish(self.btn_auto_stop)
        self.btn_auto_stop.style().polish(self.btn_auto_stop)

    def auto_step(self):
        current_row = self.step_list.currentRow()
        max_row = len(self.current_steps) - 1
        
        # Nhảy xuống 1 step
        if current_row < max_row:
            # Chọn row mới, sự kiện go_to_step sẽ tự động được gọi do chúng ta đã connect tín hiệu
            self.step_list.setCurrentRow(current_row + 1)
        else:
            # Đã tới step cuối -> tự động tắt Auto Run
            self.stop_auto_run()

    def _on_solve_error(self, msg):
        self.solving = False
        self.run_btn.setEnabled(True)
        self.overlay.setVisible(False)
        self.status_bar.setText(f"Error: {msg}")

    def show_stats(self):
        try:
            import visualize_stats
            visualize_stats.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load stats: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    css_path = os.path.join(os.path.dirname(__file__), "frontend.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    
    win = App()
    win.show()
    sys.exit(app.exec_())