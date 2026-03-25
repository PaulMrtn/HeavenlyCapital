from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from heavenly_capital.models.runtime import RuntimeModule

if TYPE_CHECKING:
    from heavenly_capital.models.config import ThreadConfig

ThreadTarget = Callable[[threading.Event], None]


class ManagedThread:
    def __init__(self, name: str, target=None, daemon: bool = False):
        self.name = name
        self._stop_event = threading.Event()
        self._target = target
        self._jobs: "queue.Queue[tuple[Callable, tuple, dict]]" = queue.Queue()

        self._thread = threading.Thread(
            target=self._run,
            name=name,
            daemon=daemon
        )

    def _run(self):
        if self._target:
            try:
                self._target(self._stop_event)
            except Exception as e:
                print(f"[{self.name}] target error: {e}")
            return

        while not self._stop_event.is_set():
            try:
                fn, args, kwargs = self._jobs.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                fn(*args, **kwargs)
            except Exception as e:
                print(f"[{self.name}] job failed: {fn.__name__} -> {e}")
            finally:
                self._jobs.task_done()


    def submit_job(self, fn: Callable, *args, **kwargs):
        self._jobs.put((fn, args, kwargs))

    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        self._stop_event.set()

    def join(self, timeout=None):
        self._thread.join(timeout)

    @property
    def is_alive(self):
        return self._thread.is_alive()



class ThreadManager(RuntimeModule):

    def __init__(self):
        self._threads: Dict[str, ManagedThread] = {}
        self._started = False
        self._configured = False
        self._config: Optional["ThreadConfig"] = None

    def configure(self, config: "ThreadConfig", ports: Any) -> None:
        self._config = config
        self._configured = True

    def start_all(self):
        for t in self._threads.values():
            t.start()
        self._started = True

    def start_thread(self, name: str) -> None:
        t = self._threads.get(name)
        if t is None:
            raise ValueError(f"Thread {name!r} non trouvé")
        t.start()

    def register_thread(self, name: str, target: Optional[ThreadTarget]=None, daemon=False):
        if name in self._threads:
            raise ValueError(f"{name} déjà enregistré")
        t = ManagedThread(name=name, target=target, daemon=daemon)
        self._threads[name] = t
        return t

    def submit(self, thread_name: str, fn: Callable, *args, **kwargs):
        t = self._threads.get(thread_name)
        if not t:
            raise ValueError(f"Thread {thread_name!r} non trouvé")
        t.submit_job(fn, *args, **kwargs)

    def stop_thread(self, name: str, wait: bool = True):
        t = self._threads.get(name)
        if t is None:
            raise ValueError(f"Thread {name!r} non trouvé")
        t.stop()
        if wait:
            t.join()

    def stop_all(self):
        for t in self._threads.values():
            t.stop()
        for t in self._threads.values():
            t.join()

    def is_started(self) -> bool:
        return self._started

    def is_configured(self) -> bool:
        return self._configured


    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }


    # def health_check(self) -> dict[str, Any]:
    #     return {
    #         "threads": {name: t.is_alive for name, t in self._threads.items()},
    #         "is_started": self._started,
    #         "is_configured": self._configured,
    #     }






_instance: Optional[ThreadManager] = None

def get_thread_manager() -> ThreadManager:
    global _instance
    if _instance is None:
        _instance = ThreadManager()
    return _instance