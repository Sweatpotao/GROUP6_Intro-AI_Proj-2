from core.solver.astar_base import AStarBase


class AStarH1(AStarBase):
    # A* với heuristic H1: đếm số ô (= 0) chưa được gán

    def _heuristic(self, grid: list) -> int:
        return sum(
            1 for i in range(self.n)
            for j in range(self.n)
            if grid[i][j] == 0
        )