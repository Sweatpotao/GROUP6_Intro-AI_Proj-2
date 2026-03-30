from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class BackwardChainingSolver(BaseSolver):
    """
    Backward Chaining solver (SLD Resolution - Prolog style).

    Khác với backtracking đơn thuần, backward chaining thực sự:

    1. Horn Clauses - các luật dưới dạng: HEAD :- BODY
       - Val(i,j,v) :- not_in_row(i,j,v), not_in_col(i,j,v), satisfies_ineq(i,j,v)
       - not_in_row(i,j,v) :- forall j' != j: Val(i,j',v) = False
       - satisfies_ineq :- kiểm tra tất cả inequality liên quan

    2. Unification - khớp goal với head của clause:
       - Goal: Val(i,j,?) → unify với Val(i,j,v) cho từng v
       - Sinh sub-goals từ body của clause

    3. SLD Resolution - chọn goal leftmost, resolve với clause phù hợp:
       - Goal list: [Val(0,0,?), Val(0,1,?), ..., Val(n-1,n-1,?)]
       - Resolve từng goal, sinh sub-goals mới nếu cần

    Điểm khác biệt với backtracking:
        Backtracking: thử val → check constraint → backtrack nếu sai
        Backward chaining: query goal → unify → prove sub-goals → succeed/fail
    """

    def _solve(self) -> bool:
        # KB (Knowledge Base): facts đã biết
        # Val(i,j,v) = True nếu ô (i,j) đã được gán giá trị v
        self.kb = {}
        for i in range(self.n):
            for j in range(self.n):
                if self.grid[i][j] != 0:
                    self.kb[(i, j)] = self.grid[i][j]

        # Goal list ban đầu: prove Val(i,j,?) cho mỗi ô trống
        goals = [
            (i, j)
            for i in range(self.n)
            for j in range(self.n)
            if self.grid[i][j] == 0
        ]

        return self._sld_resolve(goals, 0)

    # ------------------------------------------------------------------
    # SLD Resolution engine
    # ------------------------------------------------------------------

    def _sld_resolve(self, goals: list, idx: int) -> bool:
        """
        SLD resolution: chọn goal thứ idx, resolve với clause phù hợp.
        Mỗi goal = chứng minh Val(row, col, ?) là True.
        """
        if idx == len(goals):
            return True  # Tất cả goals đã được chứng minh

        row, col = goals[idx]

        # Nếu đã có trong KB (given hoặc đã gán) → goal đã thỏa
        if (row, col) in self.kb:
            return self._sld_resolve(goals, idx + 1)

        # Thử unify goal Val(row,col,?) với từng clause Val(row,col,v)
        for val in range(1, self.n + 1):
            if self.should_stop():
                return False

            # Bước unification: thử gán val cho (row, col)
            if self._prove_val(row, col, val):
                # Unification thành công → thêm vào KB
                self.kb[(row, col)] = val
                self.grid[row][col] = val
                self.record_step(row, col, val, ACTION_ASSIGN)

                # Resolve sub-goals còn lại
                if self._sld_resolve(goals, idx + 1):
                    return True

                # Sub-goals fail → undo unification (backtrack)
                del self.kb[(row, col)]
                self.grid[row][col] = 0
                self.record_step(row, col, 0, ACTION_BACKTRACK)

        return False  # Không unify được → fail goal này

    # ------------------------------------------------------------------
    # Horn clause: Val(i,j,v) :- not_in_row ^ not_in_col ^ satisfies_ineq
    # ------------------------------------------------------------------

    def _prove_val(self, row: int, col: int, val: int) -> bool:
        """
        Chứng minh Val(row,col,val) bằng cách prove tất cả sub-goals
        trong body của Horn clause.
        """
        self.inferences += 1

        # Sub-goal 1: not_in_row(row, col, val)
        # Tức là: không có j' != col nào trong KB có Val(row,j',val) = True
        if not self._prove_not_in_row(row, col, val):
            return False

        # Sub-goal 2: not_in_col(row, col, val)
        if not self._prove_not_in_col(row, col, val):
            return False

        # Sub-goal 3: satisfies_inequalities(row, col, val)
        if not self._prove_inequalities(row, col, val):
            return False

        return True

    def _prove_not_in_row(self, row: int, col: int, val: int) -> bool:
        """Prove: val chưa xuất hiện ở hàng row (trừ col)."""
        for j in range(self.n):
            if j != col and self.kb.get((row, j)) == val:
                return False
        return True

    def _prove_not_in_col(self, row: int, col: int, val: int) -> bool:
        """Prove: val chưa xuất hiện ở cột col (trừ row)."""
        for i in range(self.n):
            if i != row and self.kb.get((i, col)) == val:
                return False
        return True

    def _prove_inequalities(self, row: int, col: int, val: int) -> bool:
        """Prove: val thỏa tất cả inequality constraints liên quan."""
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        # Trái: KB[(row, col-1)] ? val
        if col > 0 and (row, col-1) in self.kb:
            left = self.kb[(row, col-1)]
            c = hc[row][col-1]
            if c == 1 and not (left < val):
                return False
            if c == -1 and not (left > val):
                return False

        # Phải: val ? KB[(row, col+1)]
        if col < self.n-1 and (row, col+1) in self.kb:
            right = self.kb[(row, col+1)]
            c = hc[row][col]
            if c == 1 and not (val < right):
                return False
            if c == -1 and not (val > right):
                return False

        # Trên: KB[(row-1, col)] ? val
        if row > 0 and (row-1, col) in self.kb:
            above = self.kb[(row-1, col)]
            c = vc[row-1][col]
            if c == 1 and not (above < val):
                return False
            if c == -1 and not (above > val):
                return False

        # Dưới: val ? KB[(row+1, col)]
        if row < self.n-1 and (row+1, col) in self.kb:
            below = self.kb[(row+1, col)]
            c = vc[row][col]
            if c == 1 and not (val < below):
                return False
            if c == -1 and not (val > below):
                return False

        return True