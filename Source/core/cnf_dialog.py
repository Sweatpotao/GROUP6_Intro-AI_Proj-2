"""
CNF Knowledge Base Dialog.
Tách biệt khỏi app.py để giữ app.py gọn.
"""

import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QGridLayout, QGroupBox
)
from PyQt5.QtCore import Qt

from core.cnf_generator import generate_kb, kb_summary, verify_solution

def _verify_status(puzzle, current_grid, n):
    """Trả về (icon, color, bg, text) tương ứng với trạng thái verify."""
    is_complete = all(
        current_grid[i][j] != 0
        for i in range(n) for j in range(n)
    )
    if not is_complete:
        return "⚠️", "#e67e22", "#fff8e1", "Skipped — puzzle not fully solved yet."
    if verify_solution(puzzle, current_grid):
        return "✅", "#27ae60", "#eafaf1", "PASSED — solution satisfies all axioms."
    return "❌", "#e74c3c", "#fdf2f2", "FAILED — logic violation detected."


def parse_summary(summary_text):
    """Bóc tách dữ liệu từ file text gốc để render UI Native"""
    var_match = re.search(r"Total variables\s*:\s*(\d+)", summary_text)
    clause_match = re.search(r"Total clauses\s*:\s*(\d+)", summary_text)
    # Tìm tất cả các axiom dạng "A1: 81 clauses"
    axioms = re.findall(r"(A\d+)[^:]*:\s*(\d+)\s*clause", summary_text, re.IGNORECASE)

    return {
        "vars": var_match.group(1) if var_match else "N/A",
        "clauses": clause_match.group(1) if clause_match else "N/A",
        "axioms": axioms
    }


class CNFDialog(QDialog):
    def __init__(self, parent, puzzle, cells):
        super().__init__(parent)
        self.puzzle = puzzle
        self.cells = cells
        self.n = puzzle["size"]

        self.setWindowTitle("CNF Knowledge Base")
        self.setMinimumWidth(480)
        
        # --- QUAN TRỌNG: KHÔNG CHẶN TƯƠNG TÁC UI CHÍNH ---
        self.setModal(False)
        # Cho phép dialog tự hủy khi đóng để dọn bộ nhớ
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._init_data()
        self._build_ui()

    def _init_data(self):
        # Lấy grid hiện tại từ cells
        cell_map = {(c.r, c.c): c for c in self.cells}
        self.current_grid = [
            [
                int(cell.text()) if (cell := cell_map.get((i, j))) and cell.text().isdigit() else 0
                for j in range(self.n)
            ]
            for i in range(self.n)
        ]

        # Sinh KB và verify
        kb = generate_kb(self.puzzle)
        self.raw_summary = kb_summary(kb)
        self.parsed_data = parse_summary(self.raw_summary)
        
        self.v_icon, self.v_color, self.v_bg, self.v_text = _verify_status(self.puzzle, self.current_grid, self.n)

    def _build_ui(self):
        # Setup font family chuẩn cho toàn bộ Dialog
        self.setStyleSheet("QDialog { background-color: #ffffff; } * { font-family: 'Segoe UI', sans-serif; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. Title
        title = QLabel("📦 Knowledge Base Summary")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(title)

        # 2. Hai Thẻ Thống Kê (Variables & Clauses)
        stats_layout = QHBoxLayout()

        # Card Variables
        var_frame = QFrame()
        var_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 8px; border: 1px solid #e1e8ed;")
        var_layout = QVBoxLayout(var_frame)
        var_title = QLabel("Total Variables")
        var_title.setStyleSheet("color: #7f8c8d; font-size: 13px; font-weight: 600;")
        var_val = QLabel(self.parsed_data["vars"])
        var_val.setStyleSheet("color: #2980b9; font-size: 24px; font-weight: bold;")
        var_layout.addWidget(var_title)
        var_layout.addWidget(var_val)

        # Card Clauses
        clause_frame = QFrame()
        clause_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 8px; border: 1px solid #e1e8ed;")
        clause_layout = QVBoxLayout(clause_frame)
        clause_title = QLabel("Total Clauses")
        clause_title.setStyleSheet("color: #7f8c8d; font-size: 13px; font-weight: 600;")
        clause_val = QLabel(self.parsed_data["clauses"])
        clause_val.setStyleSheet("color: #e67e22; font-size: 24px; font-weight: bold;")
        clause_layout.addWidget(clause_title)
        clause_layout.addWidget(clause_val)

        stats_layout.addWidget(var_frame)
        stats_layout.addWidget(clause_frame)
        layout.addLayout(stats_layout)

        # 3. Phân rã Axioms (Breakdown)
        if self.parsed_data["axioms"]:
            group_box = QGroupBox("Breakdown by Axiom")
            group_box.setStyleSheet("""
                QGroupBox {
                    font-size: 14px;
                    font-weight: bold;
                    color: #2c3e50;
                    border: 1px solid #dcdde1;
                    border-radius: 8px;
                    margin-top: 15px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
            grid_layout = QGridLayout(group_box)
            grid_layout.setContentsMargins(15, 20, 15, 15)
            grid_layout.setSpacing(10)

            # Sắp xếp hiển thị theo 2 cột cho tiết kiệm không gian
            for idx, (ax, count) in enumerate(self.parsed_data["axioms"]):
                row = idx // 2
                col = idx % 2
                lbl = QLabel(f"<b>{ax}:</b> {count} clauses")
                lbl.setStyleSheet("font-size: 14px; color: #34495e; font-weight: normal;")
                grid_layout.addWidget(lbl, row, col)

            layout.addWidget(group_box)
        else:
            # Fallback nếu parse lỗi (giữ nguyên string log)
            raw_lbl = QLabel(self.raw_summary)
            raw_lbl.setStyleSheet("font-family: Consolas; font-size: 13px; color: #34495e;")
            layout.addWidget(raw_lbl)

        # 4. Box Trạng thái (Verification Status)
        verify_frame = QFrame()
        verify_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.v_bg};
                border-left: 5px solid {self.v_color};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        v_layout = QVBoxLayout(verify_frame)
        v_lbl = QLabel(f"{self.v_icon} CNF Verification: {self.v_text}")
        v_lbl.setStyleSheet(f"color: {self.v_color}; font-weight: bold; font-size: 14px;")
        v_layout.addWidget(v_lbl)
        layout.addWidget(verify_frame)

        # 5. Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("OK")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; 
                color: white;
                border-radius: 6px; 
                padding: 8px 16px; 
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)


# ---------------------------------------------------------------------------
# Public entry point — gọi từ app.py
# ---------------------------------------------------------------------------

def show_cnf_dialog(parent, puzzle, cells):
    """
    Hiển thị CNF Knowledge Base dialog không chặn UI chính.
    """
    # Xử lý đóng/mở lại nếu user bấm nút nhiều lần
    if hasattr(parent, 'cnf_dlg') and parent.cnf_dlg is not None:
        try:
            if parent.cnf_dlg.isVisible():
                parent.cnf_dlg.close() # Đóng cái cũ đi
        except RuntimeError:
            pass # Object đã bị C++ dọn dẹp

    # Khởi tạo và LƯU dialog vào biến của `parent` (tránh bị Garbage Collector của Python xóa ngay lập tức)
    parent.cnf_dlg = CNFDialog(parent, puzzle, cells)
    parent.cnf_dlg.show() # Dùng show() thay vì exec_() để UI chính vẫn hoạt động