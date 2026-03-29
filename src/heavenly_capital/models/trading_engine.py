from dataclasses import dataclass
from datetime import date
from typing import Any, Dict

from heavenly_capital.models.runtime import ModuleRouter, ModuleType, BaseModule



@dataclass(frozen=True)
class TradingSessionKey:
    session_date: date
    account_id: str
    portfolio_id: str
    mode: str



class TradingEngine(ModuleRouter):

    def __init__(
            self,
            orders: BaseModule,
            portfolio: BaseModule,
            risk: BaseModule,
    ) -> None:
        self._modules: Dict[ModuleType, BaseModule] = {
            ModuleType.ORDERS: orders,
            ModuleType.PORTFOLIO: portfolio,
            ModuleType.RISK: risk,
        }

        for module_type, module in self._modules.items():
            module.bind_router(self, module_type)

    def transfer(
            self,
            *,
            source: ModuleType,
            target: ModuleType,
            payload: Any,
    ) -> None:
        if source == target:
            return

        target_module = self._modules[target]
        target_module.receive(payload, source)

    @property
    def orders(self):
        return self._modules[ModuleType.ORDERS]

    @property
    def portfolio(self):
        return self._modules[ModuleType.PORTFOLIO]

    @property
    def risk(self):
        return self._modules[ModuleType.RISK]
