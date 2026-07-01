import random
import time
from typing import Optional, Union, Dict

from heavenly_capital.strategy.artifacts import ModelState, ModelOutput


class MockModel:
    def __init__(self):
        self._input_names = ['volatility_close_last_5s', 'return_close_last_5s']

    def predict(self, features: Dict[str, float], state: Optional[Union[ModelState, Dict]] = None):
        if set(features.keys()) != set(self._input_names):
            raise ValueError(f"Features dictionary must have exactly keys: {self._input_names}")

        if state is None:
            state_out: Union[ModelState, Dict] = {}
            step = 1
        else:
            if isinstance(state, dict):
                state = ModelState()
            state_out = state
            step = state_out.counters.get("step", 0) + 1
            state_out.counters["step"] = step

        decision = random.random() < 0.10
        score = random.random()
        forced = False
        timestamp = int(time.time())

        output = ModelOutput(
            decision=decision,
            score=score,
            forced=forced,
            step=step,
            timestamp=timestamp
        )

        return output, state_out
