from dataclasses import dataclass, asdict
from typing import Optional
import time

@dataclass
class SessionSnapshot:
    session_id: str
    date: str
    phase: str
    status: str
    state: str
    error: bool

@dataclass
class KernelSnapshot:
    timestamp: float

    # --- Kernel metrics ---
    system_status: str
    market_state: str
    trading_state: str
    system_state: str
    today_session: Optional[SessionSnapshot]
    db_status: str
    runtime_threads: int
    active_sessions: int
    market_streaming: bool

    # --- IBKR metrics ---
    ibkr_clients_connected: int = 0
    ibkr_orders_tracked: int = 0
    ibkr_last_tick_gap: Optional[float] = None
    ibkr_tick_rate: float = 0.0
    ibkr_subscribed_contracts: int = 0

    # --- Order metrics ---
    pending_orders_count: int = 0



    def as_dict(self):
        return asdict(self)

