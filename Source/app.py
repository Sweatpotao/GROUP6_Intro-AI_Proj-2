import sys
import os
import threading

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QComboBox, QPushButton, QFrame, QScrollArea, 
    QGroupBox, QSlider, QMessageBox
)
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QObject
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
        self.setWindowTitle("Futoshiki Solver - Pro Version")
        self.resize(1100, 960)

        self.puzzles = []
        self.puzzle = None
        self.cells = []
        self.current_steps = []
        self.solving = False

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
        
        t_layout.addWidget(QLabel("Puzzle:"))
        t_layout.addWidget(self.puzzle_box)
        t_layout.addWidget(QLabel("Algo:"))
        t_layout.addWidget(self.algo_box)
        t_layout.addStretch()
        t_layout.addWidget(self.load_btn)
        t_layout.addWidget(self.run_btn)
        left_side.addWidget(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("gridScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.grid_container = QWidget()
        self.grid_container.setObjectName("gridPanel")

        from PyQt5.QtWidgets import QSizePolicy

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
        self.step_label = QLabel("Step: 0 / 0")
        self.step_slider = QSlider(Qt.Horizontal)
        self.step_slider.setEnabled(False)
        step_vbox.addWidget(self.step_label)
        step_vbox.addWidget(self.step_slider)
        step_group.setLayout(step_vbox)

        self.stats_btn = QPushButton("View Full Stats")
        self.stats_btn.setObjectName("resultBtn")

        info_layout.addWidget(QLabel("<b>STATISTICS</b>"))
        info_layout.addWidget(self.result_info, 1)
        info_layout.addWidget(step_group)
        info_layout.addWidget(self.stats_btn)
        right_side.addWidget(self.info_card)

        # Main assembly
        main_layout.addLayout(left_side, 3)
        main_layout.addLayout(right_side, 0)

        # Event connections
        self.puzzle_box.currentIndexChanged.connect(self.load_selected_puzzle)
        self.load_btn.clicked.connect(self.reload_input)
        self.run_btn.clicked.connect(self.run_solver)
        self.stats_btn.clicked.connect(self.show_stats)
        self.step_slider.valueChanged.connect(self.go_to_step)

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
        self.step_slider.setEnabled(False)
        self.step_slider.setValue(0)
        self.draw_grid()
        self.status_bar.setText(f"Loaded {self.puzzle['id']}")
        self.result_info.setText("Ready to solve.")

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
        status_txt = {STATUS_SOLVED: "Solved", STATUS_TIMEOUT: "Timeout", 
                      STATUS_UNSOLVABLE: "No Solution"}.get(r['status'], "Failed")

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
            self.step_slider.setEnabled(True)
            self.step_slider.setRange(0, len(self.current_steps))
            self.step_slider.setValue(len(self.current_steps))
        
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

    def go_to_step(self, step_idx):
        if not self.current_steps: return
        self.step_label.setText(f"Step: {step_idx} / {len(self.current_steps)}")
        
        initial_grid = self.puzzle["grid"]
        for cell in self.cells:
            if initial_grid[cell.r][cell.c] == 0:
                cell.setText("")
                cell.setProperty("status", "")
        
        for i in range(step_idx):
            r, c, val, action = self.current_steps[i]
            target_cell = next((cell for cell in self.cells if cell.r == r and cell.c == c), None)
            if target_cell:
                if action == 1:
                    target_cell.setText(str(val))
                    target_cell.setProperty("status", "fill")
                elif action == 2:
                    target_cell.setText("")
                    target_cell.setProperty("status", "remove")
        
        for cell in self.cells:
            cell.style().unpolish(cell)
            cell.style().polish(cell)

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