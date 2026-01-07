<p align="center">
  <img src="img/logo.png" alt="Logo" width="600">
</p>

---

Coming soon ...

---

## Folder Structure 

```tree
trading_station/
├── core/                   # Le "Real-Time Core" et l'orchestration
│   ├── system_manager.py   # Singleton central, autorité suprême
│   ├── session_manager.py  # Gestion du cycle de vie des sessions
│   ├── thread_manager.py   # Gestion des pools (Critical vs Bulk)
│   └── market_clock.py     # Source temporelle unique
├── data/                   # "Data Management"
│   ├── dil/                # Data Ingestion Layer (Écritures)
│   ├── dal/                # Data Access Layer (Lectures)
│   ├── lhb/                # Live History Buffer (Cache mémoire)
│   └── connector.py        # Database Connector (SQLAlchemy)
├── execution/              # Gestion des ordres et exécution
│   ├── order_manager.py    # Cycle de vie des ordres
│   ├── gor.py              # Global Order Router (Priorisation)
│   └── job_manager.py      # Ordonnanceur de tâches
├── gateway/                # Interfaces externes
│   ├── ibkr_gateway.py     # Wrapper ib_async
│   └── eod_service.py      # Client API EODHD
├── models/                 # Data Classes (DTO, Entities)
│   ├── order.py
│   ├── session.py
│   └── market_data.py
├── pipeline/               # "Pipeline Core" (Stratégie & Calcul)
│   ├── manager.py          # Pipeline Manager
│   ├── engine.py           # Strategy Engine
│   └── steps/              # AssetSelection, Optimizer, RiskManager...
└── utils/                  # Services transverses (Monitoring, Log, Error)
    ├── logger.py           # Log Service
    ├── metrics.py          # Metric Service
    └── notifications.py    # Notification Service
```

