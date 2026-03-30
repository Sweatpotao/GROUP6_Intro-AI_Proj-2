# General limits
MAX_STEPS = 10_000
TIME_LIM = 10

# Trạng thái sau khi giải xong
STATUS_UNSOLVABLE = 0   # Không giải được
STATUS_SOLVED = 1       # Giải được
STATUS_TIMEOUT = 2      # Time-out
STATUS_STEP_LIMIT = 3   # Step limit

# Action codes for steps[]
ACTION_GIVEN = 0        # ô cho sẵn
ACTION_ASSIGN = 1       # gán giá trị
ACTION_BACKTRACK = 2    # quay lui / xóa

# Kích thước game Futoshiki
VALID_SIZES = [4, 5, 6, 7, 9]

# Phân bổ input theo size đối với 10 inputs (Mặc định phân bổ đều, có thể chỉnh sửa)
INPUT_DISTRIBUTION = {
    4: 2,
    5: 2,
    6: 2,
    7: 2,
    9: 2,
}  # x2 nếu chọn 20 inputs