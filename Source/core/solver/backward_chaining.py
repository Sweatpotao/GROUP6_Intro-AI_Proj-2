from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class BackwardChainingSolver(BaseSolver):
    """
    Backward Chaining solver cho Futoshiki (SLD Resolution - Prolog style)

    Cách hoạt động:
        1. Goal ban đầu: Val(i,j,?) cho mỗi ô trống
        2. Với mỗi goal Val(i,j,?), tìm gia trị v sao cho:
           - v không xuất hiện trong cùng hàng/cột (uniqueness)
           - v thỏa mãn tất cả inequality constraints liên quan
           - Gán v vào ô -> sinh ra sub-goals cho các ô còn lại
        3. Nếu tất cả sub-goals được thỏa -> bài toán có lời giải
        4. Nếu không có v nào thỏa -> backtrack lên goal cha

    So sánh với Forward Chaining:
        Forward : suy từ facts -> goals (bottom-up)
        Backward: suy từ goals -> facts (top-down, Prolog style)
    """

    def _solve(self) -> bool:
        # Thu thập tất cả ô trống -> đây là danh sách goals cần chứng minh
        goals = [
            (i, j)
            for i in range(self.n)
            for j in range(self.n)
            if self.grid[i][j] == 0
        ]
        return self._resolve(goals, 0)

    # ------------------------------------------------------------------
    # SLD Resolution
    def _resolve(self, goals: list, idx: int) -> bool:
        # Giải quyết goal thứ idx trong danh sách goals.
        # Mỗi goal là Val(row, col, ?) - cần tìm giá trị phù hợp.
        # Tất cả goals đã được resolve -> thành công
        if idx == len(goals):
            return True

        row, col = goals[idx]

        # Ô này đã được gán (do ô khác ảnh hưởng) -> bỏ qua, resolve goal tiếp
        if self.grid[row][col] != 0:
            return self._resolve(goals, idx + 1)

        # Thử từng giá trị có thể - đây là bước "unification" trong SLD
        for val in range(1, self.n + 1):
            self.inferences += 1

            if self.is_valid(row, col, val):
                # Unify: gán val cho goal này
                self.grid[row][col] = val
                self.record_step(row, col, val, ACTION_ASSIGN)

                # Resolve các sub-goals còn lại
                if self._resolve(goals, idx + 1):
                    return True

                # Unification thất bại -> backtrack, thử val khác
                self.grid[row][col] = 0
                self.record_step(row, col, 0, ACTION_BACKTRACK)

        # Không có val nào thỏa mãn goal này -> fail, báo cho goal cha backtrack
        return False