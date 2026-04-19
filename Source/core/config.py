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

# Puzzle size
VALID_SIZES = [4, 5, 6, 7, 9]

# Lượng inputs
VALID_COUNTS = [5, 10, 20, 30]

# Path
import os
BASE_DIR   = os.path.dirname(os.path.dirname(__file__)) # Trỏ về Source
INPUT_DIR  = os.path.join(BASE_DIR, "Inputs")
OUTPUT_DIR = os.path.join(BASE_DIR, "Outputs")

# Tỉ lệ ô given - constraint so với tổng số ô, theo size
GIVEN_RATIO = {
    4: 0.20,
    5: 0.25,
    6: 0.30,
    7: 0.35,
    9: 0.35,
}
CONSTRAINT_RATIO = {
    4: 0.20,
    5: 0.25,
    6: 0.30,
    7: 0.35,
    9: 0.35,
}