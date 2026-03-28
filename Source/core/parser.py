import json
import os


def load_puzzle(filepath: str) -> dict:
    # Đọc file input .json và trả về dict chuẩn.
    # Return:
    #         "id":             str,
    #         "size":           int,
    #         "grid":           list[list[int]], N * N
    #         "h_constraints":  list[list[int]], N * (N-1)
    #         "v_constraints":  list[list[int]], (N-1) * N

    if not os.path.exists(filepath): # TH: sai định dạng
        raise FileNotFoundError(f"File: \"{filepath}\" not found")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    _validate(data, filepath)
    return data


def load_all_puzzles(input_dir: str) -> list[dict]:
    # Đọc tất cả file input_XX.json trong thư mục, sắp xếp thứ tự

    files = sorted([
        f for f in os.listdir(input_dir)
        if f.startswith("input_") and f.endswith(".json")
    ])

    if not files:
        raise FileNotFoundError(f"There is no input file in: {input_dir}")

    puzzles = []
    for fname in files:
        path = os.path.join(input_dir, fname)
        puzzles.append(load_puzzle(path))

    return puzzles

# Hàm check data
def _validate(data: dict, filepath: str):
    # Check cấu trúc & kích thước puzzle
    required_keys = ["id", "size", "grid", "h_constraints", "v_constraints"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"[{filepath}] missing field: \"{key}\"")

    n = data["size"]

    # Check grid: N * N
    grid = data["grid"]
    if len(grid) != n:
        raise ValueError(f"[{filepath}] grid must have {n} rows, found {len(grid)}")
    for i, row in enumerate(grid):
        if len(row) != n:
            raise ValueError(f"[{filepath}] grid row {i} must have {n} columns")
        for v in row:
            if not (0 <= v <= n):
                raise ValueError(f"[{filepath}] invalid grid value: {v}")

    # Check horizontal constraints: N * (N-1)
    hc = data["h_constraints"]
    if len(hc) != n:
        raise ValueError(f"[{filepath}] h_constraints must have {n} rows")
    for i, row in enumerate(hc):
        if len(row) != n - 1:
            raise ValueError(f"[{filepath}] h_constraints row {i} must have {n-1} columns")
        for v in row:
            if v not in (-1, 0, 1):
                raise ValueError(f"[{filepath}] invalid h_constraints value: {v}")

    # Check vertical constraints: (N-1) * N
    vc = data["v_constraints"]
    if len(vc) != n - 1:
        raise ValueError(f"[{filepath}] v_constraints must have {n-1} rows")
    for i, row in enumerate(vc):
        if len(row) != n:
            raise ValueError(f"[{filepath}] v_constraints row {i} must have {n} columns")
        for v in row:
            if v not in (-1, 0, 1):
                raise ValueError(f"[{filepath}] invalid v_constraints value: {v}")


def get_givens(puzzle: dict) -> list[tuple]:
    # List các ô cho sẵn: [(row, col, value), ...]
    n = puzzle["size"]
    grid = puzzle["grid"]
    return [
        (i, j, grid[i][j])
        for i in range(n)
        for j in range(n)
        if grid[i][j] != 0
    ]


def get_h_constraint(puzzle: dict, row: int, col: int) -> int:
    # Trả về ràng buộc ngang
    # 1 = '<', -1 = '>', 0 = none
    return puzzle["h_constraints"][row][col]


def get_v_constraint(puzzle: dict, row: int, col: int) -> int:
    # Trả về ràng buộc dọc
    # 1 = '<', -1 = '>', 0 = none
    return puzzle["v_constraints"][row][col]