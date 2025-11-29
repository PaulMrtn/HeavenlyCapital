### I. Data Management (Gestion des Données)

Ce cœur est responsable de l'ingestion, du nettoyage, de la persistance et de la mise à disposition des données.

* **Data Preprocessor** : Nettoie et normalise les flux de données brutes avant l'ingestion.
* **Data Ingestion Layer** : Point d'entrée pour toutes les données externes (flux de marché, fichiers, etc.).
* **Live Data Hub** : Maintient un cache des données de marché en temps réel pour un accès rapide.
* **Data Access Layer** : Fournit une interface unifiée pour l'accès aux données persistantes.
* **Database Connector** : Gère les connexions et les transactions vers la base de données.

---

### II. Real-Time Core (Noyau Temps Réel)

Ce cœur gère les opérations critiques nécessitant une faible latence, notamment l'exécution d'ordres et la surveillance immédiate.

* **Order Manager** : Traque le statut de tous les ordres ouverts et exécutés, en interaction directe avec l'API de courtage.
* **Portfolio State Manager** : Maintient l'état actuel et précis du portefeuille (positions, liquidités, P&L).
* **Risk Monitor** : Effectue des contrôles de risque pré- et post-trade en temps réel.

---

### III. Pipeline Core (Noyau de Pipeline)

Le cœur de la stratégie, exécutant la logique complexe de sélection d'actifs, d'optimisation et d'évaluation du risque.

* **Pipeline Manager** : Orchestre l'exécution séquentielle des étapes de la stratégie.
* **Asset Selection** : Applique des critères d'éligibilité pour sélectionner l'univers d'actifs.
* **Filter Manager** : Applique des filtres basés sur des indicateurs techniques ou fondamentaux.
* **Portfolio Optimizer** : Calcule les poids optimaux des actifs sélectionnés pour le portefeuille.
* **Risk Manager** : Évalue et contraint le risque global généré par l'optimisation.
* **Data Integrity Engine** : Assure que les données utilisées par le pipeline sont valides et non corrompues.

---

### IV. Backtest Core (Noyau de Backtesting)

Ce cœur est dédié à l'évaluation des performances des stratégies sur des données historiques et à la calibration des modèles.

* **Backtest Engine** : Moteur principal d'exécution pour la simulation des stratégies historiques.
* **Parametric Optimizer** : Réalise l'optimisation des paramètres pour trouver la meilleure performance ajustée au risque.
* **Shock Simulator** : Permet de réaliser des stress-tests en simulant des chocs de marché (e.g., Krach de 2008).

---

### V. Utilitaires & Infrastructure

Composants transversaux et d'infrastructure pour le bon fonctionnement et la surveillance du système.

* **Session Manager** : Gère l'état et le cycle de vie des sessions utilisateur ou d'exécution.
* **Thread Manager** : Contrôle l'allocation et la gestion des threads d'exécution.
* **Concurrency Manager** : Gère les mécanismes de parallélisme et de concurrence.
* **Log Manager** : Centralise et formate les journaux (logs) du système.
* **Reporting Manager** : Génère des rapports de performance et d'activité du système.
* **Monitoring Module** : Collecte des métriques sur la santé et les performances du système en temps réel.
* **Notification Manager** : Envoie des alertes aux utilisateurs ou aux systèmes externes.

---

### Interfaces et Connecteurs Clés

Ces éléments définissent les contrats de communication ou les dépendances technologiques entre les composants.

* **Ib\_async** : **Interface/Bibliothèque** fournie pour gérer la communication asynchrone avec l'API Interactive Brokers.
* **IBKR Order Sender** : **Interface fournie** par l'API de courtage pour l'envoi des ordres, utilisée par l'Order Manager.
* **IBKR Data Interface** : **Interface fournie** par l'API pour récupérer les données de marché, utilisée par le Live Data Hub.
* **IDatabaseWriter** : **Interface fournie** pour écrire des données de manière abstraite dans le stockage persistant.
* **SQL Alchemy** : **Bibliothèque/ORM** (Object-Relational Mapping) utilisée pour l'accès aux bases de données relationnelles.
* **Config, Path, Params** : **Interfaces/Paramètres** génériques pour la configuration, les chemins de fichiers et les données d'entrée.
