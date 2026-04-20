from core.solver.astar_base import AStarBase


class AStarH2(AStarBase):
    """
    A* với heuristic H2: ưu tiên các ô chưa gán có liên quan đến inequality constraint.

    Công thức:
        h(n) = unassigned + constrained_unassigned // 2

        Trong đó:
            unassigned            = số ô chưa được gán giá trị
            constrained_unassigned = số ô chưa gán có ít nhất 1 inequality constraint

    Tính chất:
        H2 là heuristic KHÔNG admissible (inadmissible by design).
        Vì constrained_unassigned <= unassigned, nên:
            h(n) <= unassigned + unassigned // 2 = 1.5 * unassigned
        Chi phí thực tế = unassigned (mỗi ô cần đúng 1 lần gán).
        Khi constrained_unassigned >= 2, h(n) > chi phí thực -> overestimate -> không admissible.

    Mục đích:
        Phần constrained_unassigned // 2 là bonus phạt cho các ô có constraints,
        khiến A* ưu tiên xử lý các vùng nhiều ràng buộc trước.
        Dù không đảm bảo optimal path, trong thực nghiệm H2 mở rộng ít node hơn H1
        và thường nhanh hơn H3 vì không cần chạy AC-3 mỗi bước.

    So sánh với H1 và H3:
        H1: admissible, yếu nhất — chỉ đếm ô trống
        H2: inadmissible, cân bằng tốt giữa tốc độ và hiệu quả tìm kiếm
        H3: admissible, mạnh nhất — dùng AC-3, tốn chi phí tính toán cao hơn
    """

    def _heuristic(self, grid: list) -> int:
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        unassigned             = 0
        constrained_unassigned = 0

        for i in range(self.n):
            for j in range(self.n):
                if grid[i][j] == 0:
                    unassigned += 1

                    has_constraint = (
                        (j > 0          and hc[i][j-1] != 0) or
                        (j < self.n-1   and hc[i][j]   != 0) or
                        (i > 0          and vc[i-1][j]  != 0) or
                        (i < self.n-1   and vc[i][j]    != 0)
                    )

                    if has_constraint:
                        constrained_unassigned += 1

        return unassigned + (constrained_unassigned // 2)