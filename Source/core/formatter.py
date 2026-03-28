def format_grid(puzzle: dict, solution: list[list[int]]) -> str:
    # Hiển thị lưới đã giải với các ràng buộc (>, <)
    # Vd: output (4 x 4):
    #     2 < 3   4   1
    #     v
    #     1   2 > 3   4
    #     ^
    #     4   1   2   3
    #     ^
    #     3   4   1 < 2

    n = puzzle["size"]
    hc = puzzle["h_constraints"]
    vc = puzzle["v_constraints"]
    lines = []

    for i in range(n):
        # Hàng số & ký hiệu ngang
        row_parts = []
        for j in range(n):
            row_parts.append(str(solution[i][j]))
            if j < n - 1:
                c = hc[i][j]
                if c == 1:
                    row_parts.append("<")
                elif c == -1:
                    row_parts.append(">")
                else:
                    row_parts.append(" ")
        lines.append("  ".join(row_parts))

        # Hàng ký hiệu dọc
        if i < n - 1:
            vc_row = []
            for j in range(n):
                c = vc[i][j]
                if c == 1:
                    vc_row.append("^")
                elif c == -1:
                    vc_row.append("v")
                else:
                    vc_row.append(" ")
            lines.append("  ".join(vc_row))

    return "\n".join(lines)

def format_puzzle(puzzle: dict) -> str:
    # Hiển thị puzzle chưa giải (0 : ô trống, hiển thị là '_')
    return format_grid(puzzle, [
        [v if v != 0 else 0 for v in row]
        for row in puzzle["grid"]
    ]).replace("  0  ", "  _  ").replace(" 0 ", " _ ").replace("0", "_")


# Hiển thị stats của 1 thuật toán sau khi chạy
def format_stats(algo_name: str, result: dict) -> str:
    # Status: 1=Solved, 0=Unsolvable, 2=Timeout, 3=Step limit, None=Skipped
    
    status = result.get("status")
    status_map = {
        0:    "Unsolvable",
        1:    "Solved",
        2:    "Timeout",
        3:    "Step limit",
    }
    label = status_map.get(status, "Unknown")
 
    t   = f'{result["time_ms"]:.2f} ms'   if result.get("time_ms")    is not None else "N/A"
    mem = f'{result["memory_kb"]:.1f} KB'  if result.get("memory_kb")  is not None else "N/A"
    inf = str(result["inferences"])           if result.get("inferences") is not None else "N/A"
    steps = str(len(result.get("steps") or [])) if result.get("steps") is not None else "N/A"
 
    return (
        f"  [{algo_name}] {label}\n"
        f"    Time      : {t}\n"
        f"    Memory    : {mem}\n"
        f"    Inferences: {inf}\n"
        f"    Steps saved: {steps}"
    )


def print_separator(char: str = "-", width: int = 50):
    print(char * width)