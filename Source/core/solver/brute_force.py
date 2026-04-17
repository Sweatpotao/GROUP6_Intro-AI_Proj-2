from itertools import permutations
from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class BruteForceSolver(BaseSolver):
    """
    Thuật toán Brute Force

    Cách hoạt động:
    - GENERATE: Sinh tất cả hoán vị có thể của [1..N] cho từng hàng.
    - TEST: Chỉ kiểm tra toàn bộ ràng buộc MỘT LẦN DUY NHẤT khi đã điền kín toàn bộ bảng.

    Độ phức tạp: O((N!)^N) — chỉ dùng để minh họa / so sánh baseline; không dùng cho UI, vì bị treo máy khi chạy.
    """

    def _solve(self) -> bool:
        # Xác định hàng nào cần sinh (có ô trống), hàng nào đã fixed (toàn GIVEN)
        free_rows  = []   # index hàng cần sinh hoán vị
        fixed_rows = {}   # index hàng → list giá trị cố định (dự phòng)

        for i in range(self.n):
            row = self.puzzle["grid"][i]
            if 0 in row:
                free_rows.append(i)
            else:
                fixed_rows[i] = row[:]

        return self._generate(free_rows, 0)

    def _generate(self, free_rows: list, idx: int) -> bool:
        """
        Sinh hoán vị cho hàng free_rows[idx].
        Khi đã sinh xong tất cả hàng → TEST một lần duy nhất.
        """
        if self.should_stop():
            return False

        # Đã sinh xong tất cả hàng cần sinh → TEST
        if idx == len(free_rows):
            return self.check_all_constraints()

        row = free_rows[idx]

        # Lấy các ô đã GIVEN trong hàng này
        given_in_row = {
            col: self.puzzle["grid"][row][col]
            for col in range(self.n)
            if self.puzzle["grid"][row][col] != 0
        }

        # Các giá trị còn cần điền (loại bỏ GIVEN đã có trong hàng)
        given_vals = set(given_in_row.values())
        free_cols  = [c for c in range(self.n) if c not in given_in_row]
        need_vals  = [v for v in range(1, self.n + 1) if v not in given_vals]

        # GENERATE: Thử tất cả hoán vị của need_vals vào free_cols (mù quáng)
        for perm in permutations(need_vals):
            if self.should_stop():
                return False

            # Điền hoán vị vào hàng — không check bất kỳ constraint nào
            for k, col in enumerate(free_cols):
                self.grid[row][col] = perm[k]
                self.record_step(row, col, perm[k], ACTION_ASSIGN)

            # Đệ quy sang hàng tiếp theo
            if self._generate(free_rows, idx + 1):
                return True

            # Hoàn tác để thử hoán vị tiếp theo
            for col in free_cols:
                self.grid[row][col] = 0
                self.record_step(row, col, 0, ACTION_BACKTRACK)

        return False