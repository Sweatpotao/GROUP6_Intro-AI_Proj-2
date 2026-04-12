import os
import sys
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

sys.path.insert(0, os.path.dirname(__file__))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Outputs")
OUTPUT_IMG = os.path.join(os.path.dirname(__file__), "Outputs", "comparison.png")

# Status codes (khớp với config.py)
STATUS_UNSOLVABLE = 0
STATUS_SOLVED     = 1
STATUS_TIMEOUT    = 2
STATUS_STEP_LIMIT = 3

STATUS_LABEL = {
    STATUS_SOLVED:     "Solved",
    STATUS_UNSOLVABLE: "Unsolvable",
    STATUS_TIMEOUT:    "Timeout",
    STATUS_STEP_LIMIT: "Step limit",
    None:              "N/A",
}

STATUS_COLOR = {
    STATUS_SOLVED:     "#27ae60",
    STATUS_UNSOLVABLE: "#e74c3c",
    STATUS_TIMEOUT:    "#f39c12",
    STATUS_STEP_LIMIT: "#8e44ad",
    None:              "#bdc3c7",
}

ALGO_COLORS = [
    "#3498db", "#e74c3c", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22",
]


# ---------------------------------------------------------------------------
# Đọc và chuẩn hóa log.json
# ---------------------------------------------------------------------------

def load_all_outputs() -> list:
    """Đọc tất cả output_XX.json trong Outputs/, trả về list."""
    if not os.path.exists(OUTPUT_DIR):
        raise FileNotFoundError(f"Outputs/ folder not found.")

    files = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.startswith("output_") and f.endswith(".json")
    ])

    if not files:
        raise FileNotFoundError(
            "No output files found.\nPlease run main.py first."
        )

    outputs = []
    for fname in files:
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            outputs.append(json.load(f))

    return outputs


def _get_status(algo_result: dict):
    # Hỗ trợ cả format cũ (solved bool) và mới (status int)
    if "status" in algo_result:
        return algo_result["status"]
    solved = algo_result.get("solved")
    if solved is True:
        return STATUS_SOLVED
    if solved is False:
        return STATUS_UNSOLVABLE
    return None


def extract(outputs: list, run_mode: str = "all_all") -> tuple:
    """
    Trích xuất dữ liệu từ list output dicts.

    Returns:
        algos   : list tên algorithm (lấy từ file đầu tiên)
        results : list of dict per input (chuẩn hóa từ output_XX.json)
        sizes   : list of int (puzzle size)
    """
    if not outputs:
        return [], [], []
    
    # Với all_input hoặc all_all: lấy tất cả file
    # Với all_solver: chỉ lấy file đầu tiên (1 input duy nhất)
    if run_mode == "all_solver":
        outputs = outputs[:1]

    # Lấy danh sách algorithm từ file đầu tiên có data
    algos = []
    for out in outputs:
        keys = list(out.get("algorithms", {}).keys())
        if keys:
            algos = keys
            break

    # Chuẩn hóa về cùng format với log.json
    results = []
    for out in outputs:
        results.append({
            "input_id":   out["input_id"],
            "size":       out["size"],
            "algorithms": out.get("algorithms", {}),
        })

    sizes = [r["size"] for r in results]
    return algos, results, sizes


# ---------------------------------------------------------------------------
# Vẽ bảng tổng hợp
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TH: ALL INPUT - ALL SOLVER
# ---------------------------------------------------------------------------

# Biểu đồ cột - đường biểu diễn steps
def _draw_steps_all_all(ax, algos, results):
    n     = len(results)
    width = 0.8 / max(len(algos), 1)
    x     = range(n)
    x_labels = [r["input_id"].replace("input_", "#") for r in results]

    for idx, (algo, color) in enumerate(zip(algos, ALGO_COLORS)):
        steps = []
        for r in results:
            ar         = r["algorithms"].get(algo, {})
            steps_data = ar.get("steps", [])
            count      = len(steps_data) if isinstance(steps_data, list) else int(steps_data or 0)
            steps.append(count)
        offset = (idx - len(algos) / 2 + 0.5) * width
        ax.bar([xi + offset for xi in x], steps, width,
               label=algo, color=color, alpha=0.7, zorder=3)

    ax.set_xticks(list(x))
    ax.set_xticklabels(x_labels, fontsize=8, rotation=30)
    ax.set_title("Step count per Puzzle", fontsize=12, fontweight="bold")
    ax.set_ylabel("Steps")
    ax.set_yscale("log")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)

