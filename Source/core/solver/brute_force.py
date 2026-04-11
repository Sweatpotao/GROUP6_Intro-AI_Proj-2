from core.config import ACTION_ASSIGN, ACTION_BACKTRACK
from core.solver.base_solver import BaseSolver


class BruteForceSolver(BaseSolver):
    """
    Smart Brute Force solver (Generate and Test với Pre-pruned Domain).

    Cách hoạt động (Khác biệt hoàn toàn với Backtracking):
    - THU HẸP DOMAIN: Lọc các ứng viên vô lý NGAY TỪ ĐẦU, chỉ dựa trên các ô GIVEN (cố định).
    - GENERATE: Thử mù quáng các tổ hợp có thể dựa trên tập ứng viên đã thu hẹp. KHÔNG check constraint giữa chừng với các ô do thuật toán tự điền.
    - TEST: CHỈ check_all_constraints() ĐÚNG 1 LẦN khi điền kín toàn bộ bảng.
    """

    def __init__(self, puzzle: dict):
        super().__init__(puzzle)
        self._empty_cells_data = []

    def _solve(self) -> bool:
        # Tiền xử lý: Thu hẹp phạm vi tìm kiếm 1 LẦN DUY NHẤT dựa trên các ô GIVEN
        processed_cells = []
        for i in range(self.n):
            for j in range(self.n):
                if self.puzzle["grid"][i][j] == 0:
                    candidates = self._get_initial_candidates(i, j)
                    
                    # Nếu có ô trống mà tập ứng viên rỗng (do mâu thuẫn đề bài) -> Vô nghiệm ngay
                    if not candidates:
                        return False
                        
                    processed_cells.append({
                        "pos": (i, j),
                        "candidates": candidates,
                        "count": len(candidates)
                    })

        # Sắp xếp ô có ít ứng viên nhất lên đầu để giảm số nhánh sinh tổ hợp (Heuristic)
        processed_cells.sort(key=lambda x: x["count"])
        
        self._empty_cells_data = processed_cells
        return self._brute_optimized(0)

    def _get_initial_candidates(self, r, c):
        candidates = []
        for v in range(1, self.n + 1):
            # Chỉ check với các ô GIVEN tĩnh
            if self.is_safe_with_given_cells(r, c, v):
                candidates.append(v)
        return candidates
    
    def is_safe_with_given_cells(self, row, col, val):
        # LƯU Ý CỐT LÕI: Dùng self.puzzle["grid"] (bản gốc), tuyệt đối KHÔNG dùng self.grid.
        # Điều này đảm bảo ta không vô tình check với các số đang được đệ quy điền tạm thời.
        g = self.puzzle["grid"]
        
        # Check hàng với GIVEN
        for j in range(self.n):
            if g[row][j] == val:
                return False

        # Check cột với GIVEN
        for i in range(self.n):
            if g[i][col] == val:
                return False

        # Check inequality với GIVEN
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        # Trái
        if col > 0 and g[row][col - 1] != 0:
            c = hc[row][col - 1]
            if c == 1 and not (g[row][col - 1] < val):
                return False
            if c == -1 and not (g[row][col - 1] > val):
                return False

        # Phải
        if col < self.n - 1 and g[row][col + 1] != 0:
            c = hc[row][col]
            if c == 1 and not (val < g[row][col + 1]):
                return False
            if c == -1 and not (val > g[row][col + 1]):
                return False

        # Trên
        if row > 0 and g[row - 1][col] != 0:
            c = vc[row - 1][col]
            if c == 1 and not (g[row - 1][col] < val):
                return False
            if c == -1 and not (g[row - 1][col] > val):
                return False

        # Dưới
        if row < self.n - 1 and g[row + 1][col] != 0:
            c = vc[row][col]
            if c == 1 and not (val < g[row + 1][col]):
                return False
            if c == -1 and not (val > g[row + 1][col]):
                return False

        return True
    
    def _brute_optimized(self, idx: int) -> bool:
        # Ngắt sớm nếu vượt giới hạn bước hoặc bị stop từ UI
        if self.should_stop():
            return False

        # ĐIỀU KIỆN DỪNG: Nếu đã gán hết ô trống → mới bắt đầu TEST kiểm tra toàn bộ
        if idx == len(self._empty_cells_data):
            return self.check_all_constraints()

        cell = self._empty_cells_data[idx]
        row, col = cell["pos"]
        candidates = cell["candidates"]

        # GENERATE: Chỉ sinh các trạng thái nằm trong domain đã thu hẹp
        for val in candidates:
            self.grid[row][col] = val
            self.record_step(row, col, val, ACTION_ASSIGN)

            if self._brute_optimized(idx + 1):
                return True

            self.grid[row][col] = 0
            self.record_step(row, col, 0, ACTION_BACKTRACK)

        return False