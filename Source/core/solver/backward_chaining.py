"""
Backward Chaining solver - SLD Resolution (Prolog-like interpreter).

Kiến trúc:
    KB (Knowledge Base):
        - 1 Horn clause tổng quát:
              val(I, J, V) :-
                  between(1, N, V),
                  not_same_row(I, J, V),
                  not_same_col(I, J, V),
                  satisfy_ineq(I, J, V).
        - N unit fact cho mỗi ô given:
              val(i, j, v) :- .   (fact, body rỗng)

    Query:
        Với mỗi ô trống (i,j), đặt query: ?- val(i, j, V).
        SLD engine thử tìm V thoả mãn, commit vào grid, rồi query ô tiếp theo.
        Nếu nhánh thất bại -> backtrack, thử giá trị V tiếp theo.

    Fix so với phiên bản cũ:
        - [CRITICAL] Grid được cập nhật NGAY KHI mỗi ô được gán.
          Built-ins (not_same_row, not_same_col, satisfy_ineq) đọc ctx.grid
          -> Chúng thấy đúng trạng thái hiện tại, không chỉ các ô given ban đầu.
        - Mỗi ô được query độc lập (Prolog-like: ?- val(i,j,V)) thay vì
          truyền tất cả goal một lần -> đúng ngữ nghĩa "query Val(i,j,?) for each cell".
        - record_step() được gọi trong quá trình solve (không phải sau), đảm bảo
          visualization nhìn thấy từng bước gán / backtrack.
"""

from typing import Dict, Generator, List, Optional, Tuple, Union

from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


# ======================================================================
# Cấu trúc dữ liệu logic
# ======================================================================

class Var:
    """Biến logic Prolog: ?Name"""
    __slots__ = ('name',)

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):   return f"?{self.name}"
    def __hash__(self):   return hash(self.name)
    def __eq__(self, other): return isinstance(other, Var) and self.name == other.name


class Term:
    """Hạng thức Prolog: functor(arg1, arg2, ...)"""
    __slots__ = ('functor', 'args')

    def __init__(self, functor: str, args: Tuple):
        self.functor = functor
        self.args    = args

    def __repr__(self):
        return f"{self.functor}({', '.join(str(a) for a in self.args)})"

    def __eq__(self, other):
        return (isinstance(other, Term)
                and self.functor == other.functor
                and self.args    == other.args)

    def __hash__(self):
        return hash((self.functor, self.args))


class Clause:
    """Horn clause: head :- body."""
    __slots__ = ('head', 'body')

    def __init__(self, head: Term, body: List[Term]):
        self.head = head
        self.body = body


# ======================================================================
# Substitution (ánh xạ Var -> giá trị)
# ======================================================================

Substitution = Dict[Var, Union[int, 'Var', 'Term']]


def apply_subst(subst: Substitution,
                term: Union[int, Var, Term]) -> Union[int, Var, Term]:
    """Áp dụng substitution (có phát hiện chu trình để tránh infinite loop)."""
    if isinstance(term, int):
        return term
    if isinstance(term, Var):
        visited: set = set()
        cur = term
        while cur in subst:
            if cur in visited:
                return cur          # chu trình -> trả về bản thân
            visited.add(cur)
            nxt = subst[cur]
            if isinstance(nxt, Var):
                cur = nxt
            else:
                return nxt
        return cur
    # Term: áp dụng đệ quy lên từng argument
    return Term(term.functor, tuple(apply_subst(subst, a) for a in term.args))


# ======================================================================
# Unification (Robinson, 1965) + occurs check
# ======================================================================

