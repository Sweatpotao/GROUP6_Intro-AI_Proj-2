import json
import os
import re
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "Outputs")
LOG_FILE   = os.path.join(OUTPUT_DIR, "log.json")

# Format cho file json
def _compact_json(data) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    def compress(match):
        items = re.findall(r'-?[0-9]+', match.group(0))
        return '[' + ', '.join(items) + ']'
    raw = re.sub(r'\[[^\[\]]*?\]', compress, raw, flags=re.DOTALL)
    return raw

def save_output(input_id: str, size: int, solution, algorithms: dict):
    # Ghi output_XX.json
    # Params:
    #     input_id   : "input_01"
    #     size       : N
    #     solution   : list[list[int]] hoặc None nếu không giải được
    #     algorithms : dict tên -> result dict (có steps[])

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    number = input_id.replace("input_", "")
    filepath = os.path.join(OUTPUT_DIR, f"output_{number}.json")

    data = {
        "input_id":   input_id,
        "size":       size,
        "solution":   solution,
        "algorithms": algorithms,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(_compact_json(data))

    return filepath


def rebuild_log():
    # Đọc tất cả output_XX.json -> gộp thành log.json, bỏ steps[]
    # Ghi đè log.json mỗi lần gọi
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_files = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.startswith("output_") and f.endswith(".json")
    ])

    results = []
    for fname in output_files:
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Strip steps[] khỏi mỗi algorithm
        stripped_algos = {}
        for algo_name, algo_result in data.get("algorithms", {}).items():
            stripped = {k: v for k, v in algo_result.items() if k != "steps"}
            stripped_algos[algo_name] = stripped

        results.append({
            "input_id":   data["input_id"],
            "size":       data["size"],
            "algorithms": stripped_algos,
        })

    log_data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_inputs": len(results),
        "algorithms":   _list_algorithms(results),
        "results":      results,
    }

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(_compact_json(log_data))

    return LOG_FILE


def load_log() -> dict:
    # Đọc log.json. Raise nếu chưa có
    if not os.path.exists(LOG_FILE):
        raise FileNotFoundError(
            "Error: log.json missing. Run main.py to initialize data."
        )
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_output(input_id: str) -> dict:
    # Đọc output_XX.json theo input_id (có steps[])
    number = input_id.replace("input_", "")
    filepath = os.path.join(OUTPUT_DIR, f"output_{number}.json")

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Cannot find: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def list_outputs() -> list[str]:
    # Trả về danh sách input_id có output, vd: ["input_01", "input_02"]
    files = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.startswith("output_") and f.endswith(".json")
    ])
    return [f.replace("output_", "input_").replace(".json", "") for f in files]


def _list_algorithms(results: list) -> list[str]:
    """Lấy danh sách tên algorithm từ results."""
    if not results:
        return []
    return list(results[0].get("algorithms", {}).keys())