# GodPlan


## Présentation

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

## TODO

## 1. Organisation du Projet

| Tâche | Priorité |
|-------|----------|
| Créer un dépôt GitHub avec la structure de base du projet | Haute |
| Trier le contenu du SSD pour dédier le Mac entièrement au projet | Moyenne |

---

## 2. Stratégie et Conception

### 2.1 Diagramme et architecture
| Tâche | Priorité |
|-------|----------|
| Transformer le résumé de la stratégie de sélection d’actif en diagramme couvrant tous les éléments nécessaires à un algorithme de trading | Haute |

**Éléments à inclure dans le diagramme :**
- Import de données  
- Composants de stratégie : Génération Signaux, Optimisation Portfolio, Backtest  
- Composants d’exécution : Passage Ordres, Suivi Positions, Gestion Transactions  
- Composants de risque : Contrôle Risques, Stop-Loss, Diversification  

### 2.2 Lectures et inspirations
| Tâche | Priorité |
|-------|----------|
| Lire la liste de lectures et annoter les concepts inconnus ou inspirants | Moyenne |

---

## 3. Data

| Tâche | Priorité |
|-------|----------|
| Récupérer la composition historique du S&P 500 depuis 2000 (tous les stocks présents depuis cette date) | Haute |
| Préparer la base de données initiale et prévoir extension progressive | Moyenne |

---

## 4. Développement et Implémentation

| Tâche | Priorité |
|-------|----------|
| Trouver une solution technique pour que la version incrémentale (production) de l’algo renvoie les mêmes résultats que la version vectorisée (R&D) | Haute |

---

## 5. Intégration Broker

| Tâche | Priorité |
|-------|----------|
| Se documenter sur Interactive Brokers, comprendre l’API | Haute |
| Tester le passage d’ordres en trading paper | Haute |
