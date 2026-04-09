import json
import os
import re
import random
from core.config import VALID_SIZES

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------
INPUT_DIR = os.path.join(os.path.dirname(__file__), "Inputs")

VALID_COUNTS = [5, 10, 20, 30]

# Tỉ lệ ô given so với tổng ô (N*N), theo size
# Puzzle nhỏ cần nhiều given hơn để có lời giải unique
GIVEN_RATIO = {
    4: 0.40,
    5: 0.36,
    6: 0.30,
    7: 0.25,
    9: 0.20,
}

# Số lượng inequality constraints theo size
CONSTRAINT_RATIO = {
    4: 0.50,
    5: 0.45,
    6: 0.40,
    7: 0.35,
    9: 0.30,
}

# ---------------------------------------------------------------------------
# Xử lý file input_XX.json
# ------------------------------------------------------------------------
def _compact_json(data) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    def compress(match):
        items = re.findall(r'-?[0-9]+', match.group(0))
        return '[' + ', '.join(items) + ']'
    raw = re.sub(r'\[[^\[\]]*?\]', compress, raw, flags=re.DOTALL)
    return raw

# ---------------------------------------------------------------------------
# Sinh lời giải hợp lệ (Latin Square + inequality)
# ---------------------------------------------------------------------------
def _gcd(a, b):
    if b == 0: return a
    return _gcd(b, a % b)

def _generate_latin_square(n: int) -> list:
    """
    Sinh Latin Square ngẫu nhiên NxN.
    Dùng phương pháp shift: hàng i = [(i*step + j) % n + 1]
    rồi shuffle hàng và cột.
    """
    # Bước nhảy phải coprime với n để đảm bảo tính Latin
    step = 1
    for s in range(2, n):
        if _gcd(s, n) == 1:
            step = s
            break

    base = [[(i * step + j) % n + 1 for j in range(n)] for i in range(n)]

    # Shuffle hàng
    row_order = list(range(n))
    random.shuffle(row_order)
    grid = [base[r][:] for r in row_order]

    # Shuffle cột
    col_order = list(range(n))
    random.shuffle(col_order)
    grid = [[row[c] for c in col_order] for row in grid]

    # Shuffle giá trị
    symbol_map = list(range(1, n + 1))
    random.shuffle(symbol_map)
    grid = [[symbol_map[v - 1] for v in row] for row in grid]

    return grid

def _generate_constraints(grid: list, n: int, ratio: float) -> tuple:
    """
    Sinh horizontal và vertical constraints ngẫu nhiên dựa trên lời giải.
    Chỉ thêm constraint nếu nó đúng với grid (không tạo mâu thuẫn).
    """
    total_h = n * (n - 1)
    total_v = (n - 1) * n
    num_h = max(1, int(total_h * ratio))
    num_v = max(1, int(total_v * ratio))

    hc = [[0] * (n - 1) for _ in range(n)]
    vc = [[0] * n for _ in range(n - 1)]

    # Chọn ngẫu nhiên các vị trí ngang để đặt constraint
    h_positions = [(i, j) for i in range(n) for j in range(n - 1)]
    random.shuffle(h_positions)
    for i, j in h_positions[:num_h]:
        if grid[i][j] < grid[i][j + 1]:
            hc[i][j] = 1   # <
        else:
            hc[i][j] = -1  # >

    # Chọn ngẫu nhiên các vị trí dọc để đặt constraint
    v_positions = [(i, j) for i in range(n - 1) for j in range(n)]
    random.shuffle(v_positions)
    for i, j in v_positions[:num_v]:
        if grid[i][j] < grid[i + 1][j]:
            vc[i][j] = 1   # "<"
        else:
            vc[i][j] = -1  # ">"

    return hc, vc

def _generate_givens(grid: list, n: int, ratio: float) -> list:
    """
    Chọn ngẫu nhiên một số ô làm given, trả về grid mới (0 = trống).
    """
    num_given = max(n, int(n * n * ratio))  # ít nhất N ô given

    positions = [(i, j) for i in range(n) for j in range(n)]
    random.shuffle(positions)
    given_pos = set(map(tuple, positions[:num_given]))

    result = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(grid[i][j] if (i, j) in given_pos else 0)
        result.append(row)

    return result


# ---------------------------------------------------------------------------
# Tạo 1 puzzle
# ---------------------------------------------------------------------------
def generate_puzzle(puzzle_id: str, n: int) -> dict:
    """Sinh 1 puzzle hoàn chỉnh với lời giải hợp lệ."""
    for attempt in range(100):  # tối đa 100 lần thử
        solution = _generate_latin_square(n)
        hc, vc = _generate_constraints(solution, n, CONSTRAINT_RATIO[n])
        grid = _generate_givens(solution, n, GIVEN_RATIO[n])

        if _has_unique_solution(grid, hc, vc, n):
            return {
                "id":            puzzle_id,
                "size":          n,
                "grid":          grid,
                "h_constraints": hc,
                "v_constraints": vc,
                "answer":        solution,
            }
    
    raise RuntimeError(f"Failed to generate a unique puzzle for size {n} after 100 attempts.")