def unify(t1: Union[int, Var, Term],
          t2: Union[int, Var, Term],
          subst: Substitution) -> Optional[Substitution]:
    t1 = apply_subst(subst, t1)
    t2 = apply_subst(subst, t2)

    if t1 == t2:
        return subst.copy()

    if isinstance(t1, Var):
        return _bind_var(t1, t2, subst)
    if isinstance(t2, Var):
        return _bind_var(t2, t1, subst)

    if isinstance(t1, Term) and isinstance(t2, Term):
        if t1.functor != t2.functor or len(t1.args) != len(t2.args):
            return None
        s = subst.copy()
        for a1, a2 in zip(t1.args, t2.args):
            s = unify(a1, a2, s)
            if s is None:
                return None
        return s

    return None


def _bind_var(var: Var,
              term: Union[int, Var, Term],
              subst: Substitution) -> Optional[Substitution]:
    if var in subst:
        return unify(subst[var], term, subst)
    if isinstance(term, Var) and term in subst:
        return unify(var, subst[term], subst)
    if _occurs(var, term, subst):
        return None                 # occurs check: tránh vòng lặp
    s = subst.copy()
    s[var] = term
    return s


def _occurs(var: Var,
            term: Union[int, Var, Term],
            subst: Substitution) -> bool:
    term = apply_subst(subst, term)
    if isinstance(term, Var):
        return term == var
    if isinstance(term, Term):
        return any(_occurs(var, a, subst) for a in term.args)
    return False


# ======================================================================
# Đổi tên biến (clause renaming)
# ======================================================================

def rename_vars(clause: Clause, counter: List[int]) -> Clause:
    """
    Đổi tên tất cả biến trong clause bằng suffix _<counter> để tránh
    xung đột giữa các lần resolve.
    """
    var_map: Dict[Var, Var] = {}

    def rename(t):
        if isinstance(t, Var):
            if t not in var_map:
                counter[0] += 1
                var_map[t] = Var(f"{t.name}_{counter[0]}")
            return var_map[t]
        if isinstance(t, Term):
            return Term(t.functor, tuple(rename(a) for a in t.args))
        return t

    return Clause(rename(clause.head), [rename(b) for b in clause.body])


# ======================================================================
# SLD Resolution engine (generator)
# ======================================================================

# Giới hạn độ sâu đệ quy để tránh RecursionError trên puzzle lớn
_MAX_DEPTH = 4000


def prove(goals:      List[Term],
          subst:      Substitution,
          kb:         List[Clause],
          builtins:   Dict,
          solver_ctx: 'BackwardChainingSolver',
          depth:      int        = 0,
          counter:    List[int]  = None) -> Generator[Substitution, None, None]:
    """
    SLD Resolution engine (Prolog-style, depth-first, left-to-right).

    Với danh sách goals, cố gắng chứng minh goal đầu tiên bằng cách:
        1. Nếu là built-in -> gọi hàm Python tương ứng (yield subst mới).
        2. Nếu không -> duyệt KB, unify với head của clause, thêm body vào goals.
    Đệ quy cho đến khi goals rỗng -> yield substitution hoàn chỉnh.
    """
    if counter is None:
        counter = [0]

    # Điều kiện dừng
    if depth > _MAX_DEPTH or solver_ctx.should_stop():
        return
    if not goals:
        yield subst
        return

    # Lấy goal đầu tiên (leftmost), áp subst hiện tại
    goal = apply_subst(subst, goals[0])
    rest = goals[1:]

    if not isinstance(goal, Term):
        return

    # --- Built-in predicate ---
    if goal.functor in builtins:
        try:
            for new_subst in builtins[goal.functor](goal.args, subst, solver_ctx):
                yield from prove(rest, new_subst, kb, builtins,
                                 solver_ctx, depth + 1, counter)
        except Exception:
            pass
        return

    # --- Duyệt KB: thử từng clause khớp với goal ---
    for clause in kb:
        local_counter = [counter[0]]
        renamed       = rename_vars(clause, local_counter)
        new_subst     = unify(goal, renamed.head, subst)
        if new_subst is not None:
            new_goals = renamed.body + rest
            yield from prove(new_goals, new_subst, kb, builtins,
                             solver_ctx, depth + 1, local_counter)
            counter[0] = local_counter[0]   # cập nhật counter chung


