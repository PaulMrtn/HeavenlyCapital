<p align="center">
  <img src="img/logo.png" alt="HeavenlyCapital Logo" width="600">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-in%20development-orange" alt="Status">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/broker-Interactive%20Brokers-red" alt="Broker">
  <img src="https://img.shields.io/badge/market-Equities-green" alt="Market">
  <img src="https://img.shields.io/badge/license-Private-lightgrey" alt="License">
</p>

---

> ⚠️ **Work in Progress** — This project is under active development. The core
> infrastructure is in place but trading strategies are not yet integrated. It is
> not ready for production use. For installation help or questions, feel free to
> [open an issue](https://github.com/PaulMrtn/HeavenlyCapital/issues).

---

## Overview

**HeavenlyCapital** is a Python-based algorithmic trading system built on top of the Interactive Brokers (IBKR) API. It provides a full infrastructure for **live automated trading on equity markets**, from real-time market data ingestion to order execution and portfolio management.

The system is designed around a modular, event-driven architecture with a strong emphasis on:
- Clean separation between infrastructure, strategy, and execution layers
- Robust monitoring and error handling for live trading environments
- A forecasting pipeline ready to plug in quantitative research models (ML/statistical)
- Support for both **paper trading** and **live trading** modes

The quantitative research layer (asset selection, signal generation, intraday execution logic) is developed separately and will be integrated into the `strategy/` module in a future release.

---

## Features

### ✅ Implemented
- **Core engine** — internal clock, calendar, thread pool management
- **Data layer** — real-time market data feed and historical data access
- **IBKR integration** — client connection and order gateway via TWS/IB Gateway
- **Database layer** — full read/write connector for persistence
- **Trading engine** — order manager, portfolio manager, risk manager, order router, session manager
- **Monitoring** — health checks, logging, metrics, error handling, notifications
- **Session & portfolio management** — paper and live modes, capital events, multi-portfolio support
- **Forecast pipeline** — feature engineering infrastructure and model lifecycle management (create, version, assign to portfolio)

### 🔜 Planned
- Integration of quantitative research models (signal generation, asset selection)
- Intraday execution strategy layer
- Backtesting module
- Dashboard / reporting interface

---

## Project Structure

```
heavenly_capital/
│
├── core/
│   ├── calendar.py           # Internal trading calendar
│   ├── clock.py              # System clock & synchronization
│   ├── kernel.py             # Central engine logic
│   └── thread.py             # Thread and pool management
│
├── data/
│   ├── bus.py                # Central data communication bus
│   ├── historic.py           # Historical data access
│   └── live.py               # Real-time data feed
│
├── db/
│   ├── connector.py          # Database connection
│   ├── reader.py             # DB read operations
│   └── writer.py             # DB write operations
│
├── ibkr/
│   ├── client.py             # IBKR TWS/Gateway client
│   └── gateway.py            # Order gateway & management
│
├── models/
│   ├── account.py            # Account models
│   ├── config.py             # Configuration & parameters
│   ├── market_data.py        # Market data structures
│   ├── mock.py               # Mock data for testing
│   ├── order.py              # Order models
│   ├── portfolio.py          # Portfolio models
│   ├── risk.py               # Risk models
│   ├── runtime.py            # Runtime state
│   ├── session.py            # Session management
│   ├── system.py             # Global system configuration
│   └── tickers.py            # Instrument information
│
├── monitoring/
│   ├── error_service.py      # Error handling
│   ├── health_service.py     # System health monitoring
│   ├── log_service.py        # Logging
│   ├── metric_service.py     # Metrics & indicators
│   └── notification_service.py  # Alerts & notifications
│
├── services/
│   └── app.py                # Service entry point
│
├── strategy/
│   ├── artifacts.py          # Artifact management
│   ├── feature_manager.py    # Feature preparation pipeline
│   ├── features.py           # Feature computation
│   └── forecast_manager.py   # Forecasting engine
│
└── trading/
    ├── order_manager.py      # Order lifecycle management
    ├── portfolio_manager.py  # Portfolio management
    ├── risk_manager.py       # Risk tracking
    ├── router.py             # Order routing
    └── session_manager.py    # Trading session management
```

---

## Prerequisites

Before using HeavenlyCapital, you need:

- **Python 3.10+**
  
- **Interactive Brokers account** (paper or live) with TWS or IB Gateway running
  
- **IBKR API** enabled in TWS/Gateway settings (Edit → Global Configuration → API)
  
- **Market data subscription** — the API requires a Level 1 top-of-book subscription
  to receive real-time equity data. The relevant bundle is the **US Securities Snapshot
  and Futures Value Bundle** ($10/month for non-professional users, waived if you
  generate $30+/month in commissions). IBKR also requires a minimum of **$500 in your
  account** on top of any subscription fees.
  
  - By default, every account is limited to **100 simultaneous market data lines**
    (i.e. 100 assets streamed at once). To exceed this limit, you can purchase
    **Quote Booster Packs** at **$30/month each** (100 additional lines per pack,
    max 10 packs per account). The limit also increases automatically based on
    account equity and monthly commissions.
    
  - Subscribe and manage via [Client Portal → Market Data Subscriptions](https://www.interactivebrokers.com/en/pricing/market-data-pricing.php).
    
- **A running PostgreSQL database instance** with the required schema and tables
  pre-created. The database must be
  running and accessible before starting the system.
  > A Docker image with a pre-configured PostgreSQL instance (schema + tables
  > included) is currently in development and will be available in a future release
  > to simplify the setup process.
  
- **Trained forecast models** (`.pkl` files) if using the strategy layer. The system
  requires **3 models per portfolio** — one for each signal type: `BUY`, `SELL`, and
  `STOP_LOSS` — each registered and assigned before the system can generate signals.
  
  > A tutorial on how to build your own intraday execution optimization strategy
  > and train compatible forecast models is currently in development.
  
> The system is designed for users familiar with algorithmic trading, the IBKR ecosystem, and quantitative finance. It is not a plug-and-play solution.

---

## Installation

```bash
git clone https://github.com/PaulMrtn/HeavenlyCapital.git
cd HeavenlyCapital
pip install -r requirements.txt
```

---

## Quick Start

### 1. Initialize the service

```python
from heavenly_capital.services.app import SessionService
from decimal import Decimal

service = SessionService()
```

### 2. Create a session

```python
service.create_session(
    session_name="MySession",
    account_id="ACC123",
    mode="PAPER"  # or "LIVE"
)
```

| Parameter | Type | Description |
|---|---|---|
| `session_name` | `str` | Name of the session |
| `account_id` | `str` | IBKR account identifier |
| `mode` | `str` | `"PAPER"` or `"LIVE"` |
| `context` | `dict` | Optional additional metadata |

### 3. Create a portfolio

```python
service.create_portfolio(
    account_id="ACC123",
    strategy_id="STRAT001",
    portfolio_id="PORT001",
    portfolio_name="MyPortfolio",
    cash_amount=Decimal("10000.0"),
    currency="USD",
    enabled=True
)
```

### 4. Register a capital event

```python
service.register_capital_event(
    account_id="ACC123",
    portfolio_id="PORT001",
    event="CAPITAL_ADDITION",  # "INITIAL_CAPITAL" | "CAPITAL_ADDITION" | "CAPITAL_WITHDRAWAL"
    amount=Decimal("5000.0"),
    currency="USD"
)
```

> In **PAPER** mode, the amount is provided directly. In **LIVE** mode, the initial capital is fetched from IBKR servers automatically.

### 5. Register and assign a forecast model

```python
# Register a model
service.update_forecast_model(
    model_name="BuyModelV1",
    model_type="BUY",          # "BUY" | "SELL" | "STOP_LOSS"
    version=1.0,
    path="/models/buy_v1.pkl",
    description="Linear Regression buy signal",
    enabled=True
)

# Assign it to a portfolio
service.update_portfolio_model(
    portfolio_id="PORT001",
    model_name="BuyModelV1",
    model_type="BUY",
    version=1.0
)
```

### Full example

```python
from heavenly_capital.services.app import SessionService
from decimal import Decimal

service = SessionService()

# Session
service.create_session("MySession", "ACC123", "PAPER")

# Portfolio
service.create_portfolio(
    "ACC123", "STRAT001", "PORT001", "MyPortfolio",
    cash_amount=Decimal("10000.0")
)

# Capital
service.register_capital_event("ACC123", "PORT001", "INITIAL_CAPITAL", Decimal("10000.0"))

# Model
service.update_forecast_model("BuyModelV1", "BUY", 1.0, "/models/buy_v1.pkl", "Buy signal model")
service.update_portfolio_model("PORT001", "BuyModelV1", "BUY", 1.0)
```

---

## Roadmap

| Status | Milestone |
|---|---|
| ✅ Done | Core engine, data layer, IBKR integration |
| ✅ Done | Trading engine (orders, risk, portfolio) |
| ✅ Done | Monitoring & session management |
| ✅ Done | Forecast model lifecycle management |
| 🔄 In progress | Quantitative research integration (signal generation) |
| 🔜 Planned | Intraday execution strategies |
| 🔜 Planned | Backtesting module |
| 🔜 Planned | Reporting & dashboard |

---

## Disclaimer

This project is for **personal research and educational purposes**. It is not financial advice. Live trading involves significant financial risk. Use at your own risk.

---

## Author

**Paul Martin** — [GitHub](https://github.com/PaulMrtn)
