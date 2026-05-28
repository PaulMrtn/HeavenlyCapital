<p align="center">
  <img src="img/logo.png" alt="HeavenlyCapital Logo" width="600">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-in%20development-orange" alt="Status">
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python">
  <img src="https://img.shields.io/badge/broker-Interactive%20Brokers-red" alt="Broker">
  <img src="https://img.shields.io/badge/market-US%20Equities-green" alt="Market">
  <img src="https://img.shields.io/badge/license-Private-lightgrey" alt="License">
</p>

---

> **⚠️ Work in Progress** — This project is under active development. The core infrastructure is in place but trading strategies are not yet fully integrated. It is not ready for production use. For installation help or questions, feel free to [open an issue](https://github.com/PaulMrtn/HeavenlyCapital/issues).

---

## Overview

**HeavenlyCapital** is a Python-based algorithmic trading system built on top of the Interactive Brokers (IBKR) API, designed for **live automated trading on US equity markets**.

The system is built around a modular, event-driven architecture with a strict separation between three independent layers:

- **Infrastructure** — real-time market data ingestion, multi-frequency OHLC aggregation, order execution, portfolio management, and full PostgreSQL persistence
- **Strategy** — a plug-and-play forecasting pipeline that loads trained models (`.pkl`) from the database and routes signals to the appropriate portfolios
- **Research** — a separate offline quantitative research environment (Polars, DuckDB, XGBoost) for developing and validating intraday strategies, independent from the live infrastructure

The architecture is designed so that any strategy can be integrated without modifying the infrastructure — models are registered in the database, assigned to portfolios, and consumed by the forecasting engine at runtime.

---

## Features

### ✅ Infrastructure — ~80% complete

**Core engine**
- Event-driven kernel with market state machine (PRE_MARKET → OPEN → POST_MARKET → CLOSED)
- Internal clock with accelerated time simulation for development
- NYSE trading calendar integration
- Managed thread pool with job queues and graceful shutdown

**Market data pipeline**
- Real-time tick ingestion from IBKR with multi-session support
- OHLC aggregation at 5s intervals (last, bid, ask)
- Multi-frequency resampling cascade (5s → 30s → 1m → 5m → 10m → 30m → 1h) without redundant computation
- Ring buffer (numpy) per instrument and frequency for efficient feature computation
- Structured `CandleEvent` bus connecting the data layer to the strategy layer

**IBKR integration**
- Multi-client session management (LIVE and PAPER simultaneously)
- Real-time streaming with tick rate monitoring and last-tick gap tracking
- Order placement (Market, Limit) with full lifecycle tracking (CREATED → SUBMITTED → PARTIALLY_FILLED → FILLED)
- Order, fill, and commission event handling
- Account state synchronization from IBKR servers

**Trading engine**
- Isolated `TradingSession` per portfolio with decoupled `OrderManager`, `PortfolioManager`, and `RiskManager` communicating through an internal message router
- Portfolio mark-to-market in real time from live tickers
- Rebalancing engine — computes order deltas from target weights stored in the database
- Global order router with live/paper queue prioritization
- Full order lifecycle persistence (orders, fills, commissions, positions, P&L)

**Forecasting pipeline**
- Model registry loaded from the database at startup (name, type, version, path)
- Supports 3 model types per portfolio: `BUY`, `SELL`, `STOP_LOSS`
- Feature plugin system — features are registered via decorator and computed on demand from the market data banks
- Signal routing by portfolio — each signal is published only to the portfolios that hold a position in the instrument
- Decision records persisted asynchronously to the database

**Session & portfolio management**
- Paper and live trading modes
- Multi-portfolio support per account
- Capital event tracking (initial capital, additions, withdrawals)
- Portfolio balance and position reconciliation

**Persistence**
- Full PostgreSQL schema (`sql/` folder)
- Asynchronous batch writes via a dedicated DB writer thread
- Structured logging to database (domain, event, metadata, timestamp)

**Monitoring**
- Real-time console dashboard (Rich) with kernel snapshot, market state, session status
- Structured log service with async batch persistence
- Health check framework on all runtime modules
- Null implementations for metrics and notifications (ready for integration)

### 🔄 In progress

- `RiskManager` — stop loss implementation
- Full end-to-end integration of quantitative research models
- Docker-based setup for PostgreSQL (schema + tables pre-configured)

### 🔜 Planned

- Backtesting module
- Portfolio construction (mean-variance, risk parity)
- Automated daily reconciliation (positions DB vs IBKR)
- Reporting & P&L dashboard
- CI/CD pipeline

---

## Project Structure

```
heavenly_capital/
│
├── core/
│   ├── calendar.py           # NYSE trading calendar
│   ├── clock.py              # Market state machine & time simulation
│   ├── kernel.py             # Central orchestration engine
│   └── thread.py             # Managed thread pool
│
├── data/
│   ├── bus.py                # Thread-safe event bus (pub/sub)
│   ├── historic.py           # Multi-frequency resampling & candle store
│   └── live.py               # Real-time tick ingestion & OHLC aggregation
│
├── db/
│   ├── connector.py          # PostgreSQL connector & unit of work
│   ├── reader.py             # Data access layer (read)
│   └── writer.py             # Data ingestion layer (write)
│
├── ibkr/
│   ├── client.py             # IBKR client sessions & streaming
│   └── gateway.py            # Order gateway, account sync, contract management
│
├── models/
│   ├── account.py            # Account & margin state
│   ├── config.py             # Runtime configuration
│   ├── market_data.py        # OHLC, CandleEvent, MarketDataBank (ring buffer)
│   ├── order.py              # Order lifecycle & state machine
│   ├── portfolio.py          # Portfolio, position & balance models
│   ├── risk.py               # Risk state & snapshot
│   ├── runtime.py            # Module contracts (Protocol, BaseModule, ModuleRouter)
│   ├── session.py            # Session & trading session config
│   ├── snapshot.py           # Kernel snapshot for monitoring
│   ├── system.py             # System state, ports, runtime registry
│   └── tickers.py            # Universe & instrument models
│
├── monitoring/
│   ├── error_service.py      # Error capture & reporting
│   ├── health_service.py     # Readiness checks
│   ├── log_service.py        # Async structured logging
│   ├── metric_service.py     # Metrics (extensible)
│   └── notification_service.py  # Alerts (extensible)
│
├── services/
│   ├── app.py                # SessionService — setup API (sessions, portfolios, models)
│   └── console.py            # Real-time terminal dashboard
│
├── strategy/
│   ├── artifacts.py          # FeatureSpec, ModelSpec, ModelSignal, DecisionRecord
│   ├── feature_engine.py     # Feature computation engine & FeatureStore
│   ├── features.py           # Feature plugin registry
│   └── forecast_engine.py    # Model loading, prediction, signal routing
│
├── trading/
│   ├── order_manager.py      # Order staging, authorization & routing
│   ├── portfolio_manager.py  # Portfolio state, rebalancing & mark-to-market
│   ├── risk_manager.py       # Risk controls (in progress)
│   ├── router.py             # Global order router (live/paper priority queue)
│   └── session_manager.py    # Trading session lifecycle
│
├── research/                 # Offline quantitative research (independent)
│   ├── data.py               # Intraday data loading (DuckDB + Polars)
│   └── intraday/
│       ├── features.py       # Incremental Polars feature expressions
│       ├── labels.py         # Regime labeling (Trend_Up / Mean_Reverting / Trend_Down)
│       ├── model.py          # XGBoost training & evaluation pipeline
│       ├── policy.py         # Entry policy simulation by regime
│       └── transforms.py     # OHLC normalization & true range
│
└── sql/                      # PostgreSQL schema & table definitions
```

---

## Prerequisites

Before using HeavenlyCapital, you need:

- **Python 3.12**
- **Interactive Brokers account** (paper or live) with TWS or IB Gateway running
- **IBKR API** enabled in TWS/Gateway settings (Edit → Global Configuration → API)
- **Market data subscription** — the API requires a Level 1 top-of-book subscription to receive real-time equity data. The relevant bundle is the **US Securities Snapshot and Futures Value Bundle** ($10/month for non-professional users, waived if you generate $30+/month in commissions). IBKR also requires a minimum of **$500 in your account** on top of any subscription fees.
  - By default, every account is limited to **100 simultaneous market data lines** (100 assets streamed at once). To exceed this limit, you can purchase **Quote Booster Packs** at **$30/month each** (100 additional lines per pack, max 10 packs per account). The limit also increases automatically based on account equity and monthly commissions.
  - Subscribe and manage via [Client Portal → Market Data Subscriptions](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php).
- **A running PostgreSQL database instance** with the required schema and tables pre-created. The SQL scripts are located in the [`sql/`](./sql/) folder. The database connection is configured via a `.env` file.
  > 🐳 A Docker image with a pre-configured PostgreSQL instance (schema + tables included) is currently in development and will be available in a future release to simplify the setup process.
- **Trained forecast models** (`.pkl` files) if using the strategy layer. The system requires **3 models per portfolio** — one for each signal type: `BUY`, `SELL`, and `STOP_LOSS` — each registered and assigned before the system can generate signals.
  > 📖 A tutorial on how to build your own intraday execution optimization strategy and train compatible forecast models is currently in development.

> This system is designed for users familiar with algorithmic trading, the IBKR ecosystem, and quantitative finance. It is not a plug-and-play solution.

---

## Installation

```bash
git clone https://github.com/PaulMrtn/HeavenlyCapital.git
cd HeavenlyCapital
pip install -r requirements.txt
```

---

## Database Setup

HeavenlyCapital requires a running PostgreSQL instance with the schema initialized before starting the system. The SQL scripts are located in the [`sql/`](./sql/) folder.

1. Create a PostgreSQL database
2. Run the SQL scripts from the `sql/` folder to create the required tables
3. Configure the connection in your `.env` file

> 🐳 A Docker-based setup is coming soon to automate this step entirely.

---

## Setup — Sessions, Portfolios & Models

Before running the system, use the `SessionService` to configure accounts, portfolios, and forecast models in the database.

```python
from heavenly_capital.services.app import SessionService
from decimal import Decimal

service = SessionService()

# Create a trading session for an IBKR account
service.create_session(
    session_name="MySession",
    account_id="ACC123",
    mode="PAPER"  # or "LIVE"
)

# Create a portfolio with initial capital
service.create_portfolio(
    account_id="ACC123",
    strategy_id="STRAT001",
    portfolio_id="PORT001",
    portfolio_name="MyPortfolio",
    cash_amount=Decimal("10000.0"),
    currency="USD",
    enabled=True
)

# Register capital events
service.register_capital_event(
    account_id="ACC123",
    portfolio_id="PORT001",
    event="INITIAL_CAPITAL",  # "INITIAL_CAPITAL" | "CAPITAL_ADDITION" | "CAPITAL_WITHDRAWAL"
    amount=Decimal("10000.0"),
    currency="USD"
)

# Register forecast models (3 required per portfolio: BUY, SELL, STOP_LOSS)
service.set_model(
    model_name="BuyModelV1",
    model_type="BUY",
    version=1.0,
    path="/models/buy_v1.pkl",
    description="Intraday buy signal — XGBoost regime classifier",
    enabled=True
)

# Assign models to a portfolio
service.assign_model_to_portfolio(
    portfolio_id="PORT001",
    model_name="BuyModelV1",
    model_type="BUY",
    version=1.0
)
```

> In **LIVE** mode, the initial capital is fetched directly from IBKR servers and does not need to be specified manually.

---

## Roadmap

| Status | Milestone |
|---|---|
| ✅ Done | Core engine — market state machine, clock, thread pool |
| ✅ Done | Real-time data pipeline — tick ingestion, OHLC aggregation, multi-frequency resampling |
| ✅ Done | IBKR integration — multi-session, streaming, order execution |
| ✅ Done | Trading engine — order lifecycle, portfolio management, order routing |
| ✅ Done | Forecasting pipeline — feature engine, model registry, signal routing |
| ✅ Done | Full PostgreSQL persistence — orders, fills, positions, P&L, logs |
| ✅ Done | Session & portfolio management — paper/live, capital events, multi-portfolio |
| 🔄 In progress | Risk manager — stop loss implementation |
| 🔄 In progress | Quantitative research integration |
| 🔄 In progress | Docker setup for PostgreSQL |
| 🔜 Planned | Backtesting module |
| 🔜 Planned | Portfolio construction (optimization) |
| 🔜 Planned | Automated daily reconciliation |
| 🔜 Planned | Reporting & P&L dashboard |
| 🔜 Planned | CI/CD pipeline |

---

## Disclaimer

This project is developed for **personal capital management**. It is not financial advice and is not intended for third-party use. Live trading involves significant financial risk. Use at your own risk.

---

## Author

**Paul Martin** — [GitHub](https://github.com/PaulMrtn)