# ======================================================================
# Built-in predicates
# ======================================================================

def _to_int(term, subst: Substitution) -> int:
    resolved = apply_subst(subst, term)
    if isinstance(resolved, int):
        return resolved
    raise ValueError(f"Cannot resolve {term!r} to int (got {resolved!r})")


def builtin_between(args, subst: Substitution, ctx: 'BackwardChainingSolver'):
    """
    between(Low, High, V): V là số nguyên trong [Low, High].
    Nếu V chưa được bind -> enumerate từng giá trị.
    """
    low, high, v = args
    lo = _to_int(low,  subst)
    hi = _to_int(high, subst)

    v_resolved = apply_subst(subst, v)
    if isinstance(v_resolved, int):
        if lo <= v_resolved <= hi:
            yield subst
    else:
        # V chưa được gán -> thử tất cả
        for val in range(lo, hi + 1):
            ctx.inferences += 1
            new_subst = subst.copy()
            new_subst[v_resolved] = val   # v_resolved là Var
            yield new_subst


def builtin_not_same_row(args, subst: Substitution, ctx: 'BackwardChainingSolver'):
    """
    not_same_row(I, J, V): không có ô nào cùng hàng I (trừ cột J) có giá trị V.
    Đọc ctx.grid để thấy đúng trạng thái hiện tại (kể cả ô đã gán trong prove).
    """
    i_val = _to_int(args[0], subst)
    j_val = _to_int(args[1], subst)
    v_val = _to_int(args[2], subst)
    ctx.inferences += 1
    for col in range(ctx.n):
        if col != j_val and ctx.grid[i_val][col] == v_val:
            return                  # vi phạm -> không yield
    yield subst


def builtin_not_same_col(args, subst: Substitution, ctx: 'BackwardChainingSolver'):
    """
    not_same_col(I, J, V): không có ô nào cùng cột J (trừ hàng I) có giá trị V.
    """
    i_val = _to_int(args[0], subst)
    j_val = _to_int(args[1], subst)
    v_val = _to_int(args[2], subst)
    ctx.inferences += 1
    for row in range(ctx.n):
        if row != i_val and ctx.grid[row][j_val] == v_val:
            return
    yield subst


def builtin_satisfy_ineq(args, subst: Substitution, ctx: 'BackwardChainingSolver'):
    """
    satisfy_ineq(I, J, V): V thỏa mãn tất cả ràng buộc bất đẳng thức
    liên quan đến ô (I, J) với các ô kế cận ĐÃ CÓ GIÁ TRỊ trong grid.
    """
    i_val = _to_int(args[0], subst)
    j_val = _to_int(args[1], subst)
    v_val = _to_int(args[2], subst)
    ctx.inferences += 1

    hc = ctx.puzzle["h_constraints"]
    vc = ctx.puzzle["v_constraints"]
    n  = ctx.n
    g  = ctx.grid   # đọc trực tiếp -> thấy đúng trạng thái hiện tại

    # Trái: g[i][j-1] < v  hoặc  g[i][j-1] > v
    if j_val > 0 and g[i_val][j_val - 1] != 0:
        left = g[i_val][j_val - 1]
        c = hc[i_val][j_val - 1]
        if c == 1  and not (left < v_val): return
        if c == -1 and not (left > v_val): return

    # Phải: v < g[i][j+1]  hoặc  v > g[i][j+1]
    if j_val < n - 1 and g[i_val][j_val + 1] != 0:
        right = g[i_val][j_val + 1]
        c = hc[i_val][j_val]
        if c == 1  and not (v_val < right): return
        if c == -1 and not (v_val > right): return

    # Trên: g[i-1][j] < v  hoặc  g[i-1][j] > v
    if i_val > 0 and g[i_val - 1][j_val] != 0:
        up = g[i_val - 1][j_val]
        c = vc[i_val - 1][j_val]
        if c == 1  and not (up < v_val): return
        if c == -1 and not (up > v_val): return

    # Dưới: v < g[i+1][j]  hoặc  v > g[i+1][j]
    if i_val < n - 1 and g[i_val + 1][j_val] != 0:
        down = g[i_val + 1][j_val]
        c = vc[i_val][j_val]
        if c == 1  and not (v_val < down): return
        if c == -1 and not (v_val > down): return

    yield subst


