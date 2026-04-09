from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver

class BackwardChainingSolver(BaseSolver):
    """
    Backward Chaining solver sử dụng SLD Resolution (Prolog style).
    Mỗi giá trị val được xem như một clause: Val(i,j,val) :- body.
    """

    def _solve(self) -> bool:
        # Khởi tạo KB với các given clues
        self.kb = {}
        for i in range(self.n):
            for j in range(self.n):
                if self.grid[i][j] != 0:
                    self.kb[(i, j)] = self.grid[i][j]

        # Xây dựng các Horn clause: với mỗi val, head = (None, None, val), body = các hàm kiểm tra
        self.clauses = []
        for val in range(1, self.n + 1):
            self.clauses.append({
                "head": (None, None, val),  # row, col là biến (wildcard), val là hằng
                "body": [
                    self._prove_not_in_row,
                    self._prove_not_in_col,
                    self._prove_inequalities
                ]
            })

        # Danh sách các ô cần chứng minh
        goals = [
            (i, j)
            for i in range(self.n)
            for j in range(self.n)
            if self.grid[i][j] == 0
        ]
        return self._sld_resolve(goals, 0)

    # ------------------------------------------------------------------
    # Unification (đơn giản vì head có val là hằng)
    # ------------------------------------------------------------------
    def _unify(self, goal, clause_head):
        """
        Unify goal (row, col, None) với head (None, None, val).
        Trả về val nếu thành công, ngược lại None.
        """
        _, _, val_h = clause_head
        return val_h

    # ------------------------------------------------------------------
    # SLD Resolution engine
    # ------------------------------------------------------------------
    def _sld_resolve(self, goals, idx):
        if idx == len(goals):
            return True

        row, col = goals[idx]

        # Nếu đã có trong KB -> bỏ qua
        if (row, col) in self.kb:
            return self._sld_resolve(goals, idx + 1)

        # Duyệt các clause
        for clause in self.clauses:
            val = self._unify((row, col, None), clause["head"])
            if val is None:
                continue

            if self.should_stop():
                return False

            # Kiểm tra lần lượt các điều kiện trong body
            ok = True
            for body_func in clause["body"]:
                if not body_func(row, col, val):
                    ok = False
                    break

            if not ok:
                continue

            # Gán giá trị
            self.kb[(row, col)] = val
            self.grid[row][col] = val
            self.record_step(row, col, val, ACTION_ASSIGN)

            if self._sld_resolve(goals, idx + 1):
                return True

            # Backtrack
            del self.kb[(row, col)]
            self.grid[row][col] = 0
            self.record_step(row, col, 0, ACTION_BACKTRACK)

        return False

    # ------------------------------------------------------------------
    # Body predicates (các điều kiện cần chứng minh)
    # ------------------------------------------------------------------
    def _prove_not_in_row(self, row, col, val):
        self.inferences += 1
        for j in range(self.n):
            if j != col and self.kb.get((row, j)) == val:
                return False
        return True

    def _prove_not_in_col(self, row, col, val):
        self.inferences += 1
        for i in range(self.n):
            if i != row and self.kb.get((i, col)) == val:
                return False
        return True

    def _prove_inequalities(self, row, col, val):
        self.inferences += 1
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        if col > 0 and (row, col-1) in self.kb:
            left = self.kb[(row, col-1)]
            c = hc[row][col-1]
            if c == 1 and not (left < val):
                return False
            if c == -1 and not (left > val):
                return False

        if col < self.n-1 and (row, col+1) in self.kb:
            right = self.kb[(row, col+1)]
            c = hc[row][col]
            if c == 1 and not (val < right):
                return False
            if c == -1 and not (val > right):
                return False

        if row > 0 and (row-1, col) in self.kb:
            above = self.kb[(row-1, col)]
            c = vc[row-1][col]
            if c == 1 and not (above < val):
                return False
            if c == -1 and not (above > val):
                return False

        if row < self.n-1 and (row+1, col) in self.kb:
            below = self.kb[(row+1, col)]
            c = vc[row][col]
            if c == 1 and not (val < below):
                return False
            if c == -1 and not (val > below):
                return False

        return True