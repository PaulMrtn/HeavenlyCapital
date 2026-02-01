from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Optional, Dict


@dataclass(frozen=True, slots=True)
class InstrumentFeatureSnapshot:
    conId: int
    features: Dict[str, float]
    updated_at: float


@dataclass(frozen=True, slots=True)
class CrossFeatureSnapshot:
    """
    Features globales inter-instruments (ex: corrélations).
    """
    features: Dict[str, float]
    updated_at: float


class InstrumentFeatureStore:
    """
    Swap-buffer par instrument: conId -> snapshot immuable.
    """
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshots: Dict[int, InstrumentFeatureSnapshot] = {}

    def get_snapshot(self, conId: int) -> Optional[InstrumentFeatureSnapshot]:
        return self._snapshots.get(conId)

    def set_features(self, *, conId: int, features: Dict[str, float], updated_at: float) -> InstrumentFeatureSnapshot:
        """
        Remplace complètement le set de features d'un instrument.
        """
        snap = InstrumentFeatureSnapshot(conId=conId, features=dict(features), updated_at=float(updated_at))
        with self._lock:
            self._snapshots[conId] = snap
        return snap

    def upsert_features(self, *, conId: int, patch: Dict[str, float], updated_at: float) -> InstrumentFeatureSnapshot:
        """
        Merge partiel: ajoute / remplace uniquement les clés du patch.
        """
        with self._lock:
            prev = self._snapshots.get(conId)
            merged = dict(prev.features) if prev is not None else {}
            merged.update(patch)

            snap = InstrumentFeatureSnapshot(conId=conId, features=merged, updated_at=float(updated_at))
            self._snapshots[conId] = snap
            return snap


class CrossFeatureStore:
    """
    Swap-buffer global: 1 snapshot immuable inter-instruments.
    """
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot: Optional[CrossFeatureSnapshot] = None

    def get_snapshot(self) -> Optional[CrossFeatureSnapshot]:
        return self._snapshot

    def set_features(self, *, features: Dict[str, float], updated_at: float) -> CrossFeatureSnapshot:
        snap = CrossFeatureSnapshot(features=dict(features), updated_at=float(updated_at))
        with self._lock:
            self._snapshot = snap
        return snap

    def upsert_features(self, *, patch: Dict[str, float], updated_at: float) -> CrossFeatureSnapshot:
        with self._lock:
            prev = self._snapshot.features if self._snapshot is not None else {}
            merged = dict(prev)
            merged.update(patch)

            snap = CrossFeatureSnapshot(features=merged, updated_at=float(updated_at))
            self._snapshot = snap
            return snap