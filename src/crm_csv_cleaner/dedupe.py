"""Agrupa registros que comparten alguna clave: componentes conexas con union-find.

Si A y B comparten teléfono y B y C comparten email, A, B y C quedan en el mismo grupo.
"""

from collections.abc import Hashable, Iterable, Sequence


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # compresión de camino
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # La raíz es siempre el índice menor: grupos estables y deterministas.
            self.parent[max(ra, rb)] = min(ra, rb)


def group_by_keys(keys_per_item: Sequence[Iterable[Hashable]]) -> list[list[int]]:
    """Devuelve grupos de índices; cada grupo, ordenado, y los grupos por su primer índice.

    Un elemento sin claves forma su propio grupo.
    """
    uf = UnionFind(len(keys_per_item))
    first_seen: dict[Hashable, int] = {}
    for i, keys in enumerate(keys_per_item):
        for key in keys:
            if key in first_seen:
                uf.union(first_seen[key], i)
            else:
                first_seen[key] = i
    groups: dict[int, list[int]] = {}
    for i in range(len(keys_per_item)):
        groups.setdefault(uf.find(i), []).append(i)
    return list(groups.values())
