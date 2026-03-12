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


## Installation

```bash
pip install heavenly-capital
```

## Importation

```python
from decimal import Decimal
from heavenly_capital.services.app import SessionService
from heavenly_capital.data.db_mock import TradingSessionDB

# Initialiser la base de données simulée et le service
db = TradingSessionDB()
service = SessionService(db=db)
```

---

## Création d’une session

```python
service.create_session(
    session_name="SessionTest",
    account_id="ACC123",
    mode="PAPER"  # ou "LIVE"
)
```

**Paramètres :**

* `session_name` : Nom de la session
* `account_id` : Identifiant du compte IBKR
* `mode` : `"LIVE"` ou `"PAPER"`
* `context` : dictionnaire optionnel pour stocker des informations additionnelles

**Exceptions :**

* `ValueError` si une session existe déjà pour le compte.

---

## Création d’un portefeuille

```python
service.create_portfolio(
    account_id="ACC123",
    strategy_id="STRAT001",
    portfolio_id="PORT001",
    portfolio_name="PortfolioTest",
    cash_amount=Decimal("10000.0"),
    currency="USD",
    enabled=True
)
```

**Paramètres :**

* `account_id` : identifiant du compte
* `strategy_id` : identifiant de la stratégie associée
* `portfolio_id` : identifiant unique du portefeuille
* `portfolio_name` : nom lisible du portefeuille
* `cash_amount` : capital initial (requis pour mode PAPER)
* `currency` : devise (par défaut `"USD"`)
* `enabled` : portefeuille actif ou non

**Exceptions :**

* `ValueError` si la session n’existe pas ou si le portefeuille existe déjà.

---

## Enregistrement d’un événement de capital

```python
service.register_capital_event(
    account_id="ACC123",
    portfolio_id="PORT001",
    event="CAPITAL_ADDITION",  # "INITIAL_CAPITAL" | "CAPITAL_ADDITION" | "CAPITAL_WITHDRAWAL"
    amount=Decimal("5000.0"),
    currency="USD"
)
```

Cet événement met à jour automatiquement le solde du portefeuille dans la base de données. Pour les comptes en mode **PAPER**, 
le montant est fourni lors de l’enregistrement de l’événement. Pour les comptes en mode **LIVE**, le montant initial est
récupéré directement depuis les serveurs **IBKR**.

---

## Suppression d’un portefeuille

```python
service.delete_portfolio(
    account_id="ACC123",
    portfolio_id="PORT001"
)
```

**Exceptions :**

* `ValueError` si le portefeuille n’existe pas.

---


## Gestion des modèles de prévision

### Création ou mise à jour d’un modèle

```python
service.set_model(
    model_name="ModelBuyV1",
    model_type="BUY",  # "BUY" | "SELL" | "STOP_LOSS"
    version=1.0,
    path="/models/buy_v1.pkl",
    description="Linear Regression Model",
    enabled=True
)
```

**Exceptions :**

* `ValueError` si `version` manquante ou `model_type` invalide.

### Attribution d’un modèle à un portefeuille

```python
service.assign_model_to_portfolio(
    portfolio_id="PORT001",
    model_name="ModelBuyV1",
    model_type="BUY",
    version=1.0
)
```

**Exceptions :**

* `ValueError` si le portefeuille est désactivé ou si le modèle n’existe pas.

---

## Exemple complet

```python
# Créer une session
service.create_session("MaSessionPaper", "ACC123", "PAPER")

# Créer un portefeuille
service.create_portfolio(
    "ACC123", "STRAT001", "PORT001", "PortfolioTest", cash_amount=Decimal("10000.0")
)

# Ajouter un capital supplémentaire
service.register_capital_event("ACC123", "PORT001", "CAPITAL_ADDITION", Decimal("5000.0"))

# Définir un modèle de trading
service.set_model("ModelBuyV1", "BUY", 1.0, "/models/buy_v1.pkl", "Modèle d'achat")

# Assigner le modèle au portefeuille
service.assign_model_to_portfolio("PORT001", "ModelBuyV1", "BUY", 1.0)
```
