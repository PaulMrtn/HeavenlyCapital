<p align="center">
  <img src="docs/logo.png" alt="Logo" width="600">
</p>

Cette section décrit l'état actuel de la stratégie et de l'architecture du projet.

### Stratégie de Sélection d'Actifs (`AssetSelectionStrategy`)
- Basée sur le **momentum** avec différentes périodes (1 semaine à 12 mois)  
- Poids attribués selon la durée (plus la période est longue, plus le poids est important)  
- Sélection des actifs selon :
  - Meilleurs rendements (top 5)  
  - Volatilité la plus élevée (top 10)  
- Limite du portefeuille : **maximum 5 actifs**

### Stratégie de Stop Loss (`StopLossStrategy`)
- Seuil : **95%** (`threshold = 0.95`)  
- Surveille les rendements depuis la date d'achat  
- Vente automatique si le rendement passe sous le seuil  
- Permet de limiter les pertes sur chaque position

### Stratégie de Rééquilibrage (`PortfolioManager`)
- **Rééquilibrage mensuel** : révision complète selon nouvelles sélections, poids égaux aux nouvelles positions  
- **Rééquilibrage hebdomadaire** : ajustement des positions existantes pour maintenir les poids cibles, pas de nouvelles sélections  
- **Mise à jour quotidienne** : vérification des stop-loss, mise à jour des prix et valorisations  
- Tolérance pour écart de poids : **1.5%** (`tol = 0.015`) pour limiter les coûts de transaction

---

## Folder Structure 

```tree
trading_framework/
│
├── README.md
├── .gitignore
├── requirements.txt
│
├── doc/
│   ├── todo.md
│   └── notes.md
│
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── utils.py
│   │   └── pipeline.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   └── loader.py
│   │
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── asset_selection.py
│   │   ├── stop_loss.py
│   │   └── portfolio.py
│   │
│   └── backtest/
│       ├── __init__.py
│       └── backtester.py
│
├── db/
│   ├── __init__.py
│   └── .../
│
└── notebooks/
    └── .../
```

