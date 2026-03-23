from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Dict, Tuple

from sqlalchemy import RowMapping
from uuid import UUID


class SessionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class SessionPhase(StrEnum):
    STRATEGIC_SETUP = "STRATEGIC_SETUP"
    PRE_MARKET = "PRE_MARKET"
    IN_MARKET = "IN_MARKET"
    POST_MARKET = "POST_MARKET"

class SessionState(StrEnum):
    DONE = "DONE"
    RUNNING = "RUNNING"



@dataclass(slots=True)
class MarketDaySession:
    session_id: UUID
    session_date: date
    status: SessionStatus
    phase: SessionPhase
    state: SessionState
    error: bool = False

    @classmethod
    def from_database(cls, row: RowMapping) -> "MarketDaySession":
        return cls(
            session_id=UUID(row["session_id"]) if isinstance(row["session_id"], str) else row["session_id"],
            session_date=row["session_date"],
            status=SessionStatus(row["status"]),
            phase=SessionPhase(row["phase"]),
            state=SessionState(row["state"]),
            error=row["error"]
        )



@dataclass(frozen=True, slots=True)
class PortfolioConfig:
    portfolio_id: str
    account_id: str
    strategy_id: str
    portfolio_name: str


@dataclass(frozen=True, slots=True)
class TradingSessionConfig:
    session_name: str
    account_id: str
    mode: str
    portfolios: Tuple[Any, ...] = field(default_factory=tuple)  # PortfolioConfig attendue
    context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_database(cls, row: dict) -> "TradingSessionConfig":
        portfolios = tuple(
            PortfolioConfig(**p) for p in row.get("portfolios", ())
        )
        return cls(
            session_name=row["session_name"],
            account_id=row["account_id"],
            mode=row["mode"],
            portfolios=portfolios,
            context=row.get("context") or {}
        )


