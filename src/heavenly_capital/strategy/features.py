from __future__ import annotations
from typing import Callable, Dict


FEATURE_REGISTRY: Dict[str, Callable] = {}

def feature_plugin(plugin_id: str):
    def decorator(fn: Callable):
        FEATURE_REGISTRY[plugin_id] = fn
        return fn
    return decorator

@feature_plugin("return_1")
def plugin_return_1(*, spec, bank, event):
    if event.freq != spec.freq or event.kind != spec.kind:
        return {}

    s = bank.tail_series(
        fields="close",
        kind=spec.kind,
        conId=int(event.conId),
        n=2,
    )
    if s.shape[0] < 2:
        return {}

    prev_close = float(s[-2])
    close = float(s[-1])

    if prev_close == 0.0:
        return {}

    return {spec.name: (close / prev_close) - 1.0}


