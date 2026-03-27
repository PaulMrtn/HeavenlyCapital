# monitoring/health_service.py

from dataclasses import field, dataclass
from datetime import datetime, timezone
from typing import Protocol, List


@dataclass(slots=True)
class ConnectionStatus:
    name: str
    status: bool
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class ReadinessCheck(Protocol):
    name: str
    def ping(self) -> ConnectionStatus: ...


class DatabaseReadinessCheck:
    name = "Database"
    def __init__(self, db_connector=None):
        self.db_connector = db_connector
    def ping(self) -> ConnectionStatus:
        return ConnectionStatus(name=self.name, status=True)


class IBKRReadinessCheck:
    name = "Interactive Brokers"
    def __init__(self, ibkr_gateway=None):
        self.ibkr_gateway = ibkr_gateway
    def ping(self) -> ConnectionStatus:
        return ConnectionStatus(name=self.name, status=True)


class EODHDReadinessCheck:
    name = "EODHD"
    def __init__(self, eodhd_client=None):
        self.eodhd_client = eodhd_client
    def ping(self) -> ConnectionStatus:
        return ConnectionStatus(name=self.name, status=True)


def build_readiness_checks(db_connector, ibkr_gateway, eodhd_client) -> List[object]:
    return [
        DatabaseReadinessCheck(db_connector=db_connector),
        IBKRReadinessCheck(ibkr_gateway=ibkr_gateway),
        EODHDReadinessCheck(eodhd_client=eodhd_client),
    ]





    # def run_readiness_checks(self, checks: Iterable[ReadinessCheck]) -> list[ConnectionStatus]:
    #     results: list[ConnectionStatus] = []
    #     try:
    #         for check in checks:
    #             results.append(check.ping())
    #     except Exception:
    #         self._set_status(SystemStatus.ERROR)
    #         return results
    #
    #     con_status = all(r.status for r in results)
    #     self._set_status(SystemStatus.READY if con_status else SystemStatus.ERROR)
    #     return results
