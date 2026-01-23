from __future__ import annotations

from typing import Optional, Any, TYPE_CHECKING

from heavenly_capital.core.runtime_config import LiveHubConfig, RuntimeModule

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts

class LiveDataHub(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional[LiveHubConfig] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: LiveHubConfig, ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("LiveDataHub: start() called before configure()")
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
    def config(self) -> LiveHubConfig:
        if self._config is None:
            raise RuntimeError("LiveDataHub: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("LiveDataHub: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }


_instance: Optional[LiveDataHub] = None


def get_live_data_hub() -> LiveDataHub:
    global _instance
    if _instance is None:
        _instance = LiveDataHub()
    return _instance