from collections import deque

from core.solver.astar_base import AStarBase


class AStarH3(AStarBase):
    # A* với heuristic H3: dựa trên AC-3 (Arc Consistency 3)

    _INF = 10 ** 9

    def _heuristic(self, grid: list) -> int:
        domains = self._build_domains(grid)
        ok = self._run_ac3(domains)

        if not ok:
            # Domain rỗng -> nhánh này không có lời giải
            return self._INF

        # Số ô chưa xác định (domain > 1)
        return sum(
            1 for i in range(self.n)
            for j in range(self.n)
            if len(domains[i][j]) > 1
        )

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    def _build_domains(self, grid: list) -> list:
        """Xây dựng domain cho từng ô dựa trên grid hiện tại."""
        domains = []
        for i in range(self.n):
            row = []
            for j in range(self.n):
                v = grid[i][j]
                if v != 0:
                    row.append({v})
                else:
                    # Loại bỏ ngay các giá trị đã có trong cùng hàng/cột
                    used = set()
                    for jj in range(self.n):
                        if grid[i][jj] != 0:
                            used.add(grid[i][jj])
                    for ii in range(self.n):
                        if grid[ii][j] != 0:
                            used.add(grid[ii][j])
                    row.append(set(range(1, self.n + 1)) - used)
            domains.append(row)
        return domains

    # ------------------------------------------------------------------
    # AC-3
    # ------------------------------------------------------------------

    def _run_ac3(self, domains: list) -> bool:
        """
        Chạy thuật toán AC-3 trên domains.
        Trả về False nếu phát hiện domain rỗng (dead-end).

        AC-3 xử lý hàng đợi các cung (arc) (Xi, Xj):
            - Với mỗi giá trị trong domain(Xi), kiểm tra có giá trị
              nào trong domain(Xj) thỏa constraint(Xi, Xj) không
            - Nếu không -> loại giá trị đó khỏi domain(Xi)
            - Nếu domain(Xi) thay đổi -> thêm tất cả cung liên quan
              vào hàng đợi để xử lý lại
        """
        # Khởi tạo hàng đợi với tất cả cung
        queue = deque()

        # Cung hàng: (i,j1) <-> (i,j2) với j1 != j2
        for i in range(self.n):
            for j1 in range(self.n):
                for j2 in range(self.n):
                    if j1 != j2:
                        queue.append(((i, j1), (i, j2), "row"))

        # Cung cột: (i1,j) <-> (i2,j) với i1 != i2
        for j in range(self.n):
            for i1 in range(self.n):
                for i2 in range(self.n):
                    if i1 != i2:
                        queue.append(((i1, j), (i2, j), "col"))

        # Cung inequality ngang
        hc = self.puzzle["h_constraints"]
        for i in range(self.n):
            for j in range(self.n - 1):
                if hc[i][j] != 0:
                    queue.append(((i, j), (i, j + 1), "hineq"))
                    queue.append(((i, j + 1), (i, j), "hineq_rev"))

        # Cung inequality dọc
        vc = self.puzzle["v_constraints"]
        for i in range(self.n - 1):
            for j in range(self.n):
                if vc[i][j] != 0:
                    queue.append(((i, j), (i + 1, j), "vineq"))
                    queue.append(((i + 1, j), (i, j), "vineq_rev"))

        while queue:
            (r1, c1), (r2, c2), arc_type = queue.popleft()

            if self._revise(domains, r1, c1, r2, c2, arc_type):
                if len(domains[r1][c1]) == 0:
                    return False  # Dead-end

                # Domain(r1,c1) thay đổi -> thêm lại các cung liên quan
                for i in range(self.n):
                    if i != r1 or True:  # thêm cung hàng
                        pass
                # Đơn giản hóa: thêm lại cung hàng và cột của (r1,c1)
                for jj in range(self.n):
                    if jj != c1:
                        queue.append(((r1, jj), (r1, c1), "row"))
                for ii in range(self.n):
                    if ii != r1:
                        queue.append(((ii, c1), (r1, c1), "col"))

        return True

    def _revise(self, domains, r1, c1, r2, c2, arc_type) -> bool:
        """
        Loại bỏ các giá trị trong domain(r1,c1) không có giá trị
        tương ứng trong domain(r2,c2) thỏa constraint.
        Trả về True nếu domain(r1,c1) bị thu hẹp.
        """
        to_remove = set()
        hc = self.puzzle["h_constraints"]
        vc = self.puzzle["v_constraints"]

        for v1 in domains[r1][c1]:
            # Kiểm tra có v2 nào trong domain(r2,c2) thỏa constraint không
            has_support = False

            for v2 in domains[r2][c2]:
                if arc_type == "row" or arc_type == "col":
                    # Uniqueness: v1 != v2
                    if v1 != v2:
                        has_support = True
                        break

                elif arc_type == "hineq":
                    # (r1,c1) ? (r1,c1+1), c2 = c1+1
                    c = hc[r1][c1]
                    if c == 1 and v1 < v2:
                        has_support = True
                        break
                    if c == -1 and v1 > v2:
                        has_support = True
                        break

                elif arc_type == "hineq_rev":
                    # (r1,c1) ? (r1,c1-1), c2 = c1-1
                    c = hc[r1][c2]  # constraint giữa c2 và c1
                    if c == 1 and v2 < v1:
                        has_support = True
                        break
                    if c == -1 and v2 > v1:
                        has_support = True
                        break

                elif arc_type == "vineq":
                    # (r1,c1) ? (r1+1,c1), r2 = r1+1
                    c = vc[r1][c1]
                    if c == 1 and v1 < v2:
                        has_support = True
                        break
                    if c == -1 and v1 > v2:
                        has_support = True
                        break

                elif arc_type == "vineq_rev":
                    # (r1,c1) ? (r1-1,c1), r2 = r1-1
                    c = vc[r2][c1]  # constraint giữa r2 và r1
                    if c == 1 and v2 < v1:
                        has_support = True
                        break
                    if c == -1 and v2 > v1:
                        has_support = True
                        break

            if not has_support:
                to_remove.add(v1)

        if to_remove:
            domains[r1][c1] -= to_remove
            return True

        return False