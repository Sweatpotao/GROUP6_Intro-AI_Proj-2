"""
Quy trình:
    FOL axioms (A1..A8)
        -> Ground: thay biến bằng số cụ thể (i,j,v trong 1..N)
        -> CNF: mỗi axiom thành list các clauses
        -> KB: tập hợp tất cả clauses

Encoding:
    Mỗi atom Val(i,j,v) được ánh xạ tới một số nguyên dương (literal ID).
    Literal âm = phủ định.
    Clause = list các literal (int), thỏa mãn khi ít nhất 1 literal đúng.

    Val(i, j, v) -> ID = i*N*N + j*N + (v-1) + 1
    i, j: 0-indexed | v: 1-indexed

Vd: N=4:
    Val(0,0,1) = 1
    Val(0,0,2) = 2
    Val(0,3,4) = 16
    Val(3,3,4) = 64  <- ID lớn nhất
"""


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def var(i: int, j: int, v: int, n: int) -> int:
    # Chuyển Val(i,j,v) thành integer ID (1-indexed)
    return i * n * n + j * n + (v - 1) + 1


def decode_var(lit: int, n: int) -> tuple:
    # Chuyển integer ID ngược lại thành (i, j, v)
    lit = abs(lit) - 1
    i   = lit // (n * n)
    j   = (lit % (n * n)) // n
    v   = (lit % n) + 1
    return (i, j, v)


# ---------------------------------------------------------------------------
# Axioms -> CNF clauses
# ---------------------------------------------------------------------------

def axiom_a1(n: int) -> list:
    # A1: Mỗi ô (i,j) có ít nhất 1 giá trị
    # FOL: forall i,j: exists v: Val(i,j,v)
    # CNF: với mỗi (i,j): [Val(i,j,1) v Val(i,j,2) v ... v Val(i,j,N)]
    clauses = []
    for i in range(n):
        for j in range(n):
            clause = [var(i, j, v, n) for v in range(1, n + 1)]
            clauses.append(clause)
    return clauses


def axiom_a2(n: int) -> list:
    # A2: Mỗi ô (i,j) có nhiều nhất 1 giá trị
    # FOL: forall i,j,v1,v2: Val(i,j,v1) ^ Val(i,j,v2) -> v1=v2
    # CNF: với mỗi (i,j), mỗi cặp v1<v2: [-Val(i,j,v1), -Val(i,j,v2)]
    clauses = []
    for i in range(n):
        for j in range(n):
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    clauses.append([-var(i, j, v1, n), -var(i, j, v2, n)])
    return clauses


def axiom_a3(n: int) -> list:
    # A3: Row uniqueness - mỗi hàng không có 2 ô cùng giá trị
    # FOL: forall i,j1,j2,v: Val(i,j1,v) ^ Val(i,j2,v) ^ j1!=j2 -> False
    # CNF: với mỗi i, v, mỗi cặp j1<j2: [-Val(i,j1,v), -Val(i,j2,v)]
    clauses = []
    for i in range(n):
        for v in range(1, n + 1):
            for j1 in range(n):
                for j2 in range(j1 + 1, n):
                    clauses.append([-var(i, j1, v, n), -var(i, j2, v, n)])
    return clauses


def axiom_a6(n: int) -> list:
    # A6: Column uniqueness - mỗi cột không có 2 ô cùng giá trị
    # FOL: forall j,i1,i2,v: Val(i1,j,v) ^ Val(i2,j,v) ^ i1!=i2 -> False
    # CNF: với mỗi j, v, mỗi cặp i1<i2: [-Val(i1,j,v), -Val(i2,j,v)]
    clauses = []
    for j in range(n):
        for v in range(1, n + 1):
            for i1 in range(n):
                for i2 in range(i1 + 1, n):
                    clauses.append([-var(i1, j, v, n), -var(i2, j, v, n)])
    return clauses


