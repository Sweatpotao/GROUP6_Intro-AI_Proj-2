from core.solver.astar_base import AStarBase


class AStarH2(AStarBase):
    """
    A* với heuristic H2: Ưu tiên các trạng thái có nhiều ô trống mang ràng buộc bất đẳng thức.

    Công thức: 
        h(n) = (U + C) // 2
    Trong đó:
        U (unassigned): tổng số ô chưa gán.
        C (constrained_unassigned): số ô chưa gán nằm trong các chuỗi ràng buộc.

    Admissible vì:
        1. Gọi h*(n) là chi phí thực tế để giải xong (số ô trống còn lại). 
           Ta luôn có h*(n) = U.
        2. Vì C luôn nhỏ hơn hoặc bằng U (một ô có ràng buộc thì chắc chắn là ô trống),
           nên: h(n) = (U + C) / 2 <= (U + U) / 2 = U.
        3. Vậy h(n) <= h*(n). Heuristic này hoàn toàn admissible.

    So với H1:
        - H1 chỉ đếm đơn thuần số ô chưa gán (h1 = U).
        - H2 phân biệt được các trạng thái có cùng số ô trống: 
          + Trạng thái nào có nhiều ô mang ràng buộc (khó giải hơn) sẽ có giá trị f(n) cao hơn.
          + Giúp A* có "độ dốc" để ưu tiên mở rộng các nhánh "ít ràng buộc" & dễ kiểm soát trước,
            tránh sa lầy vào các vùng vi phạm logic phức tạp ngay từ đầu.
    """

    def _heuristic(self, grid: list) -> int:
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]
        n = self.n

        unassigned = 0
        
        # Dùng set lưu tọa độ các ô trống có liên quan đến ràng buộc (C).
        # Cách này khắc phục lỗi đếm trùng khi 1 ô nằm ở giao điểm của nhiều bất đẳng thức
        cells_in_chains = set()

        # Đếm tổng số ô chưa gán (U)
        for i in range(n):
            for j in range(n):
                if grid[i][j] == 0:
                    unassigned += 1

        # Quét các chuỗi ràng buộc ngang
        for i in range(n):
            for j in range(n - 1):
                if hc[i][j] != 0:
                    # Nếu ràng buộc này chứa ô trống -> chưa được thỏa mãn
                    if grid[i][j] == 0 or grid[i][j+1] == 0:
                        if grid[i][j] == 0:   
                            cells_in_chains.add((i, j))
                        if grid[i][j+1] == 0: 
                            cells_in_chains.add((i, j+1))

        # Quét các chuỗi ràng buộc dọc
        for i in range(n - 1):
            for j in range(n):
                if vc[i][j] != 0:
                    # Nếu ràng buộc này chứa ô trống -> chưa được thỏa mãn
                    if grid[i][j] == 0 or grid[i+1][j] == 0:
                        if grid[i][j] == 0:   
                            cells_in_chains.add((i, j))
                        if grid[i+1][j] == 0: 
                            cells_in_chains.add((i+1, j))

        constrained_unassigned = len(cells_in_chains)

        # Trả về giá trị trung bình <= unassigned (Bảo toàn Admissible)
        return (unassigned + constrained_unassigned) // 2