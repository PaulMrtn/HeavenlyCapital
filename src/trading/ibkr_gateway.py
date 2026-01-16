from __future__ import annotations

from typing import Optional, Any, Callable, TYPE_CHECKING

from src.core.runtime_config import IBKRConfig, RuntimeModule

if TYPE_CHECKING:
    from src.core.system_manager import SystemPorts

class IBKRGateway(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional[IBKRConfig] = None
        self._ports: Optional["SystemPorts"] = None

        # TODO : MOCK sent order (update with OrderObject)
        self._mock_sent_orders: list[dict[str, Any]] = list()

    def configure(self, *, config: IBKRConfig, ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("IBKRGateway: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> IBKRConfig:
        if self._config is None:
            raise RuntimeError("IBKRGateway: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("IBKRGateway: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

    # --- MOCK SINK API -------------------------------------------------

    def order_sink(self, session_key, order: dict[str, Any]) -> None:
        # TODO: créer un objet Order contenant toutes les infos de TradingSessionKey et supprimer session-key en input.
        # Appliquer sysmetriquement la modificatin
        if not self._configured or not self._started:
            raise RuntimeError("IBKRGateway: order_sink() called while not started/configured")

        self._mock_sent_orders.append(order)

    def get_order_sink(self) -> Callable[[dict[str, Any]], None]:
        return self.order_sink

    # ------------------------------------------------------------------



_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance