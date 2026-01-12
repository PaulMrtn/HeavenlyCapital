from __future__ import annotations

from typing import Optional, Any

from src.core.runtime_config import IBKRConfig, RuntimeModule
from src.core.system_manager import SystemPorts


class IBKRGateway(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional[IBKRConfig] = None
        self._ports: Optional[SystemPorts] = None

    def configure(self, *, config: IBKRConfig, ports: SystemPorts) -> None:
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
    def ports(self) -> SystemPorts:
        if self._ports is None:
            raise RuntimeError("IBKRGateway: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }


_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance