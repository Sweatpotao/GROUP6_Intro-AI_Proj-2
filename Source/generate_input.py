import json
import os
import random
import sys

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

INPUT_DIR = os.path.join(os.path.dirname(__file__), "Inputs")

# Phân bổ theo size: 10 inputs -> 2 mỗi size, 20 -> 4, 50 -> 10
SIZES = [4, 5, 6, 7, 9]

VALID_COUNTS = [10, 20, 50]

# Tỉ lệ ô given so với tổng ô (N*N), theo size
# Puzzle nhỏ cần nhiều given hơn để có lời giải unique
GIVEN_RATIO = {
    4: 0.35,
    5: 0.30,
    6: 0.25,
    7: 0.22,
    9: 0.18,
}

# Số lượng inequality constraints theo size
CONSTRAINT_RATIO = {
    4: 0.30,
    5: 0.28,
    6: 0.25,
    7: 0.22,
    9: 0.18,
}


# ---------------------------------------------------------------------------
# Sinh lời giải hợp lệ (Latin Square + inequality)
# ---------------------------------------------------------------------------

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

    return grid


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def _generate_constraints(grid: int, n: int, ratio: float) -> tuple:
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
            hc[i][j] = 1   # "<"
        else:
            hc[i][j] = -1  # ">"

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
    solution = _generate_latin_square(n)
    hc, vc = _generate_constraints(solution, n, CONSTRAINT_RATIO[n])
    grid = _generate_givens(solution, n, GIVEN_RATIO[n])

    return {
        "id":            puzzle_id,
        "size":          n,
        "grid":          grid,
        "h_constraints": hc,
        "v_constraints": vc,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(INPUT_DIR, exist_ok=True)

    # Hỏi số lượng inputs
    print("Futoshiki - Input Generator")
    print("-" * 30)
    print(f"Valid options: {VALID_COUNTS}")

    while True:
        try:
            count = int(input("How many inputs to generate? (10/20/50): ").strip())
            if count in VALID_COUNTS:
                break
            print(f"Please enter one of: {VALID_COUNTS}")
        except ValueError:
            print("Invalid input. Please enter a number.")

    per_size = count // len(SIZES)  # 10->2, 20->4, 50->10

    print(f"\nGenerating {count} inputs ({per_size} per size: {SIZES})...")
    print("-" * 30)

    idx = 1
    for n in SIZES:
        for _ in range(per_size):
            puzzle_id = f"input_{idx:02d}"
            puzzle = generate_puzzle(puzzle_id, n)

            filepath = os.path.join(INPUT_DIR, f"{puzzle_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(puzzle, f, ensure_ascii=False, indent=2)

            print(f"  [{idx:02d}/{count}] {puzzle_id}.json  (size {n}x{n})")
            idx += 1

    print("-" * 30)
    print(f"Done. {count} files saved to: {INPUT_DIR}")


if __name__ == "__main__":
    main()