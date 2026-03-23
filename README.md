<p align="center">
  <img src="img/logo.png" alt="Logo" width="600">
</p>

---

Coming soon ...

---

## Folder Structure 

```tree
heavenly_capital/
│
├── core/
│   ├── __init__.py
│   ├── calendar.py           # Gestion du calendrier interne
│   ├── clock.py              # Horloge système et synchronisation
│   ├── kernel.py             # Logique centrale du moteur
│   └── thread.py             # Gestion des threads et pools
│
├── data/
│   ├── __init__.py
│   ├── bus.py                # Bus de communication des données
│   ├── historic.py           # Accès aux données historiques
│   └── live.py               # Flux de données en temps réel
│
├── db/
│   ├── __init__.py
│   ├── connector.py          # Connexion à la base de données
│   ├── reader.py             # Lecture depuis DB
│   └── writer.py             # Écriture vers DB
│
├── ibkr/
│   ├── __init__.py
│   ├── client.py             # Client IBKR
│   └── gateway.py            # Passerelle et gestion des ordres
│
├── models/
│   ├── __init__.py
│   ├── account.py            # Modèles de comptes
│   ├── config.py             # Paramètres et configuration
│   ├── market_data.py        # Structures de données marché
│   ├── mock.py               # Données mock pour tests
│   ├── order.py              # Modèles d’ordres
│   ├── portfolio.py          # Modèles de portefeuilles
│   ├── risk.py               # Modèles de risques
│   ├── runtime.py            # État du runtime
│   ├── session.py            # Gestion des sessions
│   ├── system.py             # Configuration système globale
│   └── tickers.py            # Informations sur les instruments
│
├── monitoring/
│   ├── __init__.py
│   ├── error_service.py      # Gestion des erreurs
│   ├── health_service.py     # Monitoring de santé du système
│   ├── log_service.py        # Journaux et logs
│   ├── metric_service.py     # Metrics et indicateurs
│   └── notification_service.py  # Notifications et alertes
│
├── services/
│   ├── __init__.py
│   └── app.py                # Point d’entrée des services
│
├── strategy/
│   ├── __init__.py
│   ├── artifacts.py          # Gestion des artefacts
│   ├── feature_manager.py    # Préparation des features
│   ├── features.py           # Calculs de features
│   └── forecast_manager.py   # Moteur de prévision
│
└── trading/
    ├── __init__.py
    ├── order_manager.py      # Gestion des ordres
    ├── portfolio_manager.py  # Gestion du portefeuille
    ├── risk_manager.py       # Suivi du risque
    ├── router.py             # Routage des ordres
    └── session_manager.py    # Gestion des sessions de trading

```


## Installation

```bash
pip install heavenly-capital
```

## Importation

```python
from decimal import Decimal
from heavenly_capital.services.app import SessionService

# Initialiser la base de données simulée et le service
service = SessionService()
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
service.update_forecast_model(
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
service.update_portfolio_model(
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
service.update_forecast_model("ModelBuyV1", "BUY", 1.0, "/models/buy_v1.pkl", "Modèle d'achat")

# Assigner le modèle au portefeuille
service.update_portfolio_model("PORT001", "ModelBuyV1", "BUY", 1.0)
```
