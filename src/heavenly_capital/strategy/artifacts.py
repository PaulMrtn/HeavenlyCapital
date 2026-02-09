from dataclasses import dataclass, field
from typing import Any, Optional, Dict
import numpy as np

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



@dataclass(slots=True)
class DecisionRecord:
    model_id: str
    conid: int
    timestamp: int
    step: int
    decision: bool
    forced: bool
    score: float
    output_at: float
    penalty: Optional[float] = None



