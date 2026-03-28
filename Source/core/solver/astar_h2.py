from core.solver.astar_base import AStarBase


class AStarH2(AStarBase):
    # A* với heuristic H2: kết hợp ô chưa gán + inequality constraints chưa thỏa

    def _heuristic(self, grid: list) -> int:
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        # Số ô chưa gán
        unassigned = sum(
            1 for i in range(self.n)
            for j in range(self.n)
            if grid[i][j] == 0
        )

        # Số inequality constraints có ít nhất 1 ô chưa được gán
        unsatisfied = 0

        for i in range(self.n):
            for j in range(self.n - 1):
                if hc[i][j] != 0:
                    # Constraint giữa (i,j) và (i,j+1)
                    if grid[i][j] == 0 or grid[i][j + 1] == 0:
                        unsatisfied += 1

        for i in range(self.n - 1):
            for j in range(self.n):
                if vc[i][j] != 0:
                    # Constraint giữa (i,j) và (i+1,j)
                    if grid[i][j] == 0 or grid[i + 1][j] == 0:
                        unsatisfied += 1

        return unassigned + unsatisfied