from src.core.market_calendar import USMarketsCalendar
from src.core.market_clock import MarketClock, AcceleratedTimeHeartbeat
from src.core.system_manager import SystemManager

from src.data.data_access import InMemorySessionDAL
from src.data.data_ingestion import InMemorySessionDIL


from src.monitoring.health_checks import build_readiness_checks


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






