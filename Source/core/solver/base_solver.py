import time
import tracemalloc
from abc import ABC, abstractmethod

from core.config import MAX_STEPS, ACTION_GIVEN, ACTION_ASSIGN, ACTION_BACKTRACK, STATUS_SOLVED, STATUS_UNSOLVABLE, STATUS_STEP_LIMIT

# Thằng cha
class BaseSolver(ABC):
    def __init__(self, puzzle: dict):
        self.puzzle     = puzzle
        self.n          = puzzle["size"]

        # Grid làm việc - copy để không mutate puzzle gốc
        self.grid       = [row[:] for row in puzzle["grid"]]

        # Thống kê
        self.steps      = []       # compact array: [row, col, val, action_code]
        self.inferences = 0        # số lần suy diễn / kiểm tra

    # Interface bắt buộc - mỗi solver con phải implement
    @abstractmethod
    def _solve(self) -> bool:
        # Logic giải bài toán. Trả về status: UNSOLVABLE, SOLVED, TIMEOUT, STEP_LIMIT
        # Solver con dùng self.grid để làm việc, gọi self.record_step() để ghi lại.
        pass

    # Entry point - gọi từ bên ngoài
    def solve(self) -> dict:
        self.grid       = [row[:] for row in self.puzzle["grid"]]
        self.steps      = []
        self.inferences = 0

        # Ghi các ô given trước khi chạy thuật toán
        self._record_givens()

        # Đo bộ nhớ & thời gian
        tracemalloc.start()
        t0 = time.perf_counter()

        solved = self._solve()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Xác định status
        if solved:
            status = STATUS_SOLVED
        elif len(self.steps) >= MAX_STEPS:
            status = STATUS_STEP_LIMIT
        else:
            status = STATUS_UNSOLVABLE

        return {
            "status":       status,
            "solution":     [row[:] for row in self.grid] if solved else None,
            "time_ms":      round(elapsed_ms, 3),
            "memory_kb":    round(peak / 1024, 2),
            "inferences":   self.inferences,
            "steps":        self.steps,  # đã được cap tại MAX_STEPS trong record_step()
        }

    def record_step(self, row: int, col: int, val: int, action: int):
        # Ghi 1 bước vào steps[] nếu chưa đạt MAX_STEPS
        # action: ACTION_GIVEN / ACTION_ASSIGN / ACTION_BACKTRACK
        if len(self.steps) < MAX_STEPS:
            self.steps.append([row, col, val, action])

    def is_valid(self, row: int, col: int, val: int) -> bool:
        # Kiểm tra val có hợp lệ tại (row, col) không
        # Tính cả uniqueness (hàng/cột) lẫn inequality constraints
    
        self.inferences += 1

        # Kiểm tra hàng: val chưa xuất hiện ở hàng này
        for j in range(self.n):
            if j != col and self.grid[row][j] == val:
                return False

        # Kiểm tra cột: val chưa xuất hiện ở cột này
        for i in range(self.n):
            if i != row and self.grid[i][col] == val:
                return False

        # Kiểm tra inequality constraints liên quan đến ô (row, col)
        return self._check_inequalities(row, col, val)

    def _check_inequalities(self, row: int, col: int, val: int) -> bool:
        # Kiểm tra tất cả ràng buộc liên quan đến tọa độ (row, col)
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]
        g  = self.grid

        # Ràng buộc ngang: ô bên TRÁI so với (row, col)
        if col > 0 and g[row][col - 1] != 0:
            c = hc[row][col - 1]
            if c == 1 and not (g[row][col - 1] < val):   # trái < phải
                return False
            if c == -1 and not (g[row][col - 1] > val):  # trái > phải
                return False

        # Ràng buộc ngang: ô bên PHẢI so với (row, col)
        if col < self.n - 1 and g[row][col + 1] != 0:
            c = hc[row][col]
            if c == 1 and not (val < g[row][col + 1]):   # trái < phải
                return False
            if c == -1 and not (val > g[row][col + 1]):  # trái > phải
                return False

        # Ràng buộc dọc: ô PHÍA TRÊN so với (row, col)
        if row > 0 and g[row - 1][col] != 0:
            c = vc[row - 1][col]
            if c == 1 and not (g[row - 1][col] < val):   # trên < dưới
                return False
            if c == -1 and not (g[row - 1][col] > val):  # trên > dưới
                return False

        # Ràng buộc dọc: ô PHÍA DƯỚI so với (row, col)
        if row < self.n - 1 and g[row + 1][col] != 0:
            c = vc[row][col]
            if c == 1 and not (val < g[row + 1][col]):   # trên < dưới
                return False
            if c == -1 and not (val > g[row + 1][col]):  # trên > dưới
                return False

        return True

    def next_empty(self):
        # Trả về (row, col) của ô trống đầu tiên, hoặc None nếu đã điền xong
        for i in range(self.n):
            for j in range(self.n):
                if self.grid[i][j] == 0:
                    return (i, j)
        return None

    def check_all_constraints(self) -> bool:
        # Kiểm tra toàn bộ constraints trên grid đã điền đầy đủ
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]
        self.inferences += 1

        # Uniqueness hàng và cột
        for i in range(self.n):
            if len(set(self.grid[i])) != self.n:
                return False
            if len(set(self.grid[r][i] for r in range(self.n))) != self.n:
                return False

        # Horizontal inequality
        for i in range(self.n):
            for j in range(self.n - 1):
                c = hc[i][j]
                if c == 1 and not (self.grid[i][j] < self.grid[i][j + 1]):
                    return False
                if c == -1 and not (self.grid[i][j] > self.grid[i][j + 1]):
                    return False

        # Vertical inequality
        for i in range(self.n - 1):
            for j in range(self.n):
                c = vc[i][j]
                if c == 1 and not (self.grid[i][j] < self.grid[i + 1][j]):
                    return False
                if c == -1 and not (self.grid[i][j] > self.grid[i + 1][j]):
                    return False

        return True

    def _record_givens(self):
        # Ghi tất cả ô given vào steps[] trước khi chạy thuật toán
        for i in range(self.n):
            for j in range(self.n):
                if self.grid[i][j] != 0:
                    self.record_step(i, j, self.grid[i][j], ACTION_GIVEN)