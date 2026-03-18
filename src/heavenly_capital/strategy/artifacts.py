from dataclasses import dataclass, field
from time import time
from typing import Optional, Dict, Any

from enum import Enum
from pathlib import Path



@dataclass(frozen=True, slots=True)
class FeatureSpec:
    category: str
    plugin: str
    freq: str | list[str]
    kind: str | list[str]
    name: str = ""
    fields: str = "close"
    priority: int = None
    scope: str = "per_asset"
    cache: bool = False
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_snapshot(cls, row: dict) -> "FeatureSpec":
        freqs = row.get("freqs") or []
        params = row.get("params") or {}

        return cls(
            category=row["category"],
            plugin=row["plugin"],
            freq=freqs,
            kind=row["kind"],
            fields=row.get("fields", "close"),
            priority=row.get("priority"),
            scope=row.get("scope", "per_asset"),
            cache=row.get("cache", False),
            params=params,
            name=row.get("name", "")
        )




class ModelKind(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    STOP_LOSS = "STOP_LOSS"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    model_type: ModelKind
    path: Path
    version: str

    @classmethod
    def from_snapshot(cls, row: dict) -> "ModelSpec":
        return cls(
            model_id=row["model_name"],
            model_type=ModelKind(row["model_type"]),
            path=Path(row["path"]),
            version=str(row["version"]),
        )


@dataclass(frozen=True)
class ModelInput:
    features: dict[str, float]
    timestamp: int
    instrument: str
    input_at: str


@dataclass(slots=True, frozen=True)
class ModelOutput:
    decision: bool
    score: float
    forced: bool
    step: int
    timestamp: int
    penalty: Optional[float] = None


@dataclass(frozen=True)
class ModelSignal:
    conid: int
    model_id: str
    model_type: str
    output: ModelOutput



@dataclass
class ModelState:
    dummy: Optional[float] = None

    counters: Dict[str, int] = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)
    cache: Dict[str, float] = field(default_factory=dict)


@dataclass
class DecisionRecord:
    model_id: str
    conid: int
    timestamp: int
    step: int
    decision: bool
    forced: bool
    score: float
    penalty: Optional[float]
    output_at: float

    @classmethod
    def from_model_output(
        cls,
        *,
        model_id: str,
        conid: int,
        output: "ModelOutput",
    ) -> "DecisionRecord":
        return cls(
            model_id=model_id,
            conid=conid,
            timestamp=output.timestamp,
            step=output.step,
            decision=output.decision,
            forced=output.forced,
            score=output.score,
            penalty=output.penalty,
            output_at=time(),
        )
