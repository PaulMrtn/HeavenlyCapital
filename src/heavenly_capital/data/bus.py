from threading import Lock
from typing import Dict, Any, List, Callable, Optional


class EventBus:

    def __init__(self, name: str):
        self.name = name
        self._lock = Lock()

        #TODO:MEDIUM necessaire de garder une copy du dernier publish ? overflow memory
        self._snapshots: Dict[int, Any] = {}
        self._subscribers: Dict[int, List[Callable]] = {}

        self._subscribers_all: List[Callable[[int, Any], None]] = []

        self._next_token: int = 1
        self._subscriptions: Dict[int, tuple[str, Optional[int], Callable[[int, Any], None]]] = {}

    def subscribe(self, conId: int, callback: Callable[[int, Any], None]):
        with self._lock:
            if conId not in self._subscribers:
                self._subscribers[conId] = []
            self._subscribers[conId].append(callback)

        token = self._next_token
        self._next_token += 1
        self._subscriptions[token] = ("conId", int(conId), callback)
        return token

    def subscribe_all(self, callback: Callable[[int, Any], None]) -> int:
        with self._lock:
            self._subscribers_all.append(callback)

            token = self._next_token
            self._next_token += 1
            self._subscriptions[token] = ("all", None, callback)
            return token

    def subscribe_many(self, conIds: list[int], callback: Callable[[int, Any], None]) -> list[int]:
        tokens: list[int] = []
        with self._lock:
            for conId in conIds:
                conId = int(conId)
                if conId not in self._subscribers:
                    self._subscribers[conId] = []
                self._subscribers[conId].append(callback)

                token = self._next_token
                self._next_token += 1
                self._subscriptions[token] = ("conId", conId, callback)
                tokens.append(token)

        return tokens

    def unsubscribe(self, token: int) -> bool:
        with self._lock:
            entry = self._subscriptions.pop(int(token), None)
            if entry is None:
                return False

            scope, conId, callback = entry

            if scope == "all":
                try:
                    self._subscribers_all.remove(callback)
                except ValueError:
                    pass
                return True

            if scope == "conId" and conId is not None:
                callbacks = self._subscribers.get(conId)
                if not callbacks:
                    return True
                try:
                    callbacks.remove(callback)
                except ValueError:
                    pass
                if not callbacks:
                    self._subscribers.pop(conId, None)
                return True

            return True

    def publish(self, conId: int, data: Any):
        with self._lock:
            self._snapshots[conId] = data

            callbacks_specific = self._subscribers.get(conId, [])
            callbacks_all = self._subscribers_all
            if not callbacks_specific and not callbacks_all:
                return
            target_callbacks = list(callbacks_specific) + list(callbacks_all)

        for cb in target_callbacks:
            try:
                cb(conId, data)
            except Exception as e:
                print(f"[{self.name}] Erreur Callback pour {conId}: {e}")


    def get_last(self, conId: int) -> Optional[Any]:
        with self._lock:
            return self._snapshots.get(conId)

