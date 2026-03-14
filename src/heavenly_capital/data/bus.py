from threading import Lock
from typing import Dict, Any, List, Callable, Optional, Hashable

from heavenly_capital.models.market_data import CandleEvent


Subscriber = Callable[[int, CandleEvent], None]


class EventBus:

    def __init__(self, name: str):
        self.name = name
        self._lock = Lock()

        #TODO:MEDIUM necessaire de garder une copy du dernier publish ? overflow memory
        self._snapshots: Dict[Hashable, Any] = {}
        self._subscribers: Dict[Hashable, List[Callable]] = {}
        self._subscribers_all: List[Subscriber] = []

        self._next_token: int = 1
        self._subscriptions: Dict[int, tuple[str, Optional[Hashable], Subscriber]] = {}

    def subscribe(self, entity_id: Hashable, callback: Callable[[Hashable, Any], None]):
        with self._lock:
            if entity_id not in self._subscribers:
                self._subscribers[entity_id] = []
            self._subscribers[entity_id].append(callback)

        token = self._next_token
        self._next_token += 1
        self._subscriptions[token] = ("entity_id", entity_id, callback)
        return token

    def subscribe_all(self, callback: Subscriber) -> int:
        with self._lock:
            self._subscribers_all.append(callback)

            token = self._next_token
            self._next_token += 1
            self._subscriptions[token] = ("all", None, callback)
            return token

    def subscribe_many(self, entity_ids: list[Hashable], callback: Callable[[Hashable, Any], None]) -> list[int]:
        tokens: list[int] = []
        with self._lock:
            for entity_id in entity_ids:
                if entity_id not in self._subscribers:
                    self._subscribers[entity_id] = []
                self._subscribers[entity_id].append(callback)

                token = self._next_token
                self._next_token += 1
                self._subscriptions[token] = ("entity_id", entity_id, callback)
                tokens.append(token)

        return tokens

    def unsubscribe(self, token: int) -> bool:
        with self._lock:
            entry = self._subscriptions.pop(int(token), None)
            if entry is None:
                return False

            scope, entity_id, callback = entry

            if scope == "all":
                try:
                    self._subscribers_all.remove(callback)
                except ValueError:
                    pass
                return True

            if scope == "entity_id" and entity_id is not None:
                callbacks = self._subscribers.get(entity_id)
                if not callbacks:
                    return True
                try:
                    callbacks.remove(callback)
                except ValueError:
                    pass
                if not callbacks:
                    self._subscribers.pop(entity_id, None)
                return True

            return True

    def publish(self, entity_id: Hashable, data: Any):
        with self._lock:
            self._snapshots[entity_id] = data

            callbacks_specific = self._subscribers.get(entity_id, [])
            callbacks_all = self._subscribers_all
            if not callbacks_specific and not callbacks_all:
                return
            target_callbacks = list(callbacks_specific) + list(callbacks_all)

        for cb in target_callbacks:
            try:
                cb(entity_id, data)
            except Exception as e:
                print(f"[{self.name}] Erreur Callback pour {entity_id}: {e}")


    #TODO:MEDIUM necessaire de garder une copy du dernier publish ? overflow memory
    def get_last(self, entity_id: Hashable) -> Optional[Any]:
        with self._lock:
            return self._snapshots.get(entity_id)

