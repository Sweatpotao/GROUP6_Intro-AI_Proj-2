# Hiển thị lưới đã giải với các ràng buộc
def format_grid(puzzle: dict, solution: list[list[int]]) -> str:
    n = puzzle["size"]
    hc = puzzle["h_constraints"]
    vc = puzzle["v_constraints"]

    # Độ rộng tối đa của số (để căn chỉnh)
    w = max(len(str(x)) for row in solution for x in row)

    lines = []
    for i in range(n):
        # Hàng số
        row_str = ""
        for j in range(n):
            row_str += f"{solution[i][j]:>{w}}"
            if j < n - 1:
                c = hc[i][j]
                if c == 1:
                    row_str += " < "
                elif c == -1:
                    row_str += " > "
                else:
                    row_str += "   "  # ba dấu cách để giữ khoảng cách
        lines.append(row_str)

        # Hàng ký hiệu dọc
        if i < n - 1:
            v_row_str = ""
            for j in range(n):
                c = vc[i][j]
                if c == 1:
                    v_row_str += "∧".rjust(w)
                elif c == -1:
                    v_row_str += "V".rjust(w)
                else:
                    v_row_str += " " * w
                if j < n - 1:
                    v_row_str += "   "  # ba dấu cách tương ứng với khoảng cách giữa các số
            lines.append(v_row_str)

    return "\n".join(lines)

def format_puzzle(puzzle: dict) -> str:
    # Hiển thị puzzle chưa giải (0 : ô trống, hiển thị là '_')
    return format_grid(puzzle, [
        [v if v != 0 else 0 for v in row]
        for row in puzzle["grid"]
    ]).replace("  0  ", "  _  ").replace(" 0 ", " _ ").replace("0", "_")

def print_separator(char: str = "-", width: int = 50):
    print(char * width)