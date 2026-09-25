"""The local vector database: each report's embedding, for finding its like.

Vectors live in the same SQL database as the reports (:mod:`sif.datastore`,
table ``vectors``), one per report per encoder, so a site that moves from the
offline hashing encoder to the transformer keeps both sets and never compares
one with the other. The encoders return L2-normalised rows, so similarity is
a dot product; the matrix for an encoder is read once and kept until a write.

This is enough for the tens of thousands of reports a field HQ produces in
years. A site that outgrows it swaps this class for pgvector or a dedicated
store behind the same three calls: upsert, search, missing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .datastore import DataStore

__all__ = ["VectorStore"]


class VectorStore:
    def __init__(self, store: DataStore) -> None:
        self.store = store
        self._cache: Dict[str, Tuple[List[str], List[str], np.ndarray]] = {}

    def upsert(self, items: Iterable[Tuple[str, str, np.ndarray]], encoder: str) -> int:
        """Store (fingerprint, reference, vector) for ``encoder``; returns how many."""
        from sqlalchemy import and_, select

        table = self.store.vectors
        stamp = datetime.now().isoformat(timespec="seconds")
        written = 0
        with self.store.engine.begin() as connection:
            for fingerprint, reference, vector in items:
                data = np.asarray(vector, dtype=np.float32).ravel()
                row = {"fingerprint": fingerprint, "encoder": encoder, "reference": reference,
                       "dim": int(data.size), "vector": data.tobytes(), "updated_at": stamp}
                condition = and_(table.c.fingerprint == fingerprint, table.c.encoder == encoder)
                if connection.execute(select(table.c.dim).where(condition)).first() is None:
                    connection.execute(table.insert().values(**row))
                else:
                    connection.execute(table.update().where(condition).values(**row))
                written += 1
        self._cache.pop(encoder, None)
        return written

    def _matrix(self, encoder: str) -> Tuple[List[str], List[str], np.ndarray]:
        from sqlalchemy import select

        if encoder not in self._cache:
            table = self.store.vectors
            with self.store.engine.connect() as connection:
                rows = connection.execute(select(
                    table.c.fingerprint, table.c.reference, table.c.dim, table.c.vector)
                    .where(table.c.encoder == encoder)).all()
            if rows:
                dim = rows[0][2]
                rows = [row for row in rows if row[2] == dim]
                matrix = np.vstack([np.frombuffer(row[3], dtype=np.float32) for row in rows])
            else:
                matrix = np.zeros((0, 0), dtype=np.float32)
            self._cache[encoder] = ([row[0] for row in rows], [row[1] for row in rows], matrix)
        return self._cache[encoder]

    def search(self, vector: np.ndarray, encoder: str, k: int = 5,
               exclude: Sequence[str] = ()) -> List[Tuple[str, str, float]]:
        """The ``k`` closest stored reports: (fingerprint, reference, cosine)."""
        fingerprints, references, matrix = self._matrix(encoder)
        query = np.asarray(vector, dtype=np.float32).ravel()
        if matrix.size == 0 or matrix.shape[1] != query.size:
            return []
        norm = float(np.linalg.norm(query)) or 1.0
        scores = matrix @ (query / norm)
        order = np.argsort(-scores)
        skip = set(exclude)
        found = []
        for index in order:
            if fingerprints[index] in skip:
                continue
            found.append((fingerprints[index], references[index], float(scores[index])))
            if len(found) >= k:
                break
        return found

    def missing(self, fingerprints: Iterable[str], encoder: str) -> List[str]:
        stored = set(self._matrix(encoder)[0])
        return [fingerprint for fingerprint in fingerprints if fingerprint not in stored]

    def count(self, encoder: Optional[str] = None) -> int:
        from sqlalchemy import func, select

        table = self.store.vectors
        query = select(func.count()).select_from(table)
        if encoder:
            query = query.where(table.c.encoder == encoder)
        with self.store.engine.connect() as connection:
            return int(connection.execute(query).scalar() or 0)

    def encoders(self) -> List[str]:
        from sqlalchemy import select

        table = self.store.vectors
        with self.store.engine.connect() as connection:
            return sorted({row[0] for row in connection.execute(select(table.c.encoder))})
