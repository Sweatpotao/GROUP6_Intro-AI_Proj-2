from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class BacktrackingSolver(BaseSolver):
    """
    Backtracking solver - có pruning

    Khác biệt với brute force:
    - Check constraint NGAY KHI gán giá trị (không đợi điền xong)
    - Cắt nhánh sớm (pruning) nếu phát hiện mâu thuẫn
    - Số inferences ít hơn brute force rất nhiều
    """

    def _solve(self) -> bool:
        return self._backtrack()

    def _backtrack(self) -> bool:
        cell = self.next_empty()

        # Không còn ô trống -> đã giải xong
        if cell is None:
            return True

        row, col = cell

        for val in range(1, self.n + 1):
            if self.is_valid(row, col, val):
                # Gán giá trị và ghi bước
                self.grid[row][col] = val
                self.record_step(row, col, val, ACTION_ASSIGN)

                if self._backtrack():
                    return True

                # Gán sai -> xóa và thử giá trị khác (backtrack)
                self.grid[row][col] = 0
                self.record_step(row, col, 0, ACTION_BACKTRACK)

        return False