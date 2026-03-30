import os
import sys
import json
import matplotlib
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


def extract(outputs: list) -> tuple:
    """
    Trích xuất dữ liệu từ list output dicts.

    Returns:
        algos   : list tên algorithm (lấy từ file đầu tiên)
        results : list of dict per input (chuẩn hóa từ output_XX.json)
        sizes   : list of int (puzzle size)
    """
    if not outputs:
        return [], [], []

    # Lấy danh sách algorithm từ file đầu tiên có data
    algos = []
    for out in outputs:
        keys = list(out.get("algorithms", {}).keys())
        if keys:
            algos = keys
            break

    # Chuẩn hóa về cùng format với log.json cũ
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

def _draw_table(ax, algos, results):
    ax.axis("off")
    ax.set_title("Summary Table", fontsize=13, fontweight="bold", pad=10)

    # Header
    col_labels = ["Input", "Size"] + algos
    n_cols     = len(col_labels)
    n_rows     = len(results)

    table_data = []
    cell_colors = []

    for r in results:
        row    = [r["input_id"], f"{r['size']}x{r['size']}"]
        colors = ["#f0f0f0", "#f0f0f0"]
        for algo in algos:
            ar     = r["algorithms"].get(algo, {})
            status = _get_status(ar)
            label  = STATUS_LABEL.get(status, "N/A")
            row.append(label)
            colors.append(STATUS_COLOR.get(status, "#bdc3c7") + "88")
        table_data.append(row)
        cell_colors.append(colors)

    table = ax.table(
        cellText    = table_data,
        colLabels   = col_labels,
        cellColours = cell_colors,
        loc         = "center",
        cellLoc     = "center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.4)

    # Style header
    for j in range(n_cols):
        table[0, j].set_facecolor("#2c3e50")
        table[0, j].set_text_props(color="white", fontweight="bold")


# ---------------------------------------------------------------------------
# Biểu đồ thời gian
# ---------------------------------------------------------------------------

def _draw_time_chart(ax, algos, results):
    ax.set_title("Time (ms) per puzzle", fontsize=12, fontweight="bold")

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


# ---------------------------------------------------------------------------
# Biểu đồ inferences
# ---------------------------------------------------------------------------

def _draw_inference_chart(ax, algos, results):
    ax.set_title("Inferences per puzzle", fontsize=12, fontweight="bold")

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


# ---------------------------------------------------------------------------
# Biểu đồ thời gian theo size (line chart)
# ---------------------------------------------------------------------------

def _draw_time_by_size(ax, algos, results):
    ax.set_title("Avg time (ms) by puzzle size", fontsize=12, fontweight="bold")

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


# ---------------------------------------------------------------------------
# Biểu đồ status (stacked bar)
# ---------------------------------------------------------------------------

def _draw_status_chart(ax, algos, results):
    ax.set_title("Status count per algorithm", fontsize=12, fontweight="bold")

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


# ---------------------------------------------------------------------------
# Main draw function
# ---------------------------------------------------------------------------

def show(save: bool = True):
    outputs = load_all_outputs()
    algos, results, sizes = extract(outputs)

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

    # Bảng tổng hợp - chiếm cả hàng đầu
    ax_table = fig.add_subplot(gs[0, :])
    _draw_table(ax_table, algos, results)

    # Biểu đồ thời gian
    ax_time = fig.add_subplot(gs[1, 0])
    _draw_time_chart(ax_time, algos, results)

    # Biểu đồ inferences
    ax_inf = fig.add_subplot(gs[1, 1])
    _draw_inference_chart(ax_inf, algos, results)

    # Line chart theo size
    ax_size = fig.add_subplot(gs[2, 0])
    _draw_time_by_size(ax_size, algos, results)

    # Status stacked bar
    ax_status = fig.add_subplot(gs[2, 1])
    _draw_status_chart(ax_status, algos, results)

    if save:
        plt.savefig(OUTPUT_IMG, dpi=150, bbox_inches="tight")
        print(f"Chart saved to: {OUTPUT_IMG}")

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