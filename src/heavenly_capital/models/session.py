from dataclasses import dataclass
from typing import Any, Dict


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
    portfolios: tuple["PortfolioConfig", ...] = ()
    context: Dict[str, Any] = None

    @classmethod
    def create(
        cls,
        session_name: str,
        account_id: str,
        mode: str,
        portfolios: tuple["PortfolioConfig", ...],
        context: Dict[str, Any] = None
    ) -> "TradingSessionConfig":

        return cls(
            session_name=session_name,
            account_id=account_id,
            mode=mode,
            context=context,
            portfolios=portfolios
        )

    @classmethod
    def from_persistence(cls, row: dict, db: "TradingSessionDB") -> "TradingSessionConfig":
        portfolios = tuple(
            PortfolioConfig(**p) for p in db.fetch_portfolios(account_id=row["account_id"])
        )
        return cls(
            session_name=row["session_name"],
            account_id=row["account_id"],
            mode=row["mode"],
            portfolios=portfolios,
        )


@dataclass(frozen=True, slots=True)
class SessionConfig:
    sessions: tuple["TradingSessionConfig", ...]