# Biểu đồ status (stacked bar)
def _draw_status_chart(ax, algos, results):
    ax.set_title("Status count by algorithm", fontsize=12, fontweight="bold")

    status_list = [STATUS_SOLVED, STATUS_TIMEOUT, STATUS_STEP_LIMIT, STATUS_UNSOLVABLE]
    counts      = {s: [] for s in status_list}

    for algo in algos:
        per_status = {s: 0 for s in status_list}
        for r in results:
            ar     = r["algorithms"].get(algo, {})
            status = _get_status(ar)
            if status in per_status:
                per_status[status] += 1
        for s in status_list:
            counts[s].append(per_status[s])

    x      = range(len(algos))
    bottom = [0] * len(algos)

    for status in status_list:
        vals = counts[status]
        ax.bar(x, vals, bottom=bottom, label=STATUS_LABEL[status],
               color=STATUS_COLOR[status], alpha=0.9)
        bottom = [b + v for b, v in zip(bottom, vals)]

    ax.set_xticks(list(x))
    ax.set_xticklabels(algos, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Count")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)

# Biểu đồ thời gian
def _draw_time_chart(ax, algos, results):
    ax.set_title("Execution Time (ms)", fontsize=12, fontweight="bold")

    n        = len(results)
    x_labels = [r["input_id"].replace("input_", "#") for r in results]
    x        = range(n)
    width    = 0.8 / len(algos)

    for idx, (algo, color) in enumerate(zip(algos, ALGO_COLORS)):
        times = []
        for r in results:
            ar = r["algorithms"].get(algo, {})
            t  = ar.get("time_ms")
            times.append(t if t is not None else 0)

        offset = (idx - len(algos) / 2 + 0.5) * width
        bars   = ax.bar([xi + offset for xi in x], times, width, label=algo, color=color, alpha=0.85)

    ax.set_xticks(list(x))
    ax.set_xticklabels(x_labels, fontsize=8, rotation=30)
    ax.set_ylabel("ms")
    ax.set_yscale("log")   # log scale vì brute force >> others
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", alpha=0.3)

# Biểu đồ inferences
def _draw_inference_chart(ax, algos, results):
    ax.set_title("Inferences", fontsize=12, fontweight="bold")

    n        = len(results)
    x_labels = [r["input_id"].replace("input_", "#") for r in results]
    x        = range(n)
    width    = 0.8 / len(algos)

    for idx, (algo, color) in enumerate(zip(algos, ALGO_COLORS)):
        infs = []
        for r in results:
            ar  = r["algorithms"].get(algo, {})
            inf = ar.get("inferences")
            infs.append(inf if inf is not None else 0)

        offset = (idx - len(algos) / 2 + 0.5) * width
        ax.bar([xi + offset for xi in x], infs, width, label=algo, color=color, alpha=0.85)

    ax.set_xticks(list(x))
    ax.set_xticklabels(x_labels, fontsize=8, rotation=30)
    ax.set_ylabel("Inferences")
    ax.set_yscale("log")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", alpha=0.3)

# Biểu đồ thời gian theo size (line chart)
def _draw_time_by_size(ax, algos, results):
    ax.set_title("Avg Runtime (ms) by Puzzle Size", fontsize=12, fontweight="bold")

    # Nhóm theo size
    size_data = {}
    for r in results:
        s = r["size"]
        if s not in size_data:
            size_data[s] = {a: [] for a in algos}
        for algo in algos:
            ar = r["algorithms"].get(algo, {})
            t  = ar.get("time_ms")
            if t is not None:
                size_data[s][algo].append(t)

    sizes = sorted(size_data.keys())

    for algo, color in zip(algos, ALGO_COLORS):
        y = []
        for s in sizes:
            vals = size_data[s].get(algo, [])
            y.append(sum(vals) / len(vals) if vals else 0)
        ax.plot(sizes, y, marker="o", label=algo, color=color, linewidth=1.8)

    ax.set_xticks(sizes)
    ax.set_xticklabels([f"{s}x{s}" for s in sizes])
    ax.set_ylabel("Avg ms")
    ax.set_yscale("log")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(alpha=0.3)

# Memory chart
def _draw_memory_chart(ax, algos, results):
    ax.set_title("Memory Used (KB) per algorithm", fontsize=12, fontweight="bold")
    x_labels = [r["input_id"].replace("input_", "#") for r in results]

    for algo, color in zip(algos, ALGO_COLORS):
        mems = [r["algorithms"].get(algo, {}).get("memory_kb") or 0 for r in results]
        ax.plot(x_labels, mems, marker="o", label=algo,
                color=color, linewidth=1.8, zorder=3)

    ax.set_ylabel("KB")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(linestyle="--", alpha=0.4)

# ---------------------------------------------------------------------------
# TH: ALL INPUT - 1 SOLVER
# ---------------------------------------------------------------------------

# fTime line chart theo input
def _draw_time_line(ax, algos, results):
    x_labels = [r["input_id"].replace("input_", "#") for r in results]
    algo     = algos[0]
    times    = [r["algorithms"].get(algo, {}).get("time_ms") or 0 for r in results]

    ax.plot(x_labels, times, marker="o", color=ALGO_COLORS[0], linewidth=2, markersize=7, zorder=3)
    # Chú thích giá trị mỗi điểm
    for i, v in enumerate(times):
        ax.annotate(f"{v:.1f}", (x_labels[i], times[i]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7)

    ax.set_title(f"Execution Time (ms)", fontsize=12, fontweight="bold")
    ax.set_ylabel("ms")
    ax.set_yscale("log")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    ax.grid(linestyle="--", alpha=0.4)


# Inferences line chart theo input
def _draw_inferences_line(ax, algos, results):
    x_labels = [r["input_id"].replace("input_", "#") for r in results]
    algo     = algos[0]
    infs     = [r["algorithms"].get(algo, {}).get("inferences") or 0 for r in results]

    ax.plot(x_labels, infs, marker="s", color=ALGO_COLORS[1], linewidth=2, markersize=7, zorder=3)
    for i, v in enumerate(infs):
        ax.annotate(f"{int(v)}", (x_labels[i], infs[i]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7)

    ax.set_title(f"Inference Count", fontsize=12, fontweight="bold")
    ax.set_ylabel("Inferences")
    ax.set_yscale("log")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    ax.grid(linestyle="--", alpha=0.4)


# Memory line chart theo input
def _draw_memory_line(ax, algos, results):
    x_labels = [r["input_id"].replace("input_", "#") for r in results]
    algo     = algos[0]
    mems     = [r["algorithms"].get(algo, {}).get("memory_kb") or 0 for r in results]

    ax.plot(x_labels, mems, marker="^", color=ALGO_COLORS[2], linewidth=2, markersize=7, zorder=3)
    for i, v in enumerate(mems):
        ax.annotate(f"{v:.1f}", (x_labels[i], mems[i]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7)

    ax.set_title(f"Memory Footprint (KB)", fontsize=12, fontweight="bold")
    ax.set_ylabel("KB")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    ax.grid(linestyle="--", alpha=0.4)

# ---------------------------------------------------------------------------
# TH: 1 INPUT - ALL SOLVER
# ---------------------------------------------------------------------------

# Time per ALGORITHM
def _draw_time_per_algo(ax, algos, results):
    r      = results[0]
    times  = [r["algorithms"].get(a, {}).get("time_ms") or 0 for a in algos]
    colors = ALGO_COLORS[:len(algos)]
    bars   = ax.bar(algos, times, color=colors, alpha=0.85, zorder=3)
    ax.bar_label(bars, fmt="%.1f", fontsize=7, padding=3)
    ax.set_title("Execution Time (ms)", fontsize=12, fontweight="bold")
    ax.set_ylabel("ms")
    ax.set_yscale("log")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    ax.grid(axis="y", alpha=0.3)


# Inferences per ALGORITHM
def _draw_inferences_per_algo(ax, algos, results):
    r    = results[0]
    infs = [r["algorithms"].get(a, {}).get("inferences") or 0 for a in algos]
    colors = ALGO_COLORS[:len(algos)]
    bars   = ax.bar(algos, infs, color=colors, alpha=0.85, zorder=3)
    ax.bar_label(bars, fmt="%d", fontsize=7, padding=3)
    ax.set_title("Inference Count by Algorithm", fontsize=12, fontweight="bold")
    ax.set_ylabel("Inferences")
    ax.set_yscale("log")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    ax.grid(axis="y", alpha=0.3)


# Steps comparison (radar-like horizontal bar)
def _draw_steps_per_algo(ax, algos, results):
    r      = results[0]
    y_vals = []
    colors = []
    for algo in algos:
        ar         = r["algorithms"].get(algo, {})
        steps_data = ar.get("steps", [])
        count      = len(steps_data) if isinstance(steps_data, list) else int(steps_data or 0)
        y_vals.append(count)
        st = _get_status(ar)
        colors.append("#27ae60" if st == STATUS_SOLVED else "#e67e22")

    bars = ax.barh(algos, y_vals, color=colors, alpha=0.85, zorder=3)
    ax.bar_label(bars, fmt="%d", fontsize=8, padding=4)
    ax.set_title("Step Count by Algorithm", fontsize=12, fontweight="bold")
    ax.set_xlabel("Steps")
    ax.set_xscale("log")
    ax.invert_yaxis()

    # Legend thủ công
    handles = [
        mpatches.Patch(color="#27ae60", label="Solved"),
        mpatches.Patch(color="#e67e22", label="Not solved"),
    ]
    ax.legend(handles=handles, fontsize=8, loc="center right")
    ax.grid(axis="x", linestyle="--", alpha=0.5, zorder=0)


# Memory per algorithm (bar)
def _draw_memory_per_algo(ax, algos, results):
    r      = results[0]
    mems   = [r["algorithms"].get(a, {}).get("memory_kb") or 0 for a in algos]
    colors = ALGO_COLORS[:len(algos)]
    bars   = ax.bar(algos, mems, color=colors, alpha=0.85, zorder=3)
    ax.bar_label(bars, fmt="%.1f", fontsize=7, padding=3)
    ax.set_title("Memory Usage (KB)", fontsize=12, fontweight="bold")
    ax.set_ylabel("KB")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    ax.set_yscale("log")
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)

# ---------------------------------------------------------------------------
# Main draw function
# ---------------------------------------------------------------------------

# ALL INPUT - 1 SOLVER: thẻ tóm tắt thay cho bảng
def _draw_summary_card_1solver(ax, algo, results):
    ax.axis("off")
    total = len(results)
    solved = unsolvable = timeout = step_limit = 0
    for r in results:
        st = _get_status(r["algorithms"].get(algo, {}))
        if st == STATUS_SOLVED:       solved     += 1
        elif st == STATUS_UNSOLVABLE: unsolvable += 1
        elif st == STATUS_TIMEOUT:    timeout    += 1
        elif st == STATUS_STEP_LIMIT: step_limit += 1

    text = (
        f"Succeed rate: {solved}/{total}\n\n"
        f"  Solved input(s)      : {solved}\n"
        f"  Unsolvable input(s)  : {unsolvable}\n"
        f"  Timeout input(s)     : {timeout}\n"
        f"  Step-limit input(s)  : {step_limit}"
    )
    ax.set_title(f"Summary — Algorithm: {algo}", fontsize=15, fontweight="bold", pad=22)
    ax.text(0.5, 0.40, text, ha="center", va="center",
            fontsize=14, fontweight="bold", fontfamily="monospace",
            transform=ax.transAxes,
            bbox=dict(boxstyle="round,pad=1.2", facecolor="#f8f9fa",
                      edgecolor="#bdc3c7", linewidth=1.5))

# 1 INPUT - ALL SOLVER: thẻ tóm tắt thay cho bảng
def _draw_summary_card_allsolver(ax, algos, results):
    ax.axis("off")
    inp  = results[0]["input_id"]
    size = results[0]["size"]
    total = len(algos)
    solved = unsolvable = timeout = step_limit = 0
    for algo in algos:
        st = _get_status(results[0]["algorithms"].get(algo, {}))
        if st == STATUS_SOLVED:       solved     += 1
        elif st == STATUS_UNSOLVABLE: unsolvable += 1
        elif st == STATUS_TIMEOUT:    timeout    += 1
        elif st == STATUS_STEP_LIMIT: step_limit += 1

    text = (
        f"Difficulty: {solved}/{total} solver(s) solved\n\n"
        f"  Solved      : {solved}/{total} algorithm(s)\n"
        f"  Unsolvable  : {unsolvable}/{total} algorithm(s)\n"
        f"  Timeout     : {timeout}/{total} algorithm(s)\n"
        f"  Step-limit  : {step_limit}/{total} algorithm(s)"
    )
    ax.set_title(f"Summary — Input: {inp}  ({size}×{size})", fontsize=15,
                 fontweight="bold", pad=22)
    ax.text(0.5, 0.40, text, ha="center", va="center",
            fontsize=14, fontweight="bold", fontfamily="monospace",
            transform=ax.transAxes,
            bbox=dict(boxstyle="round,pad=1.2", facecolor="#f8f9fa",
                      edgecolor="#bdc3c7", linewidth=1.5))
    
def show(run_mode: str = "all_all", save: bool = True):
    outputs = load_all_outputs()
    algos, results, sizes = extract(outputs, run_mode)

    if not results:
        print("No results found in log.json.")
        return

    fig = plt.figure(figsize=(20, 22))
    from datetime import datetime
    fig.suptitle(
        f"Futoshiki Solver - Comparison Report\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
        f"Inputs: {len(results)}",
        fontsize=14, fontweight="bold", y=0.98
    )

    gs = GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.3)

    ax_tl = fig.add_subplot(gs[1, 0])
    ax_tr = fig.add_subplot(gs[1, 1])
    ax_bl = fig.add_subplot(gs[2, 0])
    ax_br = fig.add_subplot(gs[2, 1])

    # Vẽ chart tùy mode
    if run_mode == "all_input":
        ax_top = fig.add_subplot(gs[0, :])
        _draw_summary_card_1solver(ax_top, algos[0], results)
        _draw_time_line(ax_tl, algos, results)
        _draw_inferences_line(ax_tr, algos, results)
        _draw_time_by_size(ax_bl, algos, results)
        _draw_memory_line(ax_br, algos, results)

    elif run_mode == "all_solver":
        ax_top = fig.add_subplot(gs[0, :])
        _draw_summary_card_allsolver(ax_top, algos, results)
        _draw_time_per_algo(ax_tl, algos, results)
        _draw_inferences_per_algo(ax_tr, algos, results)
        _draw_steps_per_algo(ax_bl, algos, results)
        _draw_memory_per_algo(ax_br, algos, results)

    else:           # all_all
        ax_high_l  = fig.add_subplot(gs[0, 0])
        ax_high_r = fig.add_subplot(gs[0, 1])
        _draw_status_chart(ax_high_l, algos, results)
        _draw_steps_all_all(ax_high_r, algos, results)
        _draw_time_chart(ax_tl, algos, results)
        _draw_inference_chart(ax_tr, algos, results)
        _draw_time_by_size(ax_bl, algos, results)
        _draw_memory_chart(ax_br, algos, results)

    if save:
        plt.savefig(OUTPUT_IMG, dpi=150, bbox_inches="tight")
        print(f"Chart saved to: {OUTPUT_IMG}")

    plt.get_current_fig_manager().window.showMaximized()
    plt.show()
    return fig


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        show()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)