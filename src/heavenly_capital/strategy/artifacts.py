from dataclasses import dataclass, field
from time import time
from typing import Optional, Dict

from enum import Enum


class ModelKind(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    STOP_LOSS = "STOP_LOSS"


@dataclass(frozen=True)
class ModelInput:
    features: dict[str, float]
    timestamp: int
    instrument: str
    input_at: str


# for the model generator
@dataclass(slots=True, frozen=True)
class ModelOutput:
    decision: bool
    score: float
    forced: bool
    step: int
    timestamp: int
    penalty: Optional[float] = None


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