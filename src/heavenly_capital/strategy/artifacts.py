from dataclasses import dataclass
from typing import Any
import numpy as np

from enum import Enum


class ModelKind(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    STOP_LOSS = "STOP_LOSS"


@dataclass(frozen=True)
class ForecastInput:
    features: np.ndarray
    timestamp: int
    instrument: str
    timeframe: str
    metadata: dict[str, Any]
