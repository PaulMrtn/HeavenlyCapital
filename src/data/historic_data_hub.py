from __future__ import annotations

from typing import Optional

from src.core.runtime_config import HistoricHubConfig
from src.core.system_manager import SystemPorts


class HistoricDataHub:

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._enabled: bool = True
        self._config: Optional[HistoricHubConfig] = None
        self._ports: Optional[SystemPorts] = None

    def configure(self, *, config: HistoricHubConfig, ports: SystemPorts) -> None:
        self._config = config
        self._ports = ports
        self._enabled = bool(config.enabled)
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("HistoricDataHub: start() called before configure()")
        if not self._enabled:
            return
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
    def enabled(self) -> bool:
        return self._enabled

    @property
    def config(self) -> HistoricHubConfig:
        if self._config is None:
            raise RuntimeError("HistoricHubConfig: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> SystemPorts:
        if self._ports is None:
            raise RuntimeError("HistoricHubConfig: ports not set (configure() not called)")
        return self._ports


_instance: Optional[HistoricDataHub] = None


def get_historic_service() -> HistoricDataHub:
    global _instance
    if _instance is None:
        _instance = HistoricDataHub()
    return _instance