def axiom_a4(puzzle: dict) -> list:
    # A4: Horizontal less-than constraints
    # FOL: forall i,j,v1,v2: LessH(i,j) ^ Val(i,j,v1) ^ Val(i,j+1,v2) -> Less(v1,v2)
    # CNF: với mỗi (i,j) có LessH, mỗi cặp (v1,v2) mà KHÔNG v1<v2:
    #      [-Val(i,j,v1), -Val(i,j+1,v2)]
    n  = puzzle["size"]
    hc = puzzle["h_constraints"]
    clauses = []
    for i in range(n):
        for j in range(n - 1):
            if hc[i][j] == 1:   # LessH(i,j): (i,j) < (i,j+1)
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 < v2):
                            clauses.append([-var(i, j, v1, n), -var(i, j + 1, v2, n)])
            elif hc[i][j] == -1:  # GreaterH(i,j): (i,j) > (i,j+1)
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 > v2):
                            clauses.append([-var(i, j, v1, n), -var(i, j + 1, v2, n)])
    return clauses


def axiom_a7(puzzle: dict) -> list:
    # A7: Vertical inequality constraints
    # FOL: forall i,j,v1,v2: LessV(i,j) ^ Val(i,j,v1) ^ Val(i+1,j,v2) -> Less(v1,v2)
    # CNF: tương tự A4 nhưng theo chiều dọc
    n  = puzzle["size"]
    vc = puzzle["v_constraints"]
    clauses = []
    for i in range(n - 1):
        for j in range(n):
            if vc[i][j] == 1:    # LessV(i,j): (i,j) < (i+1,j)
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 < v2):
                            clauses.append([-var(i, j, v1, n), -var(i + 1, j, v2, n)])
            elif vc[i][j] == -1:  # GreaterV(i,j): (i,j) > (i+1,j)
                for v1 in range(1, n + 1):
                    for v2 in range(1, n + 1):
                        if not (v1 > v2):
                            clauses.append([-var(i, j, v1, n), -var(i + 1, j, v2, n)])
    return clauses


def axiom_a5(puzzle: dict) -> list:
    # A5: Given clues - ô đã cho sẵn phải giữ nguyên giá trị
    # FOL: forall i,j,v: Given(i,j,v) -> Val(i,j,v)
    # CNF: với mỗi given (i,j,v): [Val(i,j,v)]  <- unit clause
    n  = puzzle["size"]
    clauses = []
    for i in range(n):
        for j in range(n):
            v = puzzle["grid"][i][j]
            if v != 0:
                clauses.append([var(i, j, v, n)])
    return clauses


# ---------------------------------------------------------------------------
# KB generation
# ---------------------------------------------------------------------------

def generate_kb(puzzle: dict) -> dict:
    """
    Sinh toàn bộ Knowledge Base (KB) từ FOL axioms cho puzzle cụ thể

    Return:
        {
            "n_vars":   int,           # tổng số biến propositional
            "clauses":  list[list],    # toàn bộ clauses (CNF)
            "n_clauses": int,
            "axioms": {                # clauses phân theo axiom (debug/report purpose)
                "A1": [...],
                "A2": [...],
                ...
            }
        }
    """
    n = puzzle["size"]

    axioms = {
        "A1": axiom_a1(n),            # at-least-one value per cell
        "A2": axiom_a2(n),            # at-most-one value per cell
        "A3": axiom_a3(n),            # row uniqueness
        "A6": axiom_a6(n),            # column uniqueness
        "A4": axiom_a4(puzzle),       # horizontal inequality
        "A7": axiom_a7(puzzle),       # vertical inequality
        "A5": axiom_a5(puzzle),       # given clues (unit clauses)
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
    lines = [
        f"KB Summary (N={int(round(kb['n_vars'] ** (1/3)))}x{int(round(kb['n_vars'] ** (1/3)))})",
        f"  Total variables : {kb['n_vars']}",
        f"  Total clauses   : {kb['n_clauses']}",
        "  Breakdown by axiom:",
    ]
    for name, clauses in kb["axioms"].items():
        lines.append(f"    {name}: {len(clauses)} clauses")
    return "\n".join(lines)