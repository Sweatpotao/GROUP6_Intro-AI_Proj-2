import os
import sys
import threading
import time
import tracemalloc

sys.path.insert(0, os.path.dirname(__file__))

from core.parser    import load_all_puzzles
from core.logger    import save_output, rebuild_log
from core.formatter import format_grid, print_separator
from core.config    import (
    TIME_LIM,
    STATUS_SOLVED,
    STATUS_UNSOLVABLE,
    STATUS_TIMEOUT,
    STATUS_STEP_LIMIT,
)

from core.solver.forward_chaining  import ForwardChainingSolver
from core.solver.backward_chaining import BackwardChainingSolver
from core.solver.astar_h1          import AStarH1
from core.solver.astar_h2          import AStarH2
from core.solver.astar_h3          import AStarH3
from core.solver.backtracking      import BacktrackingSolver
from core.solver.brute_force       import BruteForceSolver

# ---------------------------------------------------------------------------
# Cấu hình solvers
# ---------------------------------------------------------------------------

SOLVERS = [
    ("forward_chaining",  ForwardChainingSolver),
    ("backward_chaining", BackwardChainingSolver),
    ("astar_h1",          AStarH1),
    ("astar_h2",          AStarH2),
    ("astar_h3",          AStarH3),
    ("backtracking",      BacktrackingSolver),
    ("brute_force",       BruteForceSolver),
]

INPUT_DIR = os.path.join(os.path.dirname(__file__), "Inputs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status_label(status) -> str:
    if status is None:                return "Skipped"
    if status == STATUS_SOLVED:       return "Solved"
    if status == STATUS_TIMEOUT:      return "Timeout"
    if status == STATUS_STEP_LIMIT:   return "Step limit"
    if status == STATUS_UNSOLVABLE:   return "Unsolvable"
    return "Unknown"

# Lock thread
_print_lock = threading.Lock()

def _run_with_timeout(SolverClass, puzzle) -> dict:
    """
    Chạy solver trong thread riêng với giới hạn TIME_LIM giây.
    Nếu quá thời gian -> trả về status=STATUS_TIMEOUT.
    """
    result = [None]
    exc    = [None]
    solver = SolverClass(puzzle)

    # Khởi động đo đạc
    tracemalloc.start()
    tracemalloc.reset_peak()
    t0 = time.perf_counter()

    def target():
        try:
            result[0] = solver.solve()
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()

    # Đợi Solver hoặc timeout
    t.join(timeout = TIME_LIM)

    # Lấy data ngay lập tức
    _, peak = tracemalloc.get_traced_memory()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    tracemalloc.stop()

    # TH: TIMEOUT
    if t.is_alive():
        # Ra hiệu cho solver dừng
        solver.stop_event.set()
        # Đợi tối đa 2s để solver xử lý xong iteration hiện tại
        t.join(timeout=2)

        return {
            "status":     STATUS_TIMEOUT,
            "time_ms":    TIME_LIM * 1000,
            "memory_kb":  round(peak / 1024, 2),
            "inferences": solver.inferences,
            "steps":      solver.steps[:] if solver.steps else None,
            "solution":   None,
        }

    # TH: ERROR
    if exc[0]:
        with _print_lock:
            print(f"    ERROR: {exc[0]}")
        return {
            "status":     STATUS_UNSOLVABLE,
            "time_ms":    None,
            "memory_kb":  None,
            "inferences": None,
            "steps":      None,
            "solution":   None,
        }
    
    # TH: NO-TIMEOUT
    if result[0] and isinstance(result[0], dict):
        result[0]["memory_kb"]  = round(peak / 1024, 2)
        result[0]["time_ms"]    = round(elapsed_ms, 3)

    return result[0]


# ---------------------------------------------------------------------------
# Chạy 1 puzzle
# ---------------------------------------------------------------------------

def run_puzzle(puzzle: dict, verbose: bool = True) -> tuple:
    """
    Chạy tất cả solvers trên 1 puzzle.
    Trả về (solution, algo_results).
    """
    n         = puzzle["size"]
    puzzle_id = puzzle["id"]
    results   = {}
    solution  = None

    if verbose:
        print(f"\n[{puzzle_id}]  size={n}x{n}")
        print_separator()

    for name, SolverClass in SOLVERS:
        r = _run_with_timeout(SolverClass, puzzle)
        results[name] = r

        if solution is None and r.get("status") == STATUS_SOLVED:
            solution = r.get("solution")

        if verbose:
            label = _status_label(r.get("status"))
            t     = f'{r["time_ms"]:.2f} ms'    if r["time_ms"]    is not None else "N/A"
            mem   = f'{r["memory_kb"]:.1f} KB'  if r["memory_kb"]  is not None else "N/A"
            inf   = str(r["inferences"])        if r["inferences"] is not None else "N/A"
            steps = str(len(r["steps"] or []))  if r["steps"]      is not None else "N/A"
            print(f"  [{name}] {label}")
            print(f"    Time      : {t}")
            print(f"    Memory    : {mem}")
            print(f"    Inferences: {inf}")
            print(f"    Steps     : {steps}")

    return solution, results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("  Futoshiki Solver")
    print(f"  Timeout per solver: {TIME_LIM}s")
    print("=" * 50)

    if not os.path.exists(INPUT_DIR):
        print(f"ERROR: Inputs folder not found: {INPUT_DIR}")
        print("Please run generate_inputs.py first.")
        sys.exit(1)

    try:
        puzzles = load_all_puzzles(INPUT_DIR)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Please run generate_inputs.py first.")
        sys.exit(1)

    print(f"\nFound {len(puzzles)} input(s) in: {INPUT_DIR}")
    print(f"Running {len(SOLVERS)} solvers on each...\n")

    total   = len(puzzles)
    success = 0

    for i, puzzle in enumerate(puzzles, 1):
        solution, algo_results = run_puzzle(puzzle, verbose=True)

        save_output(
            input_id   = puzzle["id"],
            size       = puzzle["size"],
            solution   = solution,
            algorithms = algo_results,
        )

        if solution:
            success += 1
            print(f"\n  Solution:")
            for line in format_grid(puzzle, solution).split("\n"):
                print(f"    {line}")
        else:
            print(f"\n  No solution found.")

        print_separator()

    print(f"\n\nLogging data...\n")
    log_path = rebuild_log()

    print(f"{'=' * 50}")
    print(f"  Done: {success}/{total} puzzles solved.")
    print(f"  Log : {log_path}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()