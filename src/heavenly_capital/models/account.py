from dataclasses import dataclass, field
from numpy import nan
from typing import Dict

@dataclass
class MarginInfo:
    init: float = nan
    maint: float = nan
    full_init: float = nan
    full_maint: float = nan
    excess: float = nan
    lookahead_available: float = nan
    lookahead_excess: float = nan

@dataclass
class PnLInfo:
    unrealized: float = nan
    realized: float = nan

@dataclass
class CurrencyInfo:
    cash_balance: float = nan
    total_cash_balance: float = nan
    net_liquidation: float = nan
    accrued_cash: float = nan
    exchange_rate: float = nan
    real_currency: str = ""

@dataclass
class AccountState:
    account: str
    account_type: str = ""
    cushion: float = nan
    net_liquidation: float = nan
    total_cash_value: float = nan
    available_funds: float = nan
    buying_power: float = nan
    gross_position_value: float = nan
    margin: MarginInfo = field(default_factory=MarginInfo)
    pnl: PnLInfo = field(default_factory=PnLInfo)
    currencies: Dict[str, CurrencyInfo] = field(default_factory=dict)

    @classmethod
    def from_account_values(cls, values):
        account_id = None
        data = {}
        currencies: Dict[str, CurrencyInfo] = {}

        for v in values:
            if v.account == "All":
                continue

            account_id = v.account
            value = float(v.value) if v.value.replace('.', '', 1).isdigit() else v.value

            if v.tag in (
                "AccountType", "Cushion", "NetLiquidation", "TotalCashValue",
                "AvailableFunds", "BuyingPower", "GrossPositionValue",
                "InitMarginReq", "MaintMarginReq", "FullInitMarginReq",
                "FullMaintMarginReq", "ExcessLiquidity", "LookAheadAvailableFunds",
                "LookAheadExcessLiquidity", "UnrealizedPnL", "RealizedPnL", "AccruedCash"
            ):
                data[v.tag] = value
            else:
                # Attributs par devise
                if v.account not in currencies:
                    currencies[v.account] = CurrencyInfo()
                ccy_info = currencies[v.account]
                if hasattr(ccy_info, v.tag.lower()):
                    setattr(ccy_info, v.tag.lower(), value)

        return cls(
            account=account_id,
            account_type=data.get("AccountType", ""),
            cushion=data.get("Cushion", nan),
            net_liquidation=data.get("NetLiquidation", nan),
            total_cash_value=data.get("TotalCashValue", nan),
            available_funds=data.get("AvailableFunds", nan),
            buying_power=data.get("BuyingPower", nan),
            gross_position_value=data.get("GrossPositionValue", nan),
            margin=MarginInfo(
                init=data.get("InitMarginReq", nan),
                maint=data.get("MaintMarginReq", nan),
                full_init=data.get("FullInitMarginReq", nan),
                full_maint=data.get("FullMaintMarginReq", nan),
                excess=data.get("ExcessLiquidity", nan),
                lookahead_available=data.get("LookAheadAvailableFunds", nan),
                lookahead_excess=data.get("LookAheadExcessLiquidity", nan),
            ),
            pnl=PnLInfo(
                unrealized=data.get("UnrealizedPnL", nan),
                realized=data.get("RealizedPnL", nan),
            ),
            currencies=currencies
        )


