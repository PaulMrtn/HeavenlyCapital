Portfolio(
    account_id='DUO800430',
    portfolio_id='portfolio_01',
    base_currency='USD',
    balance=PortfolioBalance(
        cash=Decimal('299695.4614'),
        stock_market_value=Decimal('0.0000'),
        unrealized_pnl=Decimal('0.0000'),
        total_commission=Decimal('0')),

    positions={3691937: Position(symbol='AMZN', quantity=Decimal('1424.000'), avg_price=Decimal('210.8411'), market_price=Decimal('210.12'), market_value=Decimal('299210.88000'), unrealized_pnl=Decimal('-1026.8464000'), updated_at=datetime.datetime(2026, 3, 9, 16, 15, 21, 320990, tzinfo=datetime.timezone.utc))})



Portfolio(
    account_id='DUO800430',
    portfolio_id='portfolio_01',
    base_currency='USD',
    balance=PortfolioBalance(
        cash=Decimal('246.4916530'),
        stock_market_value=Decimal('0.0000'),
        unrealized_pnl=Decimal('0.0000'),
        total_commission=Decimal('37.2176799999999968')),
    positions={10098:
                   Position(symbol='BAC', quantity=Decimal('2536.0'), avg_price=Decimal('47.23'), market_price=Decimal('47.22'), market_value=Decimal('119749.920'), unrealized_pnl=Decimal('-25.360'), updated_at=datetime.datetime(2026, 3, 9, 16, 15, 31, 66410, tzinfo=datetime.timezone.utc)), 8894: Position(symbol='KO', quantity=Decimal('1548.0'), avg_price=Decimal('77.34'), market_price=Decimal('77.32'), market_value=Decimal('119691.360'), unrealized_pnl=Decimal('-30.960'), updated_at=datetime.datetime(2026, 3, 9, 16, 15, 31, 66410, tzinfo=datetime.timezone.utc)), 15124833: Position(symbol='NFLX', quantity=Decimal('1223.0'), avg_price=Decimal('97.881169'), market_price=Decimal('97.85'), market_value=Decimal('119670.550'), unrealized_pnl=Decimal('-38.1196870'), updated_at=datetime.datetime(2026, 3, 9, 16, 15, 31, 322971, tzinfo=datetime.timezone.utc)), 13272: Position(symbol='UNH', quantity=Decimal('423.0'), avg_price=Decimal('282.78922'), market_price=Decimal('282.63'), market_value=Decimal('119552.490'), unrealized_pnl=Decimal('-67.350060'), updated_at=datetime.datetime(2026, 3, 9, 16, 15, 31, 66410, tzinfo=datetime.timezone.utc)), 38685693: Position(symbol='MA', quantity=Decimal('234.0'), avg_price=Decimal('512.11'), market_price=Decimal('511.89'), market_value=Decimal('119782.260'), unrealized_pnl=Decimal('-51.480'), updated_at=datetime.datetime(2026, 3, 9, 16, 15, 28, 840127, tzinfo=datetime.timezone.utc))})




# UPDATE_INTERVAL = 5
# def refresh_market_data(self, current_time: float) -> None:
#     current_interval = int(current_time) // UPDATE_INTERVAL
#
#     if current_interval != self._last_update_interval:
#         self._last_update_interval = current_interval
#
#         market_snapshot = {
#             ticker.contract.conId: cast(float, ticker.last)
#             for ticker in self._tickers.values()
#             if ticker.last is not None and ticker.last != -1
#         }
#
#         tsDB.update_market_data_in_db(market_snapshot)