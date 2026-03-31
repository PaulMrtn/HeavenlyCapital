from __future__ import annotations
from typing import Callable, Dict, Optional, TYPE_CHECKING

import numpy as np

from heavenly_capital.strategy.artifacts import FeatureSpec

if TYPE_CHECKING:
    from heavenly_capital.strategy.feature_engine import FeatureStore


FEATURE_REGISTRY: Dict[str, Callable] = {}

def feature_plugin(plugin_id: str):
    def decorator(fn: Callable):
        if plugin_id in FEATURE_REGISTRY:
            raise RuntimeError(f"Plugin already registered: {plugin_id}")
        FEATURE_REGISTRY[plugin_id] = fn
        return fn
    return decorator


# spec: if you need to inject som params like windows, you can use different fields for cache with params

@feature_plugin("return")
def plugin_return(*, spec, cache: IntraFeatureCache):
    all_returns = cache.get_returns(n=1, fields=spec.fields)
    if all_returns is None:
        return np.nan

    if all_returns.size == 0 or np.isnan(all_returns[-1]):
        return np.nan

    return float(all_returns[-1])


@feature_plugin("volatility")
def plugin_volatility(*, spec, cache: IntraFeatureCache):
    n = spec.params.get("window")
    returns = cache.get_returns(n=n, fields=spec.fields)

    if returns is None:
        return np.nan

    valid = np.count_nonzero(~np.isnan(returns))
    if valid < 2:
        return np.nan

    return float(np.nanstd(returns))



@feature_plugin("correlation")
def plugin_correlation(*, spec, cache: "CrossFeatureCache"):
    n = spec.params.get("window")
    fields = spec.fields

    matrix = cache.get_cross_returns(n=n, fields=fields, kind=spec.kind)
    if matrix is None or matrix.shape[0] < 2:
        return np.nan

    with np.errstate(invalid='ignore'):
        corr_matrix = np.corrcoef(matrix.T)

    mask = ~np.eye(corr_matrix.shape[0], dtype=bool)
    max_corr = np.nanmax(corr_matrix[mask])

    # TODO:LOW You use max() here, for scalar but you had to handle this matrix

    return max_corr

@feature_plugin("relative_spread")
def plugin_relative_spread(*, spec, store, freq):
    basket = spec.params.get("basket")
    cache = DerivedFeatureCache(store, freq, basket)

    inputs = cache.resolve_inputs(spec)
    ret = inputs["ret"]

    cross = cache.resolve_cross(spec)

    result = {
        conId: (v - cross if not np.isnan(v) else np.nan)
        for conId, v in ret.items()
    }

    return result


class FeatureCache:
    def __init__(self, bank, event, scope):
        self.scope = scope
        if scope == "per_asset":
            self._cache = IntraFeatureCache(bank, event)
        elif scope == "cross_asset":
            self._cache = CrossFeatureCache(bank, event)
        else:
            raise ValueError(f"Unknown scope: {scope}")

    def get_returns(self, n: int, fields: str) -> Optional[np.ndarray]:
        if self.scope != "per_asset":
            raise RuntimeError("get_returns is only valid for intra-asset features")
        return self._cache.get_returns(n, fields)

    def get_cross_returns(self, n: int, fields: str, kind: str = "last") -> Optional[np.ndarray]:
        if self.scope != "cross_asset":
            raise RuntimeError("get_cross_returns is only valid for cross-asset features")
        return self._cache.get_cross_returns(n, fields, kind)

    def store_feature(self, name: str, value: float):
        self._cache.store_feature(name, value)

    def get_feature(self, name: str) -> float:
        return self._cache.get_feature(name)