def _solve_cell(grid, hc, vc, n, count, limit):
    if count[0] >= limit:
        return

    # MRV: chọn ô trống có ít lựa chọn nhất
    best = None
    best_options = None
    for r in range(n):
        for c in range(n):
            if grid[r][c] == 0:
                options = [v for v in range(1, n+1) if _is_valid(grid, hc, vc, n, r, c, v)]
                if not options:
                    return  # dead end, cắt luôn
                if best is None or len(options) < len(best_options):
                    best = (r, c)
                    best_options = options

    if best is None:
        count[0] += 1
        return

    r, c = best
    for val in best_options:
        grid[r][c] = val
        _solve_cell(grid, hc, vc, n, count, limit)
        grid[r][c] = 0
        if count[0] >= limit:
            return

def _is_valid(grid, hc, vc, n, r, c, val):
    # Kiểm tra Latin Square: không trùng hàng/cột
    for k in range(n):
        if grid[r][k] == val or grid[k][c] == val:
            return False

    # Kiểm tra h_constraints: hàng r
    grid[r][c] = val  # tạm đặt để kiểm tra
    ok = True
    for j in range(n - 1):
        a, b = grid[r][j], grid[r][j + 1]
        if a != 0 and b != 0 and hc[r][j] != 0:
            if hc[r][j] == 1 and not (a < b):
                ok = False; break
            if hc[r][j] == -1 and not (a > b):
                ok = False; break
    # Kiểm tra v_constraints: cột c
    if ok:
        for i in range(n - 1):
            a, b = grid[i][c], grid[i + 1][c]
            if a != 0 and b != 0 and vc[i][c] != 0:
                if vc[i][c] == 1 and not (a < b):
                    ok = False; break
                if vc[i][c] == -1 and not (a > b):
                    ok = False; break
    grid[r][c] = 0  # hoàn tác
    return ok


def _has_unique_solution(grid, hc, vc, n) -> bool:
    """Trả về True nếu puzzle có đúng 1 lời giải."""
    import copy
    g = copy.deepcopy(grid)
    count = [0]
    _solve_cell(g, hc, vc, n, count, limit=2)
    return count[0] == 1

def _cleanup_old_files():
    """Xóa các file input/output cũ trước khi sinh puzzle mới."""
    output_dir = os.path.join(os.path.dirname(__file__), "Outputs")
    deleted = 0

    print(f"\nCleaning old file(s)...")
    for directory, pattern in [
        (INPUT_DIR,  r"^input_\d+\.json$"),
        (output_dir, r"^output_\d+\.json$"),
        (output_dir, r"^log\.json$"),
    ]:
        if not os.path.exists(directory):
            continue
        for fname in os.listdir(directory):
            if re.match(pattern, fname):
                os.remove(os.path.join(directory, fname))
                deleted += 1

    if deleted:
        print(f"Cleaned up {deleted} old file(s).\n")
    else:
        print(f"No file found.\n")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(INPUT_DIR, exist_ok=True)

    # Hỏi số lượng inputs
    print("Futoshiki - Input Generator")
    print("-" * 30)

    # Clear file cũ
    _cleanup_old_files()

    print(f"Valid options: {VALID_COUNTS}")

    while True:
        try:
            count = int(input("How many inputs to generate? : ").strip())
            if count in VALID_COUNTS:
                break
            print(f"Please enter one of: {VALID_COUNTS}")
        except ValueError:
            print("Invalid input. Please enter a number.")

    base = count // len(VALID_SIZES)
    remainder = count % len(VALID_SIZES)
    per_size_list = [base + (1 if i < remainder else 0) for i in range(len(VALID_SIZES))]

    print(f"\nGenerating {count} inputs...")
    print("-" * 30)

    idx = 1
    for size_idx, n in enumerate(VALID_SIZES):
        for _ in range(per_size_list[size_idx]):
            puzzle_id = f"input_{idx:02d}"
            puzzle = generate_puzzle(puzzle_id, n)

            filepath = os.path.join(INPUT_DIR, f"{puzzle_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(_compact_json(puzzle))

            print(f"  [{idx:02d}/{count}] {puzzle_id}.json  (size {n}x{n})")
            idx += 1

    print("-" * 30)
    print(f"Done. {count} files saved to: {INPUT_DIR}\n")


if __name__ == "__main__":
    main()