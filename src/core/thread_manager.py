from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass

from typing import Any, Callable, Dict, Optional, Tuple

from src.core.runtime_config import RuntimeModule, ThreadConfig
from src.core.system_manager import SystemPorts

PoolName = str


@dataclass(frozen=True)
class ThreadPoolConfig:
    name: PoolName
    size: int

class _StopSignal:
    """Internal sentinel to stop workers."""


_STOP = _StopSignal()


class PoolWorker(threading.Thread):

    def __init__(
        self,
        pool_name: PoolName,
        task_queue: "queue.Queue[object]",
        *,
        daemon: bool = True,
        worker_index: int = 0,
    ) -> None:
        super().__init__(name=f"{pool_name}-worker-{worker_index}", daemon=daemon)
        self._pool_name = pool_name
        self._q = task_queue
        self._running = threading.Event()
        self._running.set()
        self._last_error: Optional[BaseException] = None

    @property
    def last_error(self) -> Optional[BaseException]:
        return self._last_error

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:
        while self._running.is_set():
            item = self._q.get()
            try:
                if item is _STOP:
                    return
                fn, args, kwargs = item  # type: ignore[misc]
                fn(*args, **kwargs)
            except BaseException as e:
                self._last_error = e
            finally:
                try:
                    self._q.task_done()
                except ValueError:
                    # task_done called too many times - ignore defensively
                    pass


class ThreadPool:
    """A small fixed-size pool with persistent worker threads."""

    def __init__(self, config: ThreadPoolConfig) -> None:
        if config.size <= 0:
            raise ValueError(f"Pool {config.name} size must be > 0 (got {config.size})")
        self.config = config
        self._q: "queue.Queue[object]" = queue.Queue()
        self._workers: list[PoolWorker] = []
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self.config.size):
            w = PoolWorker(self.config.name, self._q, worker_index=i)
            self._workers.append(w)
            w.start()

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        if not self._started:
            raise RuntimeError(f"Pool {self.config.name} not started")
        self._q.put((fn, args, kwargs))

    def shutdown(self, *, wait: bool = True, timeout_s: Optional[float] = 5.0) -> None:
        if not self._started:
            return

        for _ in self._workers:
            self._q.put(_STOP)

        if wait:
            deadline = None if timeout_s is None else (time.time() + timeout_s)
            for w in self._workers:
                remaining = None if deadline is None else max(0.0, deadline - time.time())
                w.join(timeout=remaining)

        self._started = False

    @property
    def workers(self) -> Tuple[PoolWorker, ...]:
        return tuple(self._workers)

    @property
    def queue_size(self) -> int:
        try:
            return self._q.qsize()
        except NotImplementedError:
            return -1


class ThreadManager(RuntimeModule):

    def __init__(self) -> None:
        self._pools: Dict[PoolName, ThreadPool] = {}
        self._started = False
        self._configured = False

        self._config: Optional[ThreadConfig] = None
        self._ports: Optional[SystemPorts] = None

    def configure(self, *, config: ThreadConfig, ports: SystemPorts) -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def _build_pool_configs(self) -> Dict[PoolName, ThreadPoolConfig]:
        if self._config is None:
            raise RuntimeError("ThreadManager: config not set (configure() not called)")

        return {
            "CRITICAL": ThreadPoolConfig(name="CRITICAL", size=int(self._config.critical)),
            "STANDARD": ThreadPoolConfig(name="STANDARD", size=int(self._config.standard)),
            "BULK": ThreadPoolConfig(name="BULK", size=int(self._config.bulk)),
            "AUDIT": ThreadPoolConfig(name="AUDIT", size=int(self._config.audit)),
        }


    def start(self) -> None:
        if self._started:
            return

        # TODO: Replace Mock by the config retriever fn
        cfgs = self._build_pool_configs()

        self._pools = {name: ThreadPool(cfg) for name, cfg in cfgs.items()}

        for pool in self._pools.values():
            pool.start()

        # TODO : placeholder for future OS-specific tuning
        _ = os.name

        self._started = True

    def submit(self, pool: PoolName, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        if not self._started:
            raise RuntimeError("ThreadManager not initialized; call initialize_pools() first")
        try:
            self._pools[pool].submit(fn, *args, **kwargs)
        except KeyError as e:
            raise ValueError(f"Unknown pool {pool!r}. Known pools: {sorted(self._pools.keys())}") from e

    def stop(self, *, wait: bool = True, timeout_s: Optional[float] = 5.0) -> None:
        for pool in self._pools.values():
            pool.shutdown(wait=wait, timeout_s=timeout_s)
        self._started = False


    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started


    def get_pool(self, pool: PoolName) -> ThreadPool:
        return self._pools[pool]

    @property
    def pools(self) -> Dict[PoolName, ThreadPool]:
        return dict(self._pools)

    @property
    def config(self) -> ThreadConfig:
        if self._config is None:
            raise RuntimeError("ForecastManager: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> SystemPorts:
        if self._ports is None:
            raise RuntimeError("ForecastManager: ports not set (configure() not called)")
        return self._ports


    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

    def join(self): ...
    # TODO : herite join() from all the worker


_instance: Optional[ThreadManager] = None

def get_thread_manager() -> ThreadManager:
    global _instance
    if _instance is None:
        _instance = ThreadManager()
    return _instance