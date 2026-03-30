import sys
import os
import threading

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont

sys.path.insert(0, os.path.dirname(__file__))

from core.parser  import load_all_puzzles
from core.logger  import save_output, load_output, rebuild_log, list_outputs
from core.config  import TIME_LIM, STATUS_SOLVED, STATUS_TIMEOUT, STATUS_STEP_LIMIT, STATUS_UNSOLVABLE
from main         import _run_with_timeout, SOLVERS, run_puzzle

INPUT_DIR  = os.path.join(os.path.dirname(__file__), "Inputs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Outputs")

# ---------------------------------------------------------------------------
# Signal bridge: dùng để gửi kết quả từ worker thread về main (UI) thread
# ---------------------------------------------------------------------------

class SolverSignals(QObject):
    finished = pyqtSignal(dict)   # emit khi solver xong
    error    = pyqtSignal(str)    # emit khi có lỗi


# ---------------------------------------------------------------------------
# Cell widget
# ---------------------------------------------------------------------------

class Cell(QLabel):
    def __init__(self, r, c):
        super().__init__("")
        self.r = r
        self.c = c
        self.setFixedSize(60, 60)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial", 18))
        self.setObjectName("cell")
        self.setProperty("status", "")


# ---------------------------------------------------------------------------
# Result window - hiển thị stats + điều khiển step-by-step
# ---------------------------------------------------------------------------

class ResultWindow(QWidget):
    def __init__(self, algo_name: str, result: dict, parent):
        super().__init__()
        self.setWindowTitle(f"Result - {algo_name}")
        self.resize(420, 320)

        self.parent_app = parent
        self.steps      = result.get("steps") or []
        self.step_index = 0

        layout = QVBoxLayout()

        # Status label
        status = result.get("status")
        status_map = {
            STATUS_SOLVED:     "Solved",
            STATUS_UNSOLVABLE: "Unsolvable",
            STATUS_TIMEOUT:    "Timeout",
            STATUS_STEP_LIMIT: "Step limit",
        }
        status_label = status_map.get(status, "Unknown")

        info_text = (
            f"Algorithm : {algo_name}\n"
            f"Status    : {status_label}\n"
            f"Time      : {result['time_ms']:.2f} ms\n"      if result.get('time_ms') is not None else
            f"Algorithm : {algo_name}\nStatus    : {status_label}\nTime      : N/A\n"
        )
        # Rebuild info text properly
        t   = f"{result['time_ms']:.2f} ms"   if result.get("time_ms")    is not None else "N/A"
        mem = f"{result['memory_kb']:.1f} KB"  if result.get("memory_kb")  is not None else "N/A"
        inf = str(result["inferences"])         if result.get("inferences") is not None else "N/A"

        self.info = QLabel(
            f"Algorithm : {algo_name}\n"
            f"Status    : {status_label}\n"
            f"Time      : {t}\n"
            f"Memory    : {mem}\n"
            f"Inferences: {inf}\n"
            f"Steps saved: {len(self.steps)}"
        )
        self.info.setFont(QFont("Courier New", 11))
        layout.addWidget(self.info)

        # Buttons
        btn_layout = QHBoxLayout()
        self.step_btn   = QPushButton("Step by Step")
        self.stop_btn   = QPushButton("Stop")
        self.resume_btn = QPushButton("Resume")
        self.stop_btn.setObjectName("stopBtn")
        self.resume_btn.setObjectName("resumeBtn")
        btn_layout.addWidget(self.step_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.resume_btn)
        layout.addLayout(btn_layout)

        # Speed slider
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(1000)
        self.speed_slider.setValue(200)
        self.speed_slider.setTickInterval(100)
        speed_layout.addWidget(self.speed_slider)
        layout.addLayout(speed_layout)

        self.setLayout(layout)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.play_step)

        # Events
        self.step_btn.clicked.connect(self.start_steps)
        self.stop_btn.clicked.connect(self.timer.stop)
        self.resume_btn.clicked.connect(lambda: self.timer.start(self.speed_slider.value()))

    def start_steps(self):
        if not self.steps:
            QMessageBox.warning(self, "No steps", "No steps available for this result.")
            return
        self.parent_app.draw_grid()   # reset lưới về trạng thái ban đầu
        self.step_index = 0
        self.timer.start(self.speed_slider.value())

    def play_step(self):
        if self.step_index >= len(self.steps):
            self.timer.stop()
            return

        r, c, val, action = self.steps[self.step_index]

        for cell in self.parent_app.cells:
            if cell.r == r and cell.c == c:
                if action == 1:   # assign
                    cell.setText(str(val))
                    cell.setProperty("status", "fill")
                elif action == 2:  # backtrack
                    cell.setText("")
                    cell.setProperty("status", "remove")
                else:              # given (action == 0)
                    cell.setText(str(val))
                    cell.setProperty("status", "given")
                cell.style().unpolish(cell)
                cell.style().polish(cell)

        self.step_index += 1


