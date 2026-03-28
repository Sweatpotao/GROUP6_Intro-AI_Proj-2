import heapq
from abc import abstractmethod

from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class AStarBase(BaseSolver):
    """
    Class cha cho 3 A* solvers (H1, H2, H3).

    A* tìm kiếm theo công thức: f(n) = g(n) + h(n)
        g(n) = số ô đã được gán (chi phí đã đi)
        h(n) = ước lượng số bước còn lại (heuristic)
        f(n) = tổng chi phí ước tính

    Cấu trúc:
        - State = tuple 2D của grid (để hash và so sánh)
        - Open set = priority queue sắp xếp theo f(n)
        - Closed set = tập các state đã duyệt (tránh lặp)

    Mỗi subclass chỉ cần override _heuristic() với công thức khác nhau.
    Tính admissible: h(n) không bao giờ đánh giá cao hơn chi phí thực tế.
    """

    def _solve(self) -> bool:
        # Chuyển grid thành tuple để hash được
        start = self._to_state(self.grid)

        # g(start) = số ô đã được gán trong puzzle gốc
        g_start = sum(
            1 for i in range(self.n)
            for j in range(self.n)
            if self.grid[i][j] != 0
        )

        h_start = self._heuristic(self.grid)
        f_start = g_start + h_start

        # (f, counter, g, state)
        # counter tránh so sánh state khi f bằng nhau
        counter = 0
        open_set = [(f_start, counter, g_start, start)]
        closed_set = set()

        # Lưu path để reconstruct steps
        # parent[state] = (prev_state, row, col, val)
        parent = {start: None}

        while open_set:
            f, _, g, state = heapq.heappop(open_set)
            self.inferences += 1

            if state in closed_set:
                continue
            closed_set.add(state)

            grid = self._to_grid(state)

            # Kiểm tra đã giải xong chưa
            if self._is_complete(grid):
                self._reconstruct(state, parent)
                return True

            # Tìm ô trống tiếp theo để gán
            cell = self._next_empty_from(grid)
            if cell is None:
                continue

            row, col = cell

            for val in range(1, self.n + 1):
                # Tạm gán để kiểm tra
                grid[row][col] = val
                if self._is_valid_cell(grid, row, col, val):
                    new_state = self._to_state(grid)

                    if new_state not in closed_set:
                        new_g = g + 1
                        new_h = self._heuristic(grid)
                        new_f = new_g + new_h

                        counter += 1
                        heapq.heappush(open_set, (new_f, counter, new_g, new_state))

                        if new_state not in parent:
                            parent[new_state] = (state, row, col, val)

                grid[row][col] = 0  # hoàn tác

        return False

    # ------------------------------------------------------------------
    # Heuristic - mỗi subclass override hàm này
    # ------------------------------------------------------------------

    @abstractmethod
    def _heuristic(self, grid: list) -> int:
        """
        Ước lượng số bước còn lại từ trạng thái grid hiện tại.
        Phải admissible: không được đánh giá cao hơn chi phí thực.
        """
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_state(self, grid: list) -> tuple:
        # Chuyển grid list[list] -> tuple of tuples (hashable)
        return tuple(tuple(row) for row in grid)

    def _to_grid(self, state: tuple) -> list:
        # Chuyển state tuple -> grid list[list] (mutable)
        return [list(row) for row in state]

    def _is_complete(self, grid: list) -> bool:
        # Kiểm tra grid đã điền đầy chưa
        return all(grid[i][j] != 0 for i in range(self.n) for j in range(self.n))

    def _next_empty_from(self, grid: list):
        # Trả về ô trống đầu tiên trong grid
        for i in range(self.n):
            for j in range(self.n):
                if grid[i][j] == 0:
                    return (i, j)
        return None

    def _is_valid_cell(self, grid: list, row: int, col: int, val: int) -> bool:
        """Kiểm tra val có hợp lệ tại (row,col) trong grid hiện tại."""
        # Kiểm tra hàng
        for j in range(self.n):
            if j != col and grid[row][j] == val:
                return False

        # Kiểm tra cột
        for i in range(self.n):
            if i != row and grid[i][col] == val:
                return False

        # Kiểm tra inequality constraints
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        if col > 0 and grid[row][col - 1] != 0:
            c = hc[row][col - 1]
            if c == 1 and not (grid[row][col - 1] < val):
                return False
            if c == -1 and not (grid[row][col - 1] > val):
                return False

        if col < self.n - 1 and grid[row][col + 1] != 0:
            c = hc[row][col]
            if c == 1 and not (val < grid[row][col + 1]):
                return False
            if c == -1 and not (val > grid[row][col + 1]):
                return False

        if row > 0 and grid[row - 1][col] != 0:
            c = vc[row - 1][col]
            if c == 1 and not (grid[row - 1][col] < val):
                return False
            if c == -1 and not (grid[row - 1][col] > val):
                return False

        if row < self.n - 1 and grid[row + 1][col] != 0:
            c = vc[row][col]
            if c == 1 and not (val < grid[row + 1][col]):
                return False
            if c == -1 and not (val > grid[row + 1][col]):
                return False

        return True

    def _reconstruct(self, final_state: tuple, parent: dict):
        """
        Truy ngược từ final_state về start để ghi steps[] và cập nhật self.grid.
        """
        path = []
        state = final_state

        while parent[state] is not None:
            prev_state, row, col, val = parent[state]
            path.append((row, col, val))
            state = prev_state

        # Ghi steps theo thứ tự xuôi
        for row, col, val in reversed(path):
            self.record_step(row, col, val, ACTION_ASSIGN)

        # Cập nhật self.grid
        final_grid = self._to_grid(final_state)
        for i in range(self.n):
            for j in range(self.n):
                self.grid[i][j] = final_grid[i][j]