"""Union-Find clustering over dedup pairs."""
from pathlib import Path
from rune.models.report import DedupPair


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[Path, Path] = {}

    def find(self, x: Path) -> Path:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: Path, b: Path) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def cluster_pairs(pairs: list[DedupPair], threshold: float) -> list[list[Path]]:
    """Group paths by transitive similarity at or above threshold."""
    uf = UnionFind()
    for p in pairs:
        if p.similarity >= threshold:
            uf.union(p.source_a, p.source_b)

    groups: dict[Path, list[Path]] = {}
    for node in list(uf.parent):
        root = uf.find(node)
        groups.setdefault(root, []).append(node)

    return [g for g in groups.values() if len(g) >= 2]