# ======================================================================
# Xây dựng KB từ puzzle
# ======================================================================

def build_futoshiki_kb(n: int, puzzle: dict) -> List[Clause]:
    """
    KB gồm:
        1. 1 Horn clause tổng quát:
               val(I, J, V) :-
                   between(1, N, V),
                   not_same_row(I, J, V),
                   not_same_col(I, J, V),
                   satisfy_ineq(I, J, V).
        2. Unit fact cho mỗi ô đã cho sẵn:
               val(i, j, v).
    """
    I, J, V = Var('I'), Var('J'), Var('V')

    general_rule = Clause(
        head = Term('val', (I, J, V)),
        body = [
            Term('between',      (1, n, V)),
            Term('not_same_row', (I, J, V)),
            Term('not_same_col', (I, J, V)),
            Term('satisfy_ineq', (I, J, V)),
        ]
    )

    clauses = [general_rule]

    # Thêm fact cho các ô given (body rỗng = luôn đúng)
    grid = puzzle["grid"]
    for i in range(n):
        for j in range(n):
            v = grid[i][j]
            if v != 0:
                clauses.append(Clause(Term('val', (i, j, v)), []))

    return clauses


# ======================================================================
# BackwardChainingSolver
# ======================================================================

class BackwardChainingSolver(BaseSolver):
    """
    Backward Chaining solver – SLD Resolution (Prolog-like interpreter).

    Cách hoạt động:
        1. Xây dựng KB từ Horn clause + given clues.
        2. Sắp xếp các ô trống theo domain size tăng dần (MRV heuristic).
        3. Với mỗi ô (i,j), đặt Prolog query: ?- val(i, j, V).
        4. SLD engine tìm V hợp lệ:
               - between(1,N,V)      : V nằm trong [1,N]
               - not_same_row(I,J,V) : V chưa có trong hàng i (đọc grid thực)
               - not_same_col(I,J,V) : V chưa có trong cột j (đọc grid thực)
               - satisfy_ineq(I,J,V) : V thỏa bất đẳng thức với kế cận
        5. Khi tìm được V -> gán vào grid (để built-ins thấy ở bước sau).
        6. Đệ quy sang ô tiếp theo. Nếu thất bại -> backtrack (xóa khỏi grid,
           thử V tiếp theo từ generator).

    Điểm khác biệt với Backtracking thông thường:
        - Constraint check được thực hiện thông qua SLD unification và
          built-in predicates, không phải gọi is_valid() trực tiếp.
        - Mô hình logic (KB + query) tách biệt với cơ chế tìm kiếm.
    """

    def __init__(self, puzzle: dict):
        super().__init__(puzzle)
        self._builtins: Dict = {
            'between':      builtin_between,
            'not_same_row': builtin_not_same_row,
            'not_same_col': builtin_not_same_col,
            'satisfy_ineq': builtin_satisfy_ineq,
        }
        self._kb: List[Clause] = build_futoshiki_kb(self.n, puzzle)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def _solve(self) -> bool:
        try:
            return self._solve_impl()
        except RecursionError:
            # Puzzle quá lớn -> Python stack overflow, trả về False
            return False
        except Exception:
            import traceback
            traceback.print_exc()
            return False

    def _solve_impl(self) -> bool:
        # Lấy danh sách ô trống, sắp xếp theo domain nhỏ nhất trước (MRV)
        empty_cells = [
            (i, j)
            for i in range(self.n)
            for j in range(self.n)
            if self.grid[i][j] == 0
        ]
        empty_cells.sort(key=lambda cell: self._estimate_domain(cell[0], cell[1]))

        return self._query_cells(empty_cells, 0)

    # ------------------------------------------------------------------
    # Prolog-like cell-by-cell query  <-- FIX CHÍNH
    # ------------------------------------------------------------------

    def _query_cells(self, cells: List[Tuple[int, int]], idx: int) -> bool:
        """
        Với mỗi ô trong cells[idx:], đặt query ?- val(i, j, V) và commit
        kết quả vào self.grid trước khi query ô tiếp theo.

        Đây là điểm mấu chốt:
            - Grid được cập nhật NGAY SAU KHI tìm được V.
            - Built-ins ở bước tiếp theo đọc grid -> thấy đúng trạng thái.
            - Nếu nhánh con thất bại -> xóa grid[i][j] = 0 rồi thử V tiếp.
        """
        if idx == len(cells):
            return True                 # Tất cả ô đã được gán -> xong

        i, j = cells[idx]

        # Tạo biến V cho query
        V    = Var('V')
        goal = Term('val', (i, j, V))

        # Gọi SLD engine: generate từng substitution thoả mãn val(i,j,V)
        counter = [0]
        for subst in prove([goal], {}, self._kb, self._builtins,
                           self, 0, counter):

            if self.should_stop():
                return False

            # Lấy giá trị từ substitution
            v_term = apply_subst(subst, V)
            if not isinstance(v_term, int):
                continue              # V chưa được ground -> bỏ qua

            # --- COMMIT: gán vào grid để built-ins thấy ở bước sau ---
            self.grid[i][j] = v_term
            self.record_step(i, j, v_term, ACTION_ASSIGN)

            # Đệ quy sang ô tiếp theo
            if self._query_cells(cells, idx + 1):
                return True

            # --- BACKTRACK: gỡ gán, thử V tiếp theo ---
            self.grid[i][j] = 0
            self.record_step(i, j, 0, ACTION_BACKTRACK)

        return False    # Không có V nào hợp lệ -> báo thất bại lên trên

    # ------------------------------------------------------------------
    # MRV heuristic: ước lượng số giá trị khả thi còn lại của ô (i,j)
    # ------------------------------------------------------------------

    def _estimate_domain(self, row: int, col: int) -> int:
        """
        Đếm số giá trị trong [1,N] chưa vi phạm:
            - uniqueness hàng/cột
            - bất đẳng thức với các ô kế cận đã có giá trị

        Giá trị trả về nhỏ -> ưu tiên chọn trước (MRV).
        """
        used = set()
        for j in range(self.n):
            if self.grid[row][j] != 0:
                used.add(self.grid[row][j])
        for i in range(self.n):
            if self.grid[i][col] != 0:
                used.add(self.grid[i][col])

        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]
        g  = self.grid
        n  = self.n
        count = 0

        for val in range(1, n + 1):
            if val in used:
                continue
            ok = True

            if col > 0 and g[row][col - 1] != 0:
                c = hc[row][col - 1]
                if c == 1  and not (g[row][col - 1] < val): ok = False
                if c == -1 and not (g[row][col - 1] > val): ok = False

            if ok and col < n - 1 and g[row][col + 1] != 0:
                c = hc[row][col]
                if c == 1  and not (val < g[row][col + 1]): ok = False
                if c == -1 and not (val > g[row][col + 1]): ok = False

            if ok and row > 0 and g[row - 1][col] != 0:
                c = vc[row - 1][col]
                if c == 1  and not (g[row - 1][col] < val): ok = False
                if c == -1 and not (g[row - 1][col] > val): ok = False

            if ok and row < n - 1 and g[row + 1][col] != 0:
                c = vc[row][col]
                if c == 1  and not (val < g[row + 1][col]): ok = False
                if c == -1 and not (val > g[row + 1][col]): ok = False

            if ok:
                count += 1

        return count