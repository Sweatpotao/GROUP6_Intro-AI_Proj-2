# Project 02 - Futoshiki Solver
### CSC14003 - Fundamentals of Artificial Intelligence

Solving Futoshiki puzzles using First-Order Logic & Inference Algorithms.

---

## Requirements

**Python 3.7+**

Install dependencies:
```bash
pip install -r requirements.txt
```

`requirements.txt` contains:
```
matplotlib
PyQt5
```

---

## Project Structure

```
Source/
|
|-- core/                        Logic layer (no UI dependency)
|   |-- config.py                Global constants (MAX_STEPS, TIME_LIM, ...)
|   |-- parser.py                Read input JSON -> dict
|   |-- formatter.py             Format grid -> string for display
|   |-- logger.py                Read/write output JSON & log JSON
|   |-- cnf_generator.py         Generate KB/CNF from FOL axioms
|   |-- cnf_dialog.py            CNF Knowledge Base dialog (used by app.py)
|   |
|   +-- solver/
|       |-- base_solver.py       Abstract base class for all solvers
|       |-- forward_chaining.py  Forward chaining (Modus Ponens propagation)
|       |-- backward_chaining.py Backward chaining (SLD resolution, Prolog-style)
|       |-- astar_base.py        A* abstract base class (shared framework for H1/H2/H3)
|       |-- astar_h1.py          A* search - H1: cell count heuristic
|       |-- astar_h2.py          A* search - H2: constrained cell heuristic
|       |-- astar_h3.py          A* search - H3: AC-3 arc consistency
|       |-- backtracking.py      Backtracking with constraint pruning
|       |-- brute_force_opt.py   Brute force (used by app.py)
|       +-- brute_force.py       Brute force (no pruning, baseline)
|
|-- main.py                      Console: run all solvers -> output + log
|-- generate_input.py            Console: generate 5/10/20/30 input files
|-- visualize_stats.py           Matplotlib: read outputs -> charts & table
|-- app.py                       PyQt5 UI: control panel for all features
|-- frontend.css                 Stylesheet for app.py
|
|-- Inputs/
|   |-- input_01.json            Sample input (4x4)
|   +-- ...
|
|-- Outputs/
|   |-- output_01.json           Full result with steps[] for visualization
|   |-- ...
|   +-- log.json                 Summary (no steps[])
|
|-- requirements.txt
|-- README.md
+-- .gitignore
```

---

## Input Format (`input_XX.json`)

```json
{
  "id":            "input_01",
  "size":          4,
  "grid": [
    [0, 2, 0, 4],
    [0, 0, 3, 0],
    [0, 0, 0, 0],
    [2, 1, 4, 0]
  ],
  "h_constraints": [
    [-1, 0,  0],
    [ 1,-1, -1],
    [ 0, 0,  0],
    [ 0, 1, -1]
  ],
  "v_constraints": [
    [ 0, 1,  0, -1],
    [ 0,-1, -1,  0],
    [-1, 0,  0,  1]
  ],
  "answer": [
    [3, 2, 1, 4],
    [1, 4, 3, 2],
    [4, 3, 2, 1],
    [2, 1, 4, 3]
  ]
}
```

| Field | Description |
|---|---|
| `grid` | N x N — `0` = empty, `1..N` = pre-filled |
| `h_constraints` | N x (N-1) — `1` = `<` (left < right), `-1` = `>` (left > right), `0` = none |
| `v_constraints` | (N-1) x N — `1` = `<` (top < bottom), `-1` = `>` (top > bottom), `0` = none |
| `answer` | Known valid solution (used for verification, not exposed to solvers) |

---

## Output Format (`output_XX.json`)

```json
{
  "input_id":  "input_01",
  "size":      4,
  "solution":  [[...], ...],
  "algorithms": {
    "forward_chaining": {
      "status":     1,
      "solution":   [[...], ...],
      "time_ms":    2.097,
      "memory_kb":  13.3,
      "inferences": 9,
      "steps":      [[row, col, val, action], ...]
    },
    ...
  }
}
```

| Field | Value |
|---|---|
| `solution` | `null` if no solver found a solution |
| `status` | `0`=Unsolvable, `1`=Solved, `2`=Timeout, `3`=StepLimit |
| `steps` | action: `0`=given, `1`=assign, `2`=backtrack |

> `steps[]` is capped at `MAX_STEPS` (default: 10,000). `steps = null` when status = Timeout.

---

## How to Run

### Step 1 — Generate inputs
> Skip if `Inputs/` already has files.

