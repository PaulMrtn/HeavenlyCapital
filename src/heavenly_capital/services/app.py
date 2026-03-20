from decimal import Decimal
from typing import Optional, Dict, Any

from heavenly_capital.data.db_mock import TradingSessionDB


class SessionService:

    def __init__(self, db: TradingSessionDB):
        self._db = db

    def create_session(
            self,
            session_name: str,
            account_id: str,
            mode: str,
            context: Dict[str, Any] = None,
    ) -> None:

        if self._db.session_exists_for_account(account_id):
            raise ValueError(
                f"A session already exists for account_id={account_id}"
            )

        self._db.insert_session(session_name, account_id, mode, context)

    def create_portfolio(
            #TODO:LOW - ADD constraint on account capital
            self,
            account_id: str,
            strategy_id: str,
            portfolio_id: str,
            portfolio_name: str,
            cash_amount: Optional[Decimal | float] = None,
            currency: str = "USD",
            enabled: bool = True,
    ) -> None:

        sessions = self._db.fetch_sessions_by_account(account_id)
        if not sessions:
            raise ValueError(f"No session found for account_id={account_id}")

        session_mode = sessions[0].mode.upper()

        if self._db.exists_for_portfolio(portfolio_id):
            raise ValueError(
                f"Portfolio id '{portfolio_id}' already exists in the database"
            )

        self._db.insert_portfolio(
            account_id, strategy_id, portfolio_id, portfolio_name, currency, enabled
        )

        if session_mode == "LIVE":
            cash_amount = self._db.get_account_total_cash(account_id, currency)
            if cash_amount is None:
                raise ValueError(
                    f"No total_cash_balance found for LIVE account {account_id} in {currency}"
                )
        else:
            if cash_amount is None:
                raise ValueError(
                    "cash_amount must be specified when creating a PAPER session"
                )

        self.register_capital_event(
            account_id=account_id,
            portfolio_id=portfolio_id,
            event="INITIAL_CAPITAL",
            amount=Decimal(cash_amount),
            currency=currency
        )

    def register_capital_event(
            self,
            account_id: str,
            portfolio_id: str,
            event: str,  # "INITIAL_CAPITAL", "CAPITAL_ADDITION", "CAPITAL_WITHDRAWAL"
            amount: Decimal,
            currency: str = "USD"
    ) -> None:

        self._db.insert_capital_event(
            account_id=account_id,
            portfolio_id=portfolio_id,
            event=event,
            amount=amount,
            currency=currency
        )

        self._db.update_portfolio_balances(
            account_id=account_id,
            portfolio_id=portfolio_id,
            currency=currency
        )

    def delete_portfolio(
            self,
            account_id: str,
            portfolio_id: str,
    ) -> None:

        if not self._db.exists_for_portfolio(portfolio_id):
            raise ValueError(
                f"No portfolio with id '{portfolio_id}' exists in the database"
            )

        deleted = self._db.delete_portfolio(account_id, portfolio_id)
        if not deleted:
            raise ValueError(
                f"No portfolio named '{portfolio_id}' found for account_id={account_id}"
            )

    def is_portfolio_enabled(self, portfolio_id: str) -> bool:
        if not self._db.exists_for_portfolio(portfolio_id):
            raise ValueError(
                f"No portfolio with id '{portfolio_id}' exists in the database"
            )

        return self._db.portfolio_is_enabled(portfolio_id)


    def set_model(
            self,
            model_name: str,
            model_type: str,
            version: float,
            path: str,
            description: Optional[str],
            enabled: bool = True
    ) -> None:

        if version is None:
            raise ValueError("version must be provided")
        if model_type not in ("BUY", "SELL", "STOP_LOSS"):
            raise ValueError(f"Invalid model_type {model_type}")

        self._db.update_forecast_model(
            model_name=model_name,
            model_type=model_type,
            version=version,
            path=path,
            description=description,
            enabled=enabled
        )


    def assign_model_to_portfolio(
            self,
            portfolio_id: str,
            model_name: str,
            model_type: str,
            version: float
    ) -> None:

        if not self._db.portfolio_is_enabled(portfolio_id):
            raise ValueError(f"Portfolio {portfolio_id} does not exist or is disabled")

        if not self._db.model_is_enabled(model_name, version):
            raise ValueError(f"Model {model_name} v{version} does not exist or is disabled")

        self._db.update_portfolio_model(
            portfolio_id=portfolio_id,
            model_name=model_name,
            model_type=model_type,
            version=version
        )


    def add_feature(
        self,
        uid: str,
        category: str,
        plugin: str,
        scope: str,
        kind: str,
        fields: str,
        freqs: list[str],
        priority: int,
        params: Optional[Dict[str, Any]] = None,
        cache: bool = False,
        is_active: bool = True,
    ) -> None:

        if self._db.feature_exists(uid):
            raise ValueError(f"Feature with uid '{uid}' already exists in DB")

        params = params or {}
        self._db.insert_feature(
            uid=uid,
            category=category,
            plugin=plugin,
            scope=scope,
            kind=kind,
            fields=fields,
            freqs=freqs,
            params=params,
            priority=priority,
            cache=cache,
            is_active=is_active
        )

    def activate_feature(self, uid: str) -> None:
        if not self._db.feature_exists(uid):
            raise ValueError(f"No feature with uid '{uid}' in DB")

        self._db.update_feature_status(uid, True)

    def deactivate_feature(self, uid: str) -> None:
        if not self._db.feature_exists(uid):
            raise ValueError(f"No feature with uid '{uid}' in DB")

        self._db.update_feature_status(uid, False)