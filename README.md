<p align="center">
  <img src="img/logo.png" alt="Logo" width="600">
</p>

---

Coming soon ...

---

## Folder Structure 

```tree
trading_system/
│
├── core/
│   ├── __init__.py
│   ├── system_manager.py         # Composant central SystemManager
│   ├── market_clock.py           # Singleton pour le cadencement temporel
│   ├── session_manager.py        # Gestion des TradingSession
│   ├── thread_manager.py         # Gestion des pools et threads I/O
│   └── job_manager.py            # Orchestration des tâches et jobs
│
├── data/
│   ├── __init__.py
│   ├── database_connector.py     # Gestion DB, pool, sessions
│   ├── data_ingestion.py         # DIL
│   ├── data_access.py            # DAL
│   ├── live_data_hub.py          # Flux temps réel
│   └── live_history_buffer.py    # Cache/Buffer central
│
├── trading/
│   ├── __init__.py
│   ├── portfolio_manager.py
│   ├── order_manager.py
│   ├── risk_monitor.py
│   ├── global_order_router.py
│   └── ibkr_gateway.py
│
├── pipeline/
│   ├── __init__.py
│   ├── pipeline_manager.py
│   ├── asset_selection.py
│   ├── filter_manager.py
│   ├── portfolio_optimizer.py
│   ├── risk_manager.py
│   └── data_integrity_engine.py
│
├── strategy/
│   ├── __init__.py
│   ├── forecast_manager.py 
│   ├── strategy_engine.py
│   └── backtest_engine.py
│       ├── parametric_optimizer.py
│       └── shock_simulator.py
│
├── monitoring/
│   ├── __init__.py
│   ├── log_service.py
│   ├── metric_service.py
│   ├── error_service.py
│   └── notification_service.py
│
├── models/                        # Data classes et ODT/DTO
│   ├── __init__.py
│   ├── portfolio.py
│   ├── order.py
│   ├── market_data.py
│   ├── trading_session.py
│   └── pipeline_dot.py
│
├── utils/
│   ├── __init__.py
│   └── helpers.py
│
├── config/
│   ├── __init__.py
│   └── settings.py                 # Paramètres globaux, secrets, paths
│
└── main.py                         # Point d’entrée pour démarrage du système

```

