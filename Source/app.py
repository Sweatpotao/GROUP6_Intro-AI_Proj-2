import sys
import os
import threading
import json
import time
import gc
import glob
import importlib

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
import visualize_stats
from main         import _run_with_timeout, SOLVERS

INPUT_DIR  = os.path.join(os.path.dirname(__file__), "Inputs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Outputs")
SOLVERS = [s for s in SOLVERS if s[0] != "brute_force"]

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
        self.message = "⚡ Solving..."

    def set_message(self, msg):
        self.message = msg
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # nền blur giả lập
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # box giữa
        box_rect = self.rect().adjusted(
            self.width()//4, self.height()//3,
            -self.width()//4, -self.height()//3
        )

        painter.setBrush(QColor(255, 255, 255, 230))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(box_rect, 20, 20)

        # text
        painter.setPen(QPen(QColor("#8e44ad")))
        painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
        painter.drawText(box_rect, Qt.AlignCenter | Qt.TextWordWrap, self.message)

    def resize_to_parent(self):
        if self.parent():
            self.setGeometry(self.parent().rect())

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Futoshiki Solver")

        self.puzzles = []
        self.puzzle = None
        self.cells = []
        self.current_steps = []
        self.solving = False

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.auto_step)
        self.is_auto_running = False

        # Lưu answer từ JSON
        self.answer_data = None
        self.showing_answer = False

        self._build_ui()
        self._load_puzzles()

        self.showMaximized()

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
        self.algo_box.addItem("ALL SOLVER")
        self.algo_box.addItems([name for name, _ in SOLVERS])
        self.algo_box.setCurrentIndex(1)
        self.load_btn = QPushButton("Reset Map")
        self.load_btn.setObjectName("loadBtn")
        self.run_btn = QPushButton("Solve")
        self.run_btn.setObjectName("solveBtn")
        self.load_data_btn = QPushButton("Show Result")
        self.load_data_btn.setObjectName("showResultBtn")
        
        t_layout.addWidget(QLabel("Puzzle:"))
        t_layout.addWidget(self.puzzle_box)
        t_layout.addWidget(QLabel("Algo:"))
        t_layout.addWidget(self.algo_box)
        t_layout.addStretch()
        t_layout.addWidget(self.load_btn)
        t_layout.addWidget(self.load_data_btn)
        t_layout.addWidget(self.run_btn)
        left_side.addWidget(toolbar)

        # --- LABEL THÔNG BÁO BATCH MODE ---
        self.lbl_batch_status = QLabel("")
        self.lbl_batch_status.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 16px;")
        self.lbl_batch_status.setAlignment(Qt.AlignCenter)
        self.lbl_batch_status.setVisible(False)
        left_side.addWidget(self.lbl_batch_status)
        # ---------------------------------

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
        self.status_bar.setStyleSheet("font-size: 20px; color: #7f8c8d;")
        left_side.addWidget(self.status_bar)
        
        # --- BÊN PHẢI: INFO PANEL ---
        right_side = QVBoxLayout()
        self.info_card = QFrame()
        self.info_card.setObjectName("infoPanel")
        self.info_card.setFixedWidth(330)
        
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
        self.stats_btn.setEnabled(False)

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
        self.puzzle_box.currentIndexChanged.connect(self.disable_stats_btn)
        self.algo_box.currentIndexChanged.connect(self.disable_stats_btn)
        self.load_btn.clicked.connect(self.reload_input)
        self.load_data_btn.pressed.connect(self.show_answer)
        self.load_data_btn.released.connect(self.hide_answer)
        self.run_btn.clicked.connect(self.run_solver)
        self.stats_btn.clicked.connect(self.show_stats)
        self.step_list.currentRowChanged.connect(self.go_to_step)
        self.btn_auto_run.clicked.connect(self.toggle_auto_run)
        self.btn_auto_stop.clicked.connect(self.toggle_pause)
        self.speed_slider.valueChanged.connect(self.update_speed)

    def set_ui_locked(self, locked):
        self.puzzle_box.setDisabled(locked)
        self.algo_box.setDisabled(locked)
        self.load_btn.setDisabled(locked)
        self.load_data_btn.setDisabled(locked)
        self.run_btn.setDisabled(locked)
        self.set_visualize_controls_enabled(not locked)
    
    def disable_stats_btn(self):
        self.stats_btn.setEnabled(False)

    def _load_puzzles(self):
        try:
            if not os.path.exists(INPUT_DIR): return

            self.puzzles = load_all_puzzles(INPUT_DIR)
            self.puzzle_box.clear()

            self.puzzle_box.addItem("ALL INPUT")
            for p in self.puzzles:
                self.puzzle_box.addItem(f"{p['id']} ({p['size']}x{p['size']})")

            if len(self.puzzles) > 0:
                    # Đặt mặc định là Input đầu tiên (Index 1 vì Index 0 là ALL INPUT)
                    self.puzzle_box.setCurrentIndex(1) 
                    self.load_selected_puzzle()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load puzzles: {e}")

    def load_selected_puzzle(self):
        idx = self.puzzle_box.currentIndex()
        
        if idx < 0: return
        elif idx == 0:
            self.status_bar.setText("Ready for ALL INPUT batch run.")
            return
            
        real_idx = idx - 1
        if real_idx < 0: return
        
        self.puzzle = self.puzzles  [real_idx]
        self.current_steps = []
        self.step_list.clear()
        self.stop_auto_run()
        
        self.answer_data = None

        self.draw_grid()
        self.status_bar.setText(f"Loaded {self.puzzle['id']}")
        self.result_info.setText("Ready to solve.")

    # ================== Hiển thị list step ==================
    def populate_step_list(self):
        # Khóa UI và Tín hiệu để tối ưu
        self.step_list.setUpdatesEnabled(False)
        self.step_list.blockSignals(True)

        try:
            self.step_list.clear()
            
            if not self.current_steps:
                return # Nhảy xuống finally để mở lại UI

            items = []
            for i, step in enumerate(self.current_steps):
                # Format chuẩn: [r, c, val, action]
                r, c, val, action = step
                
                if action == 0:
                    act_str = "Given"
                elif action == 1:
                    act_str = "Fill"
                else:
                    act_str = "Remove"
                    
                items.append(f"Step {i+1}: {act_str} '{val}' at ({r},{c})")

            self.step_list.addItems(items)
        finally:
            # LUÔN unlock giao diện bất kể có lỗi hay không
            self.step_list.blockSignals(False)
            self.step_list.setUpdatesEnabled(True)
            self.step_list.update()

    # ================= Load answer từ input =================
    def load_answer_data(self):
        if not self.puzzle:
            return
        
        input_id = self.puzzle['id']
        input_filename = input_id + ".json"
        json_path = os.path.join(INPUT_DIR, input_filename)
        
        # Kiểm tra file có tồn tại không
        if not os.path.exists(json_path):
            QMessageBox.warning(self, "Not Found", f"Cannot find input file at:\n{json_path}")
            return
        
        # Thử đọc file JSON
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Lấy mảng "answer" từ JSON
            self.answer_data = data.get("answer")
            
            if not self.answer_data:
                QMessageBox.warning(self, "No Answer", "No 'answer' field found in input JSON file.")
                self.answer_data = None
                return
            
            self.status_bar.setText(f"Answer loaded for {input_id}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse JSON:\n{e}")
            self.answer_data = None
    
    def show_answer(self):
        if not self.puzzle:
            return
        
        if not self.answer_data:
            self.load_answer_data()
            if not self.answer_data:
                return
        
        # Đánh dấu là đang hiển thị answer
        self.showing_answer = True
        self.status_bar.setText("🔍 Showing answer...")
        initial_grid = self.puzzle["grid"]
        
        # Loop qua tất cả các cell
        for cell in self.cells:
            # Nếu là Given thì bỏ qua
            if initial_grid[cell.r][cell.c] != 0:
                continue
            
            # Với ô trống (giá trị = 0), lấy đáp án
            answer_val = self.answer_data[cell.r][cell.c]
            
            # Ghi giá trị lên cell
            cell.setText(str(answer_val))
            
            # Đổi status thành "answer" (xanh lam)
            cell.setProperty("status", "answer")
        
        # Cập nhật giao diện
        for cell in self.cells:
            cell.style().unpolish(cell)
            cell.style().polish(cell)

    def hide_answer(self):
        if not self.showing_answer:
            return
        
        # Đánh dấu là không hiển thị answer nữa
        self.showing_answer = False
        self.status_bar.setText("Answer hidden.")

        current_row = self.step_list.currentRow()
        # KIỂM TRA: Nếu đã chạy giải thuật (có steps) và đang chọn 1 step nào đó
        if self.current_steps and current_row >= 0:
            # Khôi phục lại đúng trạng thái của step đó
            self.go_to_step(current_row)
        else:
            # Nếu chưa chạy giải thuật (chưa bấm Solve), thì mới xóa về lưới trống
            initial_grid = self.puzzle["grid"]
            for cell in self.cells:
                if initial_grid[cell.r][cell.c] == 0:
                    cell.setText("")
                    cell.setProperty("status", "")
                else:
                    cell.setProperty("status", "given")
        
        # Cập nhật giao diện
        for cell in self.cells:
            cell.style().unpolish(cell)
            cell.style().polish(cell)

    # ========================================================

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
        if self.solving: return
        
        p_idx = self.puzzle_box.currentIndex()
        s_idx = self.algo_box.currentIndex()

        self.batch_tasks = []
        
        # Nhận diện TH chạy
        if p_idx == 0 and s_idx != 0: self.run_mode = "all_input"
        elif p_idx != 0 and s_idx == 0: self.run_mode = "all_solver"
        elif p_idx == 0 and s_idx == 0: self.run_mode = "all_all"
        else: self.run_mode = "single"

        # Phân tích 4 trường hợp:
        # Nếu == 0 (ALL), chạy từ 1 đến hết. Nếu != 0 (1 cái), chỉ chạy đúng index đó.
        puzzles_to_run = range(1, len(self.puzzles) + 1) if p_idx == 0 else [p_idx]
        solvers_to_run = range(1, len(SOLVERS) + 1) if s_idx == 0 else [s_idx]

        for p in puzzles_to_run:
            for s in solvers_to_run:
                self.batch_tasks.append((p, s))

        self.is_batch_mode = len(self.batch_tasks) > 1
        # Khóa cứng UI
        self.set_ui_locked(True)

        if self.is_batch_mode:
            self.lbl_batch_status.setVisible(True)
            for f in glob.glob(os.path.join(OUTPUT_DIR, "output_*.json")): os.remove(f)
            self.run_next_batch_task()
        else:
            self.lbl_batch_status.setVisible(False)
            self.run_single_task(p_idx, s_idx)

    def run_next_batch_task(self):
        if not self.batch_tasks:
            # Đã chạy xong toàn bộ (Hết Queue)
            self.is_batch_mode = False
            self.lbl_batch_status.setVisible(False)
            self.status_bar.setText("Batch execution finished.")
            self.overlay.setVisible(False)
            self.run_btn.setEnabled(True)
            self.solving = False
            
            # Mở khóa lại UI
            self.set_ui_locked(False)

            # Mở khóa Visualize
            self.stats_btn.setEnabled(True)
            return

        p_idx, s_idx = self.batch_tasks.pop(0)
        
        # Cập nhật UI để load puzzle mới (Tạm tắt tín hiệu để tránh load 2 lần)
        self.puzzle_box.blockSignals(True)
        self.puzzle_box.setCurrentIndex(p_idx)
        self.puzzle_box.blockSignals(False)
        self.load_selected_puzzle()
        self.algo_box.setCurrentIndex(s_idx)

        self.run_single_task(p_idx, s_idx)

    def run_single_task(self, p_idx, s_idx):
        self.solving = True
        
        puzzle = self.puzzles[p_idx - 1]
        solver_name, SolverClass = SOLVERS[s_idx - 1]

        total_p = len(self.puzzles)
        total_s = len(SOLVERS)

        # Format Text thông báo theo 4 trường hợp
        if self.run_mode == "all_input":
            msg = f"{solver_name}\n⚡ Solving {puzzle['id']} ({p_idx}/{total_p})..."
        elif self.run_mode == "all_solver":
            msg = f"INPUT {puzzle['id']}\n⚡ Solving {solver_name}... ({s_idx}/{total_s})"
        elif self.run_mode == "all_all":
            msg = f"⚡ Running all Experiments...\nInput: {puzzle['id']} ({p_idx}/{total_p}) - Solver: {solver_name} ({s_idx}/{total_s})"
        else:
            msg = f"⚡ Solving with {solver_name}..."


        if self.is_batch_mode:
            self.lbl_batch_status.setText(msg.replace('\n', ' - ').replace('⚡ ', ''))

        self.status_bar.setText(f"Solving with {solver_name}...")
        self.overlay.set_message(msg)
        self.overlay.resize_to_parent()
        self.overlay.setVisible(True)

        signals = SolverSignals()
        signals.finished.connect(self._on_solve_finished)
        signals.error.connect(self._on_solve_error)

        # Lưu lại thời gian bắt đầu để tính delay 0,75s
        self.solve_start_time = time.time()

        def worker():
            try:
                r = _run_with_timeout(SolverClass, puzzle)
                
                # Đọc file cũ nếu có để merge, tránh ghi đè solver khác
                number   = puzzle['id'].replace("input_", "")
                out_path = os.path.join(OUTPUT_DIR, f"output_{number}.json")
                merged   = {}
                if os.path.exists(out_path):
                    try:
                        with open(out_path, "r", encoding="utf-8") as f:
                            merged = json.load(f).get("algorithms", {})
                    except Exception:
                        merged = {}
                merged[solver_name] = r

                save_output(puzzle['id'], puzzle['size'], r.get('solution'), merged)
                signals.finished.emit({solver_name: r})
            except Exception as e:
                signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_solve_finished(self, results):
        # Tính toán thời gian đã trôi qua
        elapsed = time.time() - self.solve_start_time
        
        # Nếu tốc độ giải < 0,75s, delay phần thời gian còn thiếu
        if elapsed < 1:
            delay_ms = int((1 - elapsed) * 750)
            QTimer.singleShot(delay_ms, lambda: self._process_solve_results(results))
        else:
            self._process_solve_results(results)

    def _process_solve_results(self, results):
        self.solving = False
        self.overlay.setVisible(False)
        
        algo_name = list(results.keys())[0]
        r = results[algo_name]

        # 1. Giữ bản sao đầy đủ các bước để lưu vào batch_results (ghi JSON)
        full_steps = r.get("steps") or []
        
        if self.is_batch_mode:
            p_id = self.puzzle["id"]
            # Khởi tạo dict nếu chưa có (tránh lỗi crash lần trước)
            if not hasattr(self, 'batch_results'): self.batch_results = {}
            if p_id not in self.batch_results:
                self.batch_results[p_id] = {"input_id": p_id, "size": self.puzzle["size"], "solution": r.get("solution"), "algorithms": {}}
            
            # Lưu full kết quả vào bộ nhớ
            self.batch_results[p_id]["algorithms"][algo_name] = r

        # 2. Xử lý UI ListWidget (Giảm lag)
        self.step_list.clear() 

        if self.is_batch_mode:
            # TRƯỜNG HỢP BATCH: Thủ công thêm 1 dòng, không gọi hàm populate_step_list()
            if full_steps:
                last_idx = len(full_steps)
                self.step_list.addItem(f"Step {last_idx} (Final Result)")
                
                # Gán current_steps chỉ chứa 1 cái cuối để Grid hiển thị đáp án
                self.current_steps = [full_steps[-1]]
                self.step_list.setCurrentRow(0)
            else:
                self.current_steps = []
        else:
            # TRƯỜNG HỢP LẺ: Chạy bình thường
            self.current_steps = full_steps
            if self.current_steps:
                self.populate_step_list()
                self.step_list.setCurrentRow(len(self.current_steps) - 1)

        # 3. Hiện thông số
        status_txt = {
            STATUS_SOLVED: "Solved", 
            STATUS_TIMEOUT: "Timeout", 
            STATUS_STEP_LIMIT: "Step limit",
            STATUS_UNSOLVABLE: "Unsolvable"
        }.get(r['status'], "Unknown")

        mem = f"{r['memory_kb']:.1f} KB" if r.get('memory_kb') is not None else "N/A"
        
        # Chỗ này hiện số bước thực tế (vd: 20000) để theo dõi
        total_display = len(full_steps)
        if self.is_batch_mode and total_display > 1:
            total_display = f"{total_display}"

        info = (f"<b>Algorithm:</b> {algo_name}<br>"
                f"<b>Status:</b> {status_txt}<br>"
                f"<b>Time:</b> {r['time_ms']:.2f} ms<br>"
                f"<b>Memory:</b> {mem}<br>"
                f"<b>Inferences:</b> {r.get('inferences', 0)}<br>"
                f"<b>Total Steps:</b> {total_display}")
        
        self.result_info.setText(info)
        self.status_bar.setText(f"Finished: {status_txt}")

        if r['status'] == STATUS_SOLVED and r.get('solution'):
            self._apply_solution_to_ui(r['solution'])
        
        # 4. Điều hướng Batch tiếp theo
        if self.is_batch_mode:
            QTimer.singleShot(1500, self.run_next_batch_task)
        else:
            self.set_ui_locked(False)

        # 5. Dọn rác (dọn temp-value nằm trong RAM)
        gc.collect()

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

    # ========================================================

    def _on_solve_error(self, msg):
        self.solving = False
        self.run_btn.setEnabled(True)
        self.overlay.setVisible(False)
        self.set_ui_locked(False)
        self.status_bar.setText(f"Error: {msg}")

    def set_visualize_controls_enabled(self, enabled):
        self.step_list.setEnabled(enabled)
        self.speed_slider.setEnabled(enabled)
        self.btn_auto_run.setEnabled(enabled)
        if hasattr(self, 'btn_show_result'):
            self.btn_show_result.setEnabled(enabled)
        
        if not enabled:
            self.btn_auto_stop.setEnabled(False)

    def show_stats(self):
        mode = getattr(self, "run_mode", "all_all")
        try:
            # Khóa btn, đổi text
            self.stats_btn.setDisabled(True)
            self.stats_btn.setText("Generating...")
            QApplication.processEvents()
            
            # Chạy visualize
            importlib.reload(visualize_stats)
            visualize_stats.show(run_mode=mode)

            # Mở btn trở lại
            self.stats_btn.setText("View Full Stats")
            self.stats_btn.setEnabled(True)
        except Exception as e:
            # Đảm bảo btn được mở lại nếu có lỗi xảy ra
            self.stats_btn.setText("View Full Stats")
            self.stats_btn.setEnabled(True)

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