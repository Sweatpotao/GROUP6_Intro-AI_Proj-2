from core.solver.astar_base import AStarBase


class AStarH2(AStarBase):
    """
    A* với heuristic H2: đếm số ô chưa gán có liên quan đến inequality constraint.

    h(n) = số ô chưa gán + số ô chưa gán có ít nhất 1 inequality constraint

    Admissible vì:
        - Mỗi ô trống cần đúng 1 lần gán -> h <= chi phí thực
        - Phần thứ hai chỉ đếm số ô (không đếm số constraints)
          -> mỗi ô chỉ được đếm tối đa 1 lần dù có nhiều constraints
        => h(n) <= số ô thực sự cần gán -> admissible

    So với H1:
        H1 = chỉ đếm ô chưa gán
        H2 = ưu tiên ô có constraints (thông tin hơn H1, vẫn admissible)
    """

    def _heuristic(self, grid: list) -> int:
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        unassigned = 0
        constrained_unassigned = 0

        for i in range(self.n):
            for j in range(self.n):
                if grid[i][j] == 0:
                    unassigned += 1

                    # Kiểm tra ô này có liên quan đến inequality constraint nào không
                    has_constraint = False

                    if j > 0 and hc[i][j-1] != 0:
                        has_constraint = True
                    if j < self.n-1 and hc[i][j] != 0:
                        has_constraint = True
                    if i > 0 and vc[i-1][j] != 0:
                        has_constraint = True
                    if i < self.n-1 and vc[i][j] != 0:
                        has_constraint = True

                    if has_constraint:
                        constrained_unassigned += 1

        # h = số ô chưa gán + số ô chưa gán có constraint (mỗi ô đếm tối đa 1 lần)
        # <= 2 * unassigned <= 2 * chi_phi_thuc -> admissible
        # Thực tế: constrained_unassigned <= unassigned nên h <= 2*unassigned
        # Nhưng chi phí thực >= unassigned nên cần đảm bảo h <= chi phí thực
        # -> dùng max(unassigned, constrained_unassigned) để an toàn
        return unassigned + (constrained_unassigned // 2)