# ---------------------------------------------------------------------------
# Main app window
# ---------------------------------------------------------------------------

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Futoshiki Solver")
        self.resize(960, 860)

        # Data
        self.puzzles     = []
        self.puzzle      = None   # puzzle dict hiện tại
        self.cells       = []
        self.result_data = None   # dict: algo_name -> result
        self.solving     = False

        self._build_ui()
        self._load_puzzles()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # ===== TOP: chọn puzzle + algorithm =====
        top = QHBoxLayout()
        top.setSpacing(6)

        self.puzzle_box = QComboBox()
        self.puzzle_box.setMinimumWidth(160)
        self.algo_box = QComboBox()
        self.algo_box.setMinimumWidth(160)
        self.algo_box.addItems([name for name, _ in SOLVERS])

        # Load: đọc kết quả từ output_XX.json (nhanh, không delay)
        self.load_btn  = QPushButton("Load")
        # Run: chạy trực tiếp thuật toán (có thể chậm)
        self.run_btn   = QPushButton("Run")
        self.stats_btn = QPushButton("View Stats")

        self.load_btn.setObjectName("loadBtn")
        self.run_btn.setObjectName("solveBtn")
        self.stats_btn.setObjectName("resultBtn")

        top.addWidget(QLabel("Puzzle:"))
        top.addWidget(self.puzzle_box)
        top.addSpacing(12)
        top.addWidget(QLabel("Algorithm:"))
        top.addWidget(self.algo_box)
        top.addSpacing(12)
        top.addWidget(self.load_btn)
        top.addWidget(self.run_btn)
        top.addWidget(self.stats_btn)
        layout.addLayout(top)

        # ===== GRID =====
        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignCenter)
        self.grid_layout.setHorizontalSpacing(6)
        self.grid_layout.setVerticalSpacing(6)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)

        self.grid_panel = QWidget()
        self.grid_panel.setObjectName("gridPanel")
        self.grid_panel.setLayout(self.grid_layout)
        layout.addWidget(self.grid_panel)

        # ===== BOTTOM: result button =====
        bottom = QHBoxLayout()
        self.result_btn = QPushButton("Show Result / Visualize")
        self.result_btn.setObjectName("resultBtn")
        self.result_btn.setEnabled(False)
        bottom.addStretch()
        bottom.addWidget(self.result_btn)
        bottom.addStretch()
        layout.addLayout(bottom)

        # ===== STATUS BAR =====
        self.status_bar = QLabel("Ready.")
        self.status_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_bar)

        self.setLayout(layout)

        # Events
        self.puzzle_box.currentIndexChanged.connect(self.load_selected_puzzle)
        self.load_btn.clicked.connect(self.load_from_output)
        self.run_btn.clicked.connect(self.run_solver)
        self.result_btn.clicked.connect(self.show_result)
        self.stats_btn.clicked.connect(self.show_stats)

    # ------------------------------------------------------------------
    # Load puzzles từ Inputs/
    # ------------------------------------------------------------------

    def _load_puzzles(self):
        if not os.path.exists(INPUT_DIR):
            self.status_bar.setText("Inputs/ folder not found. Run generate_inputs.py first.")
            return

        try:
            self.puzzles = load_all_puzzles(INPUT_DIR)
        except FileNotFoundError:
            self.status_bar.setText("No input files found. Run generate_inputs.py first.")
            return

        self.puzzle_box.clear()
        for p in self.puzzles:
            self.puzzle_box.addItem(f"{p['id']}  ({p['size']}x{p['size']})")

        if self.puzzles:
            self.load_selected_puzzle()

    def load_selected_puzzle(self):
        idx = self.puzzle_box.currentIndex()
        if idx < 0 or idx >= len(self.puzzles):
            return
        self.puzzle      = self.puzzles[idx]
        self.result_data = None
        self.result_btn.setEnabled(False)
        self.draw_grid()
        self.status_bar.setText(f"Loaded: {self.puzzle['id']}  ({self.puzzle['size']}x{self.puzzle['size']})")

    # ------------------------------------------------------------------
    # Vẽ lưới
    # ------------------------------------------------------------------

    def draw_grid(self):
        # Xóa lưới cũ
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self.cells = []

        if not self.puzzle:
            return

        grid = self.puzzle["grid"]
        hc   = self.puzzle["h_constraints"]
        vc   = self.puzzle["v_constraints"]
        n    = self.puzzle["size"]
        size = 2 * n - 1

        for i in range(size):
            for j in range(size):
                if i % 2 == 0 and j % 2 == 0:
                    # Ô số
                    r, c = i // 2, j // 2
                    cell = Cell(r, c)
                    val  = grid[r][c]
                    if val != 0:
                        cell.setText(str(val))
                        cell.setProperty("status", "given")
                    self.grid_layout.addWidget(cell, i, j)
                    self.cells.append(cell)

                elif i % 2 == 0 and j % 2 == 1:
                    # Ràng buộc ngang
                    val   = hc[i // 2][j // 2]
                    text  = "<" if val == 1 else ">" if val == -1 else ""
                    label = QLabel(text)
                    label.setAlignment(Qt.AlignCenter)
                    label.setObjectName("constraint")
                    label.setFixedSize(20, 60)
                    self.grid_layout.addWidget(label, i, j)

                elif i % 2 == 1 and j % 2 == 0:
                    # Ràng buộc dọc
                    val   = vc[i // 2][j // 2]
                    text  = "^" if val == 1 else "v" if val == -1 else ""
                    label = QLabel(text)
                    label.setAlignment(Qt.AlignCenter)
                    label.setObjectName("constraint")
                    label.setFixedSize(60, 20)
                    self.grid_layout.addWidget(label, i, j)

    # ------------------------------------------------------------------
    # Load from output_XX.json - nhanh, không delay
    # ------------------------------------------------------------------

    def load_from_output(self):
        if not self.puzzle:
            QMessageBox.warning(self, "No puzzle", "Please select a puzzle first.")
            return

        puzzle_id = self.puzzle["id"]
        try:
            data = load_output(puzzle_id)
        except FileNotFoundError:
            QMessageBox.warning(
                self, "No output",
                "No output found for this puzzle.\nPlease run main.py first."
            )
            return

        algo_name = self.algo_box.currentText()
        algos     = data.get("algorithms", {})

        if algo_name not in algos:
            QMessageBox.warning(
                self, "No data",
                "No result for this algorithm in the output file."
            )
            return

        r = algos[algo_name]

        if self.result_data is None:
            self.result_data = {}
        self.result_data[algo_name] = r

        status_map = {
            STATUS_SOLVED:     "Solved",
            STATUS_UNSOLVABLE: "Unsolvable",
            STATUS_TIMEOUT:    "Timeout",
            STATUS_STEP_LIMIT: "Step limit",
        }
        status = r.get("status")
        label  = status_map.get(status, "Unknown")
        t      = f"{r['time_ms']:.2f} ms" if r.get("time_ms") is not None else "N/A"
        self.status_bar.setText(f"[{algo_name}] {label}  |  Time: {t}  (loaded from file)")

        if status == STATUS_SOLVED and r.get("solution"):
            self._draw_solution(r["solution"])

        self.result_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Run solver - chạy trực tiếp, có thể chậm
    # ------------------------------------------------------------------

    def run_solver(self):
        if not self.puzzle:
            QMessageBox.warning(self, "No puzzle", "Please select a puzzle first.")
            return
        if self.solving:
            QMessageBox.warning(self, "Busy", "A solver is already running.")
            return

        algo_name   = self.algo_box.currentText()
        SolverClass = dict(SOLVERS)[algo_name]

        self.solving = True
        self.run_btn.setEnabled(False)
        self.result_btn.setEnabled(False)
        self.status_bar.setText(f"Running {algo_name}... (this may take a while)")

        signals = SolverSignals()
        signals.finished.connect(self._on_solve_finished)
        signals.error.connect(self._on_solve_error)

        puzzle = self.puzzle

        def worker():
            try:
                r = _run_with_timeout(SolverClass, puzzle)
                signals.finished.emit({algo_name: r})
            except Exception as e:
                signals.error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_solve_finished(self, results: dict):
        self.solving = False
        self.run_btn.setEnabled(True)

        # Merge vào result_data (nhiều lần solve nhiều algo)
        if self.result_data is None:
            self.result_data = {}
        self.result_data.update(results)

        algo_name = list(results.keys())[0]
        r         = results[algo_name]
        status    = r.get("status")

        status_map = {
            STATUS_SOLVED:     "Solved",
            STATUS_UNSOLVABLE: "Unsolvable",
            STATUS_TIMEOUT:    "Timeout",
            STATUS_STEP_LIMIT: "Step limit",
        }
        label = status_map.get(status, "Unknown")
        t     = f"{r['time_ms']:.2f} ms" if r.get("time_ms") is not None else "N/A"
        self.status_bar.setText(f"[{algo_name}] {label}  |  Time: {t}")

        # Nếu solved -> vẽ solution lên grid
        if status == STATUS_SOLVED and r.get("solution"):
            self._draw_solution(r["solution"])

        self.result_btn.setEnabled(True)

        # Lưu output
        save_output(
            input_id   = self.puzzle["id"],
            size       = self.puzzle["size"],
            solution   = r.get("solution"),
            algorithms = {algo_name: r},
        )

    def _on_solve_error(self, msg: str):
        self.solving = False
        self.run_btn.setEnabled(True)
        self.status_bar.setText(f"Error: {msg}")

    def _draw_solution(self, solution: list):
        n = self.puzzle["size"]
        for cell in self.cells:
            val = solution[cell.r][cell.c]
            cell.setText(str(val))
            cell.setProperty("status", "fill")
            cell.style().unpolish(cell)
            cell.style().polish(cell)

    # ------------------------------------------------------------------
    # Show result window
    # ------------------------------------------------------------------

    def show_result(self):
        if not self.result_data:
            QMessageBox.information(self, "No result", "Please run Solve first.")
            return

        algo_name = self.algo_box.currentText()

        # Nếu algo hiện tại chưa chạy -> lấy algo đầu tiên có kết quả
        if algo_name not in self.result_data:
            algo_name = list(self.result_data.keys())[0]

        r = self.result_data[algo_name]
        self.result_window = ResultWindow(algo_name, r, self)
        self.result_window.show()

    # ------------------------------------------------------------------
    # Show stats (gọi visualize_stats.py)
    # ------------------------------------------------------------------

    def show_stats(self):
        log_path = os.path.join(OUTPUT_DIR, "log.json")
        if not os.path.exists(log_path):
            QMessageBox.warning(self, "No log", "log.json not found.\nRun main.py first to generate stats.")
            return

        try:
            import visualize_stats
            visualize_stats.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot open stats:\n{e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)

    css_path = os.path.join(os.path.dirname(__file__), "frontend.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = App()
    window.show()
    sys.exit(app.exec_())