class IntraFeatureCache:
    def __init__(self, bank: 'MarketDataBank', event: 'CandleEvent') :
        self.bank = bank
        self.event = event
        self._cache: Optional[dict[str, np.ndarray]] = {}
        self._cache_features: dict[str, float] = {}

    def get_returns(self, n: int, fields: str) -> Optional[np.ndarray]:
        cache_key = f"return_{fields}_{self.event.kind}_{n}"

        if cache_key not in self._cache:
            series = self.bank.tail_series(
                        fields=fields,
                        kind=self.event.kind,
                        conId=self.event.conId,
                        n=n+1
            )

            if series is None or series.shape[0] < n + 1:
                self._cache[cache_key] = None

            else:
                with np.errstate(divide='ignore', invalid='ignore'):
                    _return = np.where(series[:-1] == 0, np.nan, series[1:] / series[:-1] - 1.0)
                self._cache[cache_key] = _return

        return self._cache[cache_key]

    def store_feature(self, name: str, value: float):
        self._cache_features[name] = value

    def get_feature(self, name: str) -> float:
        return self._cache_features.get(name, np.nan)



class CrossFeatureCache:
    def __init__(self, bank: 'MarketDataBank', event: 'CandleEvent') :
        self.bank = bank
        self.event = event
        self._cache: Optional[dict[str, np.ndarray]] = {}
        self._cache_features: dict[str, float] = {}

    def get_cross_returns(self, n: int, fields: str, kind: str = "last") -> Optional[np.ndarray]:
        cache_key = f"cross_return_{fields}_{kind}_{n}"

        if cache_key not in self._cache:
            matrix = self.bank.tail_matrix(fields=fields, kind=kind, n=n + 1)

            if matrix is None or matrix.shape[0] < n + 1:
                self._cache[cache_key] = None
            else:
                prev = matrix[:-1]
                curr = matrix[1:]
                mask = (prev == 0) | np.isnan(prev)
                with np.errstate(divide='ignore', invalid='ignore'):
                    r = np.where(mask, np.nan, curr / prev - 1.0)
                self._cache[cache_key] = r

        return self._cache[cache_key]

    def store_feature(self, name: str, value: float):
        self._cache_features[name] = value

    def get_feature(self, name: str) -> float:
        return self._cache_features.get(name, np.nan)


class DerivedFeatureCache:
    def __init__(self, store: "FeatureStore", freq: str, basket: list[int] | None = None):
        self.store = store
        self.freq = freq
        self.basket = basket
        self._cache_features: dict[str, float] = {}


    def resolve_inputs(self, spec: "FeatureSpec") -> dict[str, dict[int, float]]:
        inputs = {}

        for key, cfg in spec.params.get("inputs", {}).items():
            name = f"{cfg['category']}_{spec.fields}_{spec.kind}_{self.freq}"
            inputs[key] = self.store.get_feature_map(name)

        return inputs

    def resolve_cross(self, spec: "FeatureSpec") -> float:
        cfg = spec.params.get("cross", {})

        name = f"{cfg['category']}_{spec.fields}_{spec.kind}_{self.freq}"
        agg = cfg.get("agg", "mean")

        return self.get_cross_feature(name=name, agg=agg)


    def get_cross_feature(self, name: str, agg: str) -> float:
        if self.basket:
            values = [self.store.get_latest(c, name) for c in self.basket]
            vals = [v for v in values if v is not None and not np.isnan(v)]

            if not vals:
                return np.nan

            if agg == "mean":
                return float(np.nanmean(vals))
            if agg == "median":
                return float(np.nanmedian(vals))
            if agg == "std":
                return float(np.nanstd(vals))
            if agg == "max":
                return float(np.nanmax(vals))
            if agg == "min":
                return float(np.nanmin(vals))

            raise ValueError(f"Unknown aggregation: {agg}")

        return self.store.get_global(name, agg)


    # TODO:LOW Finish cache option
    def get_feature(self, name: str, conId: int) -> float:
        if name in self._cache_features:
            return self._cache_features[name]

        value = self.store.get_latest(conId, name)
        return value if value is not None else np.nan

    def store_feature(self, name: str, value: float, conId: int):
        self._cache_features[f"{conId}_{name}"] = value



