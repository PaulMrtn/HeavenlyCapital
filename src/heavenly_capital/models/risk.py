from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, Optional



class PositionStatus(StrEnum):
    INACTIVE = "INACTIVE"
    MONITORING = "MONITORING"
    PENDING    = "PENDING"
    LIQUIDATED = "LIQUIDATED"


class TriggerReason(StrEnum):
    ML_SIGNAL      = "ML_SIGNAL"      # Règle 1 — signal ML STOP_LOSS
    HIT_THRESHOLD  = "HIT_THRESHOLD"   # Règle 3b — prix sous S en post/pre market
    FORCE_CLOSE    = "FORCE_CLOSE"    # Règle 2 — 15h55, distance trop faible
    BUFFER_BREACH  = "BUFFER_BREACH"   # Règle 3 — entrée zone buffer S-B



@dataclass
class MonitoredPosition:
    con_id: int
    threshold_pct: float                  # S% — depuis DB, immuable en session
    quantity: Optional[float] = None    # mis à jour à chaque fill BUY
    threshold_abs: float = 0.0            # avg_cost * (1 - threshold_pct)
    status: PositionStatus = PositionStatus.INACTIVE

    @classmethod
    def from_snapshot(cls, row: dict) -> "MonitoredPosition":
        return cls(
            con_id=int(row["con_id"]),
            threshold_pct=float(row["threshold_pct"])
        )

    def on_fill_updated(self, avg_cost: float, quantity: float) -> None:
        self.threshold_abs = avg_cost * (1 - self.threshold_pct)
        self.quantity = quantity
        self.status = PositionStatus.MONITORING

    def on_order_sent(self) -> None:
        self.status = PositionStatus.PENDING

    def on_closed(self) -> None:
        self.status = PositionStatus.LIQUIDATED

    @property
    def is_monitoring(self) -> bool:
        return self.status == PositionStatus.MONITORING

    @property
    def is_pending(self) -> bool:
        return self.status == PositionStatus.PENDING

    @property
    def is_liquidated(self) -> bool:
        return self.status == PositionStatus.LIQUIDATED


class StopLossStore:

    def __init__(self) -> None:
        self._positions: Dict[int, MonitoredPosition] = {}

    @classmethod
    def from_rows(cls, rows: list[dict]) -> "StopLossStore":
        store = cls()
        for row in rows:
            pos = MonitoredPosition.from_snapshot(row)
            store._positions[pos.con_id] = pos
        return store

    def get(self, con_id: int) -> Optional[MonitoredPosition]:
        return self._positions.get(con_id)

    def on_fill_updated(self, con_id: int, avg_cost: float, quantity: float) -> None:
        pos = self._positions.get(con_id)
        if pos:
            pos.on_fill_updated(avg_cost, quantity)

    def on_order_sent(self, con_id: int) -> None:
        pos = self._positions.get(con_id)
        if pos:
            pos.on_order_sent()

    def on_closed(self, con_id: int) -> None:
        pos = self._positions.get(con_id)
        if pos:
            pos.on_closed()

    def is_monitoring(self, con_id: int) -> bool:
        pos = self._positions.get(con_id)
        return pos.is_monitoring if pos else False

    def has_position(self, con_id: int) -> bool:
        return con_id in self._positions

    def all_monitoring(self) -> list[MonitoredPosition]:
        return [p for p in self._positions.values() if p.is_monitoring]