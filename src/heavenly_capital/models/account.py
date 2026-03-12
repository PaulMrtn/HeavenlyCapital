from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class BalanceState:
    total_cash_balance: Optional[float] = None
    accrued_cash: Optional[float] = None
    net_liquidation_by_currency: Optional[float] = None
    # USD only
    stock_market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    exchange_rate: Optional[float] = None
    net_dividend: Optional[float] = None


@dataclass
class MarginState:
    cushion: Optional[float] = None
    lookahead_next_change: Optional[int] = None
    buying_power: Optional[float] = None
    equity_with_loan: Optional[float] = None
    full_available_funds: Optional[float] = None
    full_excess_liquidity: Optional[float] = None
    full_init_margin_req: Optional[float] = None
    full_maint_margin_req: Optional[float] = None


@dataclass
class AccountState:
    account: str
    net_liquidation: Optional[float] = None
    total_cash_value: Optional[float] = None
    gross_position_value: Optional[float] = None
    margin: Optional[MarginState] = None
    balances: Dict[str, BalanceState] = field(default_factory=dict)

    @classmethod
    def from_account_summary(cls, values):
        account_id = None
        account_data = {}
        margin_data = {}
        balances: Dict[str, BalanceState] = {}

        account_fields = {
            "NetLiquidation": "net_liquidation",
            "TotalCashValue": "total_cash_value",
            "GrossPositionValue": "gross_position_value",
        }

        margin_fields = {
            "Cushion": "cushion",
            "LookAheadNextChange": "lookahead_next_change",
            "BuyingPower": "buying_power",
            "EquityWithLoanValue": "equity_with_loan",
            "FullAvailableFunds": "full_available_funds",
            "FullExcessLiquidity": "full_excess_liquidity",
            "FullInitMarginReq": "full_init_margin_req",
            "FullMaintMarginReq": "full_maint_margin_req",
        }

        balance_fields_common = {
            "TotalCashBalance": "total_cash_balance",
            "AccruedCash": "accrued_cash",
            "NetLiquidationByCurrency": "net_liquidation_by_currency",
        }

        balance_fields_usd_extra = {
            "StockMarketValue": "stock_market_value",
            "UnrealizedPnL": "unrealized_pnl",
            "RealizedPnL": "realized_pnl",
            "ExchangeRate": "exchange_rate",
            "NetDividend": "net_dividend",
        }

        for v in values:
            if v.currency == "BASE":
                continue

            if v.account != "All":
                account_id = v.account

            try:
                value = float(v.value)
            except (ValueError, TypeError):
                value = None

            if v.tag == "LookAheadNextChange":
                value = int(v.value)
                if value == 0:
                    value = None

            if v.account != "All" and v.tag in account_fields:
                account_data[account_fields[v.tag]] = value

            if v.account != "All" and v.tag in margin_fields:
                margin_data[margin_fields[v.tag]] = value

            if v.account == "All" and v.currency in ("EUR", "USD"):
                if v.currency not in balances:
                    balances[v.currency] = BalanceState()

                c = balances[v.currency]

                if v.tag in balance_fields_common:
                    setattr(c, balance_fields_common[v.tag], value)

                if v.currency == "USD" and v.tag in balance_fields_usd_extra:
                    setattr(c, balance_fields_usd_extra[v.tag], value)

        margin = MarginState(**margin_data) if margin_data else None

        return cls(
            account=account_id,
            net_liquidation=account_data.get("net_liquidation"),
            total_cash_value=account_data.get("total_cash_value"),
            gross_position_value=account_data.get("gross_position_value"),
            margin=margin,
            balances=balances,
        )

    def apply_usd_exchange_rate(self) -> None:
        usd_balance = self.balances.get("USD")
        if not usd_balance or usd_balance.exchange_rate is None:
            return

        rate = usd_balance.exchange_rate

        fields = [
            "net_liquidation",
            "total_cash_value",
            "gross_position_value",
        ]

        for f in fields:
            val = getattr(self, f)
            if val is not None:
                setattr(self, f, val * rate)

        if self.margin:
            margin_fields = [
                "buying_power",
                "equity_with_loan",
                "full_available_funds",
                "full_excess_liquidity",
                "full_init_margin_req",
                "full_maint_margin_req",
            ]

            for f in margin_fields:
                val = getattr(self.margin, f)
                if val is not None:
                    setattr(self.margin, f, val * rate)