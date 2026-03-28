from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class BruteForceSolver(BaseSolver):
    """
    Brute force solver - không pruning.

    Cách hoạt động:
    - Thử tất cả tổ hợp có thể (1..N cho mỗi ô trống)
    - Chỉ check constraint SAU KHI điền xong toàn bộ grid
    - Chậm nhất trong tất cả solver, dùng làm baseline so sánh
    """

    def __init__(self, puzzle: dict):
        super().__init__(puzzle)
        # Lấy danh sách ô trống một lần khi khởi tạo
        self._empty_cells = [
            (i, j)
            for i in range(self.n)
            for j in range(self.n)
            if puzzle["grid"][i][j] == 0
        ]

    def _solve(self) -> bool:
        # Reset lại empty cells sau mỗi lần solve() (vì solve() reset grid)
        self._empty_cells = [
            (i, j)
            for i in range(self.n)
            for j in range(self.n)
            if self.grid[i][j] == 0
        ]
        return self._brute(0)

    def _brute(self, idx: int) -> bool:
        # Đã điền xong tất cả ô trống -> check toàn bộ constraints
        if idx == len(self._empty_cells):
            return self.check_all_constraints()

        row, col = self._empty_cells[idx]

        for val in range(1, self.n + 1):
            self.grid[row][col] = val
            self.record_step(row, col, val, ACTION_ASSIGN)

            if self._brute(idx + 1):
                return True

            self.grid[row][col] = 0
            self.record_step(row, col, 0, ACTION_BACKTRACK)

        return False