from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

import os
import subprocess
from pathlib import Path



def load_env(dotenv_path: Path):
    if not dotenv_path.exists():
        raise FileNotFoundError(f"{dotenv_path} doesn't exist")

    with dotenv_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            os.environ.setdefault(key, value)


def get_env(key: str, cast=None):
    value = os.getenv(key)
    if cast and value is not None:
        try:
            value = cast(value)
        except Exception as e:
            raise ValueError(f"Unable to cast {key} to {cast}: {e}")
    return value


def get_keychain_password(account: str, service: str) -> str:
    result = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()



class DBConfig:
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
            cls.__instance._init()
        return cls.__instance

    def _init(self):
        self.user = get_env("DB_USER")
        self.host = get_env("DB_HOST")
        self.port = get_env("DB_PORT", cast=int)
        self.name = get_env("DB_NAME")
        self.pool_size = get_env("DB_POOL_SIZE", cast=int) or 10
        self.max_overflow = get_env("DB_MAX_OVERFLOW", cast=int) or 20
        self.pool_recycle = get_env("DB_POOL_RECYCLE", cast=int) or 3600
        self.pool_pre_ping = True

        self.__password = get_keychain_password(self.user, "trading_db")

    def get_password(self):
        return self.__password




class DBConnector:
    def __init__(self, config: DBConfig):
        self._engine: Engine = create_engine(
            f"postgresql+psycopg2://{config.user}:{config.get_password()}@"
            f"{config.host}:{config.port}/{config.name}",
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=config.pool_pre_ping,
            future=True,
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        conn = self._engine.connect()
        try:
            yield conn
        finally:
            conn.close()


    def uow(self):
        return UnitOfWork(self._engine)


class UnitOfWork:
    def __init__(self, engine: Engine):
        self._engine = engine

    def __enter__(self) -> Connection:
        self.conn = self._engine.connect()
        self.trans = self.conn.begin()
        return self.conn

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            self.trans.rollback()
        else:
            self.trans.commit()
        self.conn.close()



class DuckDBConnector:
    def __init__(self, db_path: Path):
        import duckdb
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(db_path))

    @property
    def conn(self):
        return self._conn

    def execute(self, query: str, parameters=None):
        if parameters:
            return self._conn.execute(query, parameters)
        return self._conn.execute(query)

    def executemany(self, query: str, parameters_list):
        return self._conn.executemany(query, parameters_list)

    def fetchall(self, query: str):
        return self._conn.execute(query).fetchall()


def create_duckdb_connector(db_name: str = "market_data_lab_dev.duckdb"):
    base_path = Path(__file__).resolve().parent.parent / "storage"
    db_path = base_path / db_name
    return DuckDBConnector(db_path)



ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_env(ENV_PATH)

DB_CONFIG = DBConfig()
DB_CONNECTOR = DBConnector(DB_CONFIG)