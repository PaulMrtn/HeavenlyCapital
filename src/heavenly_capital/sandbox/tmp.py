from heavenly_capital.core.market_calendar import USMarketsCalendar
from heavenly_capital.core.market_clock import MarketClock, AcceleratedTimeHeartbeat
from heavenly_capital.core.system_manager import SystemManager

from heavenly_capital.data.data_access import InMemorySessionDAL
from heavenly_capital.data.data_ingestion import InMemorySessionDIL


from heavenly_capital.monitoring.health_service import build_readiness_checks


checks = build_readiness_checks(db_connector=None, ibkr_gateway=None, eodhd_client=None)


# heartbeat = SystemTimeHeartbeat()
sim_heartbeat = AcceleratedTimeHeartbeat()

market_clock = MarketClock(time_source=sim_heartbeat)
market_calendar = USMarketsCalendar()

data_ingestion = InMemorySessionDIL()
data_access = InMemorySessionDAL()


system_manager = SystemManager(market_clock=market_clock,
                               market_calendar=market_calendar,
                               data_ingestion=data_ingestion,
                               data_access=data_access)


# system_manager._market_clock.start()

system_manager._prepare_bootstrap(checks=checks)

system_manager.launch_global_runtime()






