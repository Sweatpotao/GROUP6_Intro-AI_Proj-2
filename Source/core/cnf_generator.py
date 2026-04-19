"""
Quy trình:
    FOL axioms (A1..A8)
        -> Skolemization: loại bỏ lượng từ tồn tại (∃)
        -> Ground: thay biến bằng số cụ thể (i,j,v trong 1..N)
        -> CNF: phân phối thành clauses (Conjunctive Normal Form)
        -> KB: tập hợp tất cả clauses

Encoding:
    Val(i, j, v) -> ID = i*N*N + j*N + (v-1) + 1
    i, j : 0-indexed (0..N-1)
    v    : 1-indexed (1..N)
    Literal âm = phủ định.

Ví dụ N=4:
    Val(0,0,1)=1  Val(0,3,4)=16  Val(3,3,4)=64  <- ID lớn nhất
"""


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def var(i: int, j: int, v: int, n: int) -> int:
    # Chuyển Val(i,j,v) thành integer ID (1-indexed)
    return i * n * n + j * n + (v - 1) + 1


def decode_var(lit: int, n: int) -> tuple:
    # Chuyển integer ID ngược lại thành (i, j, v)
    idx = abs(lit) - 1
    i   = idx // (n * n)
    j   = (idx % (n * n)) // n
    v   = (idx % n) + 1
    return (i, j, v)

# ---------------------------------------------------------------------------
# Axioms -> CNF clauses
# ---------------------------------------------------------------------------

def axiom_a1(n: int) -> list:
    """
    A1 — At-least-one
    FOL : ∀i, j, ∃v  Val(i,j,v)
    Skolem: ∀i, j  Val(i,j, f(i,j))   với f(i,j) là Skolem function
    Ground: f(i, j) ∈ {1 ... N}
    CNF : [Val(i, j, 1) V ... V Val(i, j, N)]  với mỗi (i,j)
    """
    clauses = []
    for i in range(n):
        for j in range(n):
            clauses.append([var(i, j, v, n) for v in range(1, n + 1)])
    return clauses


def axiom_a2(n: int) -> list:
    """
    A2 — At-most-one
    FOL : ∀i, j, v1, v2  [Val(i, j, v1) ∧ Val(i, j, v2)] -> v1 = v2
    CNF : [-Val(i, j, v1), -Val(i, j, v2)]  với mỗi (i, j), v1 < v2
    """
    clauses = []
    for i in range(n):
        for j in range(n):
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    clauses.append([-var(i, j, v1, n), -var(i, j, v2, n)])
    return clauses


def axiom_a3(n: int) -> list:
    """
    A3 — Row uniqueness
    FOL : ∀i, j1, j2, v  [Val(i, j1, v) ∧ Val(i, j2, v) ∧ j1 ≠ j2] -> ⊥
    CNF : [-Val(i, j1, v), -Val(i, j2, v)]  ∀i, v, j1 < j2
    """
    clauses = []
    for i in range(n):
        for v in range(1, n + 1):
            for j1 in range(n):
                for j2 in range(j1 + 1, n):
                    clauses.append([-var(i, j1, v, n), -var(i, j2, v, n)])
    return clauses


def axiom_a6(n: int) -> list:
    """
    A6 — Column uniqueness
    FOL : ∀j, i1, i2, v  [Val(i1, j, v) ∧ Val(i2, j, v) ∧ i1 ≠ i2] -> ⊥
    CNF : [-Val(i1, j, v), -Val(i2, j, v)]  với mỗi j, v, i1 < i2
    """
    clauses = []
    for j in range(n):
        for v in range(1, n + 1):
            for i1 in range(n):
                for i2 in range(i1 + 1, n):
                    clauses.append([-var(i1, j, v, n), -var(i2, j, v, n)])
    return clauses


def axiom_a4(puzzle: dict) -> list:
    """
    A4 — Horizontal inequality constraints
    FOL : ∀i, j, v1, v2  [LessH(i, j) ∧ Val(i, j, v1) ∧ Val(i, j+1, v2)] → Less(v1, v2)
    CNF : nếu hc[i][j] = 1: [-Val(i, j, v1), -Val(i, j + 1, v2)]  ∀(v1, v2) mà ¬(v1 < v2)
          nếu hc[i][j] =-1: [-Val(i, j, v1), -Val(i, j + 1, v2)]  ∀(v1, v2) mà ¬(v1 > v2)
    """
    n  = puzzle["size"]
    hc = puzzle["h_constraints"]
    clauses = []
    for i in range(n):
        for j in range(n - 1):
            if hc[i][j] == 1:
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 < v2):
                            clauses.append([-var(i, j, v1, n), -var(i, j + 1, v2, n)])
            elif hc[i][j] == -1:
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 > v2):
                            clauses.append([-var(i, j, v1, n), -var(i, j + 1, v2, n)])
    return clauses


