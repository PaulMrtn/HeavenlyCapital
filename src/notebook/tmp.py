from src.core.market_clock import MarketClock, AcceleratedTimeHeartbeat
from src.core.system_manager import SystemManager, ExitCode
from src.monitoring.health_checks import IBKRReadinessCheck

# heartbeat = SystemTimeHeartbeat()
sim_heartbeat = AcceleratedTimeHeartbeat()

market_clock = MarketClock(time_source=sim_heartbeat)

system_manager = SystemManager(market_clock=market_clock)

system_manager.shutdown(ExitCode.MARKET_CLOSED_TODAY, detail="The market is closed today.")

system_manager