```bash
python generate_input.py
```

- Choose **5, 10, 20, or 30** inputs.
- Sizes: 4x4, 5x5, 6x6, 7x7, 9x9 (distributed evenly).
- Old input and output files are automatically cleaned up before generation.
- Each puzzle is verified to have a **unique solution** before saving.

---

### Step 2A — Run via console
```bash
python main.py
```

- Outputs saved to: `Outputs/output_XX.json`
- Summary saved to: `Outputs/log.json`
- Timeout per solver: **10 seconds** (configurable in `core/config.py`)

---

### Step 2B — Run via UI
```bash
python app.py
```

**Toolbar controls:**

| Control | Description |
|---|---|
| **Puzzle** dropdown | Select a specific puzzle or **ALL INPUT** to run all |
| **Algo** dropdown | Select a specific algorithm or **ALL SOLVER** to run all |
| **CNF for Puzzle** | Show Knowledge Base summary and verify the current grid against CNF axioms |
| **Reset Map** | Reset the grid to its original unsolved state |
| **Show Result** | Hold to preview the known answer (orange); release to hide |
| **Solve** | Run the selected solver(s) in a background thread |
| **View Full Stats** | Open comparison charts — enabled after a full run completes |

**Run modes (controlled by Puzzle + Algo dropdowns):**

| Puzzle | Algo | Mode | Description |
|---|---|---|---|
| Specific | Specific | Single | Run one solver on one puzzle |
| ALL INPUT | Specific | Batch | Run one solver across all puzzles sequentially |
| Specific | ALL SOLVER | Batch | Run all solvers on one puzzle |
| ALL INPUT | ALL SOLVER | Full benchmark | Equivalent to running `main.py` — runs everything |

> Batch and full-benchmark modes automatically clear old output files before starting and enable **View Full Stats** when complete.

**Visualization Controls (right panel):**

| Control | Description |
|---|---|
| Step list | Click any step to jump to that point in the solution trace |
| **Run / End** | Auto-play the step trace at the configured speed |
| **Stop / Resume** | Pause and resume auto-play |
| Speed slider | Adjust playback speed from 3 to 200 steps/second |

---

### Step 3 — View comparison charts
> After running `main.py`.

```bash
python visualize_stats.py
```

Reads all `output_XX.json` files. Saves chart to `Outputs/comparison.png`.

Charts included:
- Summary table (status per algorithm per puzzle)
- Time (ms) per puzzle — log scale bar chart
- Inferences per puzzle — log scale bar chart
- Average time by puzzle size — line chart
- Status count per algorithm — stacked bar chart

---

## Algorithms

| # | Algorithm | Description |
|---|---|---|
| 1 | **Forward Chaining** | Starts from known facts, propagates via Modus Ponens, falls back to MRV search |
| 2 | **Backward Chaining** | SLD resolution (Prolog-style), proves `Val(i,j,?)` using Horn clauses |
| 3 | **A\* H1** | `h(n)` = number of unassigned cells — admissible, weakest |
| 4 | **A\* H2** | `h(n)` = unassigned + constrained_unassigned / 2 — admissible, stronger |
| 5 | **A\* H3** | `h(n)` = cells with domain > 1 after AC-3 — strongest, highest cost per node |
| 6 | **Backtracking** | DFS with per-step constraint checking (pruning) |
| 7 | **Brute Force** | Tries all combinations, checks constraints only after full assignment — baseline |
| 8 | **Brute Force Opt** | Pre-prunes domain from given clues, then generates combinations — faster baseline |

---

## Configuration (`core/config.py`)

```python
MAX_STEPS  = 10_000   # Max steps stored per solver (caps memory usage)
TIME_LIM   = 10       # Timeout per solver in seconds

STATUS_UNSOLVABLE = 0
STATUS_SOLVED     = 1
STATUS_TIMEOUT    = 2
STATUS_STEP_LIMIT = 3

VALID_SIZES = [4, 5, 6, 7, 9]
```

---

## Notes

- Brute force on puzzles >= 5x5 will almost always hit `TIME_LIM`.
- A* H3 is theoretically optimal but slower than H2 on large puzzles due to the overhead of running AC-3 at every node expansion.
- `steps[]` in output files can be replayed in `app.py` (Show Result / Visualize).
- `Inputs/` and `Outputs/` (except sample files) are excluded from git via `.gitignore`.
- `generate_input.py` guarantees **unique solution** for every generated puzzle (verified by a backtracking solver limited to 2 solutions).