def axiom_a7(puzzle: dict) -> list:
    """
    A7 — Vertical inequality constraints
    FOL : ∀i, j, v1, v2
              [LessV(i, j) ∧ Val(i, j, v1) ∧ Val(i + 1, j, v2)] → Less(v1, v2)
    CNF : tương tự A4 nhưng theo chiều dọc
    """
    n  = puzzle["size"]
    vc = puzzle["v_constraints"]
    clauses = []
    for i in range(n - 1):
        for j in range(n):
            if vc[i][j] == 1:
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 < v2):
                            clauses.append([-var(i, j, v1, n), -var(i + 1, j, v2, n)])
            elif vc[i][j] == -1:
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 > v2):
                            clauses.append([-var(i, j, v1, n), -var(i + 1, j, v2, n)])
    return clauses


def axiom_a5(puzzle: dict) -> list:
    """
    A5 — Given clues (unit clauses)
    FOL : ∀i, j, v  Given(i, j, v) -> Val(i, j, v)
    CNF : [Val(i, j, v)] với mỗi ô given
    """
    n = puzzle["size"]
    clauses = []
    for i in range(n):
        for j in range(n):
            v = puzzle["grid"][i][j]
            if v != 0:
                clauses.append([var(i, j, v, n)])
    return clauses


def axiom_a8(n: int) -> list:
    """
    A8 — Value range constraint
    FOL : ∀i, j, v  Val(i, j, v) → (1 ≤ v ≤ N)

    Kết hợp A1 (at-least-one) + A2 (at-most-one) = exactly-one
    A8 tường minh hóa ràng buộc miền giá trị: v phải thuộc {1..N}.

    Trong encoding này, biến propositional chỉ được tạo cho v ∈ {1..N}
    nên A8 sinh cùng clause với A1 — tuy nhiên được giữ tường minh trong
    KB để đảm bảo tính đầy đủ về mặt logic

    CNF : [Val(i, j, 1) V ... V Val(i, j, N)]  với mỗi (i,j)
    """
    clauses = []
    for i in range(n):
        for j in range(n):
            clauses.append([var(i, j, v, n) for v in range(1, n + 1)])
    return clauses


# ---------------------------------------------------------------------------
# KB generation
# ---------------------------------------------------------------------------

def generate_kb(puzzle: dict) -> dict:
    """
    Sinh toàn bộ Knowledge Base (KB) từ FOL axioms cho puzzle cụ thể

    Returns:
        n_vars    : int         — tổng số biến propositional (N^3)
        clauses   : list[list]  — toàn bộ clauses (CNF)
        n_clauses : int
        axioms    : dict        — clauses phân theo từng axiom
    """
    n = puzzle["size"]

    axioms = {
        "A1 — At least one          ": axiom_a1(n),          # at-least-one  (Skolemized)
        "A2 — At most one           ": axiom_a2(n),          # at-most-one
        "A3 — Row uniqueness        ": axiom_a3(n),          # row uniqueness
        "A4 — Horizontal inequality ": axiom_a4(puzzle),     # horizontal inequality
        "A5 — Given clues           ": axiom_a5(puzzle),     # given clues (unit clauses)
        "A6 — Column uniqueness     ": axiom_a6(n),          # column uniqueness
        "A7 — Vertical inequality   ": axiom_a7(puzzle),     # vertical inequality
        "A8 — Value range           ": axiom_a8(n),          # value range (exactly-one, = A1 ∧ A2)
    }

    all_clauses = []
    for clauses in axioms.values():
        all_clauses.extend(clauses)

    return {
        "n_vars":    n * n * n,
        "clauses":   all_clauses,
        "n_clauses": len(all_clauses),
        "axioms":    axioms,
    }


def kb_summary(kb: dict) -> str:
    # In thông tin tổng hợp của KB
    n = int(round(kb["n_vars"] ** (1 / 3)))
    lines = [
        f"KB Summary (N = {n} x {n})",
        f"  Total variables : {kb['n_vars']}",
        f"  Total clauses   : {kb['n_clauses']}",
        "  Breakdown by axiom:",
    ]
    for name, clauses in kb["axioms"].items():
        lines.append(f"    {name}: {len(clauses)} clauses")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_solution(puzzle: dict, solution: list) -> bool:
    # True = solution hợp lệ theo tất cả axioms A1-A7.
    
    n  = puzzle["size"]
    kb = generate_kb(puzzle)

    # Tập literal đúng: Val(i,j,v) = True với v = solution[i][j]
    true_lits = set()
    for i in range(n):
        for j in range(n):
            true_lits.add(var(i, j, solution[i][j], n))

    # Mỗi clause phải có ít nhất 1 literal đúng
    for clause in kb["clauses"]:
        if not any(
            (lit > 0 and lit in true_lits) or
            (lit < 0 and -lit not in true_lits)
            for lit in clause
        ):  return False
    return True