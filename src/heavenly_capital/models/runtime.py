from abc import abstractmethod, ABC
from enum import Enum
from typing import Optional, Any, Protocol, runtime_checkable



@runtime_checkable
class RuntimeModule(Protocol):

    def configure(self, config: Any, ports: Any) -> Any: ...

    def start(self) -> Any: ...

    def stop(self) -> Any: ...

    @property
    def is_configured(self) -> bool: ...

    @property
    def is_started(self) -> bool: ...

    def health_check(self) -> dict[str, Any]: ...


class AsyncRuntimeModule(RuntimeModule):

    @abstractmethod
    async def start(self) -> Any:
        pass

    @abstractmethod
    async def stop(self) -> Any:
        pass



class ModuleType(str, Enum):
    ORDERS = "orders"
    PORTFOLIO = "portfolio"
    RISK = "risk"


class ModuleRouter(ABC):
    @abstractmethod
    def transfer(
        self,
        source: ModuleType,
        target: ModuleType,
        payload: Any,
    ) -> None:
        ...


class BaseModule(ABC):

    def __init__(self) -> None:
        self._router: Optional[ModuleRouter] = None
        self._module_type: Optional[ModuleType] = None

    def bind_router(self, router: ModuleRouter, module_type: ModuleType) -> None:
        self._router = router
        self._module_type = module_type

    def send(self, target: ModuleType, payload: Any) -> None:
        self._router.transfer(
            source=self._module_type,
            target=target,
            payload=payload,
        )

    def _receive(self, source: ModuleType, payload: Any) -> None:
        pass


