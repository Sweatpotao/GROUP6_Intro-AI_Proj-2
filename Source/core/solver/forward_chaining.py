from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class ForwardChainingSolver(BaseSolver):
    """
    Forward Chaining solver

    Cách hoạt động:
        1. Khởi tạo domain[i][j] = tập giá trị còn có thể của ô (i,j).
        2. Áp dụng các số đã cho sẵn -> thu hẹp domain.
        3. Lan truyền ràng buộc (propagate):
           - Nếu ô (i,j) chỉ còn 1 giá trị khả thi -> gán ngay giá trị đó.
           - Xóa giá trị đó khỏi danh sách khả thi của các ô cùng hàng, cùng cột.
           - Áp dụng các ràng buộc bất đẳng thức để xóa các giá trị vi phạm.
        4. Lặp lại bước 3 cho đến khi trạng thái ổn định (không còn thay đổi mới).
        5. Nếu vẫn còn ô chưa được gán -> dùng backtracking để giải quyết trên các domain đã thu hẹp.

    So sánh với Backtracking:
        Backtracking: Thử từng giá trị, kiểm tra sai phạm sau.
        Forward chaining: Suy diễn trước, cắt giảm domain trước, sau đó mới thử.
        -> Forward chaining có ít lượt suy diễn (inferences) hơn trong phần lớn trường hợp.
    """

    def _solve(self) -> bool:
        # Domain[i][j] = set các giá trị còn có thể của ô (i,j)
        domains = self._init_domains()

        # Lan truyền ràng buộc (Propagate) từ given clues
        ok = self._propagate(domains)
        if not ok:
            return False

        # Giải quyết các ô còn lại bằng backtracking trên domain đã thu hẹp
        return self._search(domains)

    # ------------------------------------------------------------------
    # Domain initialization
    def _init_domains(self) -> list:
        domains = []
        for i in range(self.n):
            row = []
            for j in range(self.n):
                v = self.grid[i][j]
                if v != 0:
                    row.append({v})
                else:
                    row.append(set(range(1, self.n + 1)))
            domains.append(row)
        return domains

    # ------------------------------------------------------------------
    # Propagation - Lan truyền (forward chaining)
    def _propagate(self, domains: list) -> bool:
        # Lan truyền ràng buộc liên tục cho đến khi ổn định.
        # Trả về False nếu phát hiện mâu thuẫn (domain rỗng).
        changed = True
        while changed:
            changed = False
            self.inferences += 1

            for i in range(self.n):
                for j in range(self.n):
                    # Không còn valid value -> Mâu thuẫn
                    if len(domains[i][j]) == 0:
                        return False

                    # Nếu ô chỉ còn 1 giá trị khả thi -> Lan truyền
                    if len(domains[i][j]) == 1:
                        val = next(iter(domains[i][j]))

                        # Xóa val khỏi cung hàng
                        for jj in range(self.n):
                            if jj != j and val in domains[i][jj]:
                                domains[i][jj].discard(val)
                                changed = True
                                if len(domains[i][jj]) == 0:
                                    return False

                        # Xóa val khỏi cung cột
                        for ii in range(self.n):
                            if ii != i and val in domains[ii][j]:
                                domains[ii][j].discard(val)
                                changed = True
                                if len(domains[ii][j]) == 0:
                                    return False

                        # Áp dụng inequality constraints
                        ok, was_changed = self._propagate_inequalities(domains, i, j, val)
                        if not ok:
                            return False
                        if was_changed:
                            changed = True

        return True

    # ------------------------------------------------------------------
    # Lan truyền bất đẳng thức (>, <)
    def _propagate_inequalities(self, domains, row, col, val) -> tuple:
        # Dựa vào val vừa biết ở (row,col)
        # suy diễn và loại bỏ các giá trị không hợp lệ ở các ô kế cận
        # Trả về (ok, changed)

        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]
        changed = False

        # Ràng buộc ngang: (row, col) & (row, col+1)
        if col < self.n - 1:
            c = hc[row][col]
            if c == 1:      # val < neighbor_right
                to_remove = {v for v in domains[row][col + 1] if v <= val}
                if to_remove:
                    domains[row][col + 1] -= to_remove
                    changed = True
                    if len(domains[row][col + 1]) == 0:
                        return False, changed
            elif c == -1:   # val > neighbor_right
                to_remove = {v for v in domains[row][col + 1] if v >= val}
                if to_remove:
                    domains[row][col + 1] -= to_remove
                    changed = True
                    if len(domains[row][col + 1]) == 0:
                        return False, changed

        # Ràng buộc ngang: (row, col-1) & (row, col)
        if col > 0:
            c = hc[row][col - 1]
            if c == 1:      # neighbor_left < val
                to_remove = {v for v in domains[row][col - 1] if v >= val}
                if to_remove:
                    domains[row][col - 1] -= to_remove
                    changed = True
                    if len(domains[row][col - 1]) == 0:
                        return False, changed
            elif c == -1:   # neighbor_left > val
                to_remove = {v for v in domains[row][col - 1] if v <= val}
                if to_remove:
                    domains[row][col - 1] -= to_remove
                    changed = True
                    if len(domains[row][col - 1]) == 0:
                        return False, changed

        # Ràng buộc dọc: (row, col) & (row+1, col)
        if row < self.n - 1:
            c = vc[row][col]
            if c == 1:      # val < neighbor_below
                to_remove = {v for v in domains[row + 1][col] if v <= val}
                if to_remove:
                    domains[row + 1][col] -= to_remove
                    changed = True
                    if len(domains[row + 1][col]) == 0:
                        return False, changed
            elif c == -1:   # val > neighbor_below
                to_remove = {v for v in domains[row + 1][col] if v >= val}
                if to_remove:
                    domains[row + 1][col] -= to_remove
                    changed = True
                    if len(domains[row + 1][col]) == 0:
                        return False, changed

        # Ràng buộc dọc: (row-1, col) & (row, col)
        if row > 0:
            c = vc[row - 1][col]
            if c == 1:      # neighbor_above < val
                to_remove = {v for v in domains[row - 1][col] if v >= val}
                if to_remove:
                    domains[row - 1][col] -= to_remove
                    changed = True
                    if len(domains[row - 1][col]) == 0:
                        return False, changed
            elif c == -1:   # neighbor_above > val
                to_remove = {v for v in domains[row - 1][col] if v <= val}
                if to_remove:
                    domains[row - 1][col] -= to_remove
                    changed = True
                    if len(domains[row - 1][col]) == 0:
                        return False, changed

        return True, changed

    # ------------------------------------------------------------------
    # Search - Dùng khi suy luận chưa đủ để giải quyết toàn bộ
    def _search(self, domains: list) -> bool:
        # Tìm ô chưa được gán có domain nhỏ nhất (MRV heuristic), thử từng giá trị, lan truyền tiếp, rồi đệ quy.
        target = None
        min_size = self.n + 1
        for i in range(self.n):
            for j in range(self.n):
                size = len(domains[i][j])
                if size > 1 and size < min_size:
                    min_size = size
                    target = (i, j)

        # Tất cả ô đã được gán -> ghi vào grid & kết thúc
        if target is None:
            self._apply_domains(domains)
            return True

        row, col = target

        # Thử từng giá trị khả thi trong domain của ô đó
        for val in sorted(domains[row][col]):
            self.inferences += 1

            # Copy domains để thử val
            new_domains = [[set(cell) for cell in row_d] for row_d in domains]
            new_domains[row][col] = {val}

            ok = self._propagate(new_domains)
            if ok:
                self.record_step(row, col, val, ACTION_ASSIGN)
                if self._search(new_domains):
                    return True
                self.record_step(row, col, 0, ACTION_BACKTRACK)

        return False

    # ------------------------------------------------------------------
    # Ghi kết quả cuối từ domains vào main grid
    def _apply_domains(self, domains: list):
        for i in range(self.n):
            for j in range(self.n):
                val = next(iter(domains[i][j]))
                if self.grid[i][j] == 0:
                    self.grid[i][j] = val
                    self.record_step(i, j, val, ACTION_ASSIGN)