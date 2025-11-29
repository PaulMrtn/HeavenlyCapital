## I. Data Management

Ce cœur est responsable de l'ingestion, du nettoyage, de la persistance et de la mise à disposition des données.

### **Database Connector**

Ce composant est l'interface du système avec la base de données relationnelle. Sa fonction principale est de gérer le cycle de vie des connexions : établir, maintenir, et clore les sessions. Il gère la **résilience** de la connexion, la **lecture sécurisée** des identifiants, et fournit des métriques de **surveillance** au système.

* **Interfaces Fournies / Requises :**
    * **IConnectionFactory** : **Interface fournie** par le `Database Connector` pour instancier et retourner un objet de connexion ou une session de base de données.
    * *SQL Alchemy* : **Package/Framework requis** (ORM) pour la gestion technique du *pool* de connexions.
    * **Config / Secret Vault** : **Composant/Source requis** pour l'extraction sécurisée des identifiants de connexion (*secrets*).
    * **Monitoring Module** : **Composant requis** pour rapporter l'état des connexions et la latence I/O.

#### Notes

* **Résilience :** Implémente une **logique de *retry*** pour rétablir automatiquement la connexion à la base de données en cas de défaillance temporaire du réseau.
* **Sécurité :** Construit l'URI de connexion en lisant les identifiants à partir d'une source sécurisée (**Secret Vault**) et non d'un simple fichier de configuration.
* **Performance/Monitoring :** Transmet des métriques de performance et de santé de la base de données au **Monitoring Module** (e.g., temps de réponse, taux de succès des connexions) pour une surveillance proactive.


### **Data Preprocessor**
  
Ce composant assure la sanitisation et la normalisation des payloads de données brutes. Il est invoqué par le Data Ingestion Layer en amont de toute opération de persistance. Il opère comme une unité de transformation interne garantissant la cohérence du schema des données.


### **Data Ingestion Layer (DIL)**

Le DIL est l'orchestrateur de la persistance des *data sets. Sa responsabilité principale est de fournir un set de méthodes d'écriture pour injecter l'intégralité des flux de données dans le système de stockage persistant. Il assure la séquence des opérations : appel au Data Preprocessor pour la standardisation des données, puis mapping et écriture.

* **Interfaces Fournies / Requises :**
    * **IDatabaseWriter** : **Interface de persistance fournie** par le DIL, constituant le **contrat de service** pour les composants tiers souhaitant stocker des données (e.g., **Live Data Hub**).
    * **Database Connector** : **Composant requis** pour la gestion du *pool* de connexions et des sessions de transaction vers le *data store*.
    * **Data Preprocessor** : **Composant requis** pour standardiser le *payload* de données.
    * *SQL Alchemy* : **Package/Framework requis** (ORM) utilisé pour l'abstraction et l'efficacité des opérations CRUD.


### **Data Access Layer (DAL)**

Le DAL est la couche d'**abstraction de la lecture** qui fournit des méthodes simplifiées et optimisées pour requêter l'intégralité des *data sets* stockés. Il agit comme un **intermédiaire de service** permettant aux composants clients (stratégies, *risk monitors*) de consommer des données sans connaissance directe du *schema* ou de la complexité du **Database Connector**.

* **Interfaces Fournies / Requises :**
    * **IDataReader** : **Interface de lecture fournie** par le DAL. Elle expose des méthodes de haut niveau (ex: `get_historical_prices(asset_id, start_date)`) qui constituent le **contrat de service** pour la consommation de données.
    * **Database Connector** : **Composant requis** pour obtenir la session de connexion active à la base de données.
    * *SQL Alchemy* : **Package/Framework requis** (ORM) utilisé pour la construction et l'exécution des requêtes optimisées.

#### Notes

* **Mise en Cache des Requêtes :** Intégration d'un mécanisme de **caching** au niveau du DAL pour les requêtes de données historiques coûteuses ou fréquemment sollicitées. Cela permet de réduire la **latence** et la **charge I/O** sur la base de données pour les composants consommateurs.
  

### **Live Data Hub**

Ce composant est l'**écouteur central** des flux de prix marché. Il écoute les *triggers* de prix en temps réel via l'**IBKR Gateway** pour créer des **snapshots de marché** réguliers. Ces données sont mises en cache via l'**Interface Cache** et mises en file d'attente pour la persistance via l'**Interface Buffer**.

* **Interfaces Fournies / Requises :**
    * **IBKR Data Interface** : **Interface requise** via **IBKR Gateway** pour recevoir les mises à jour de prix (*market data stream*).
    * **Cache Interface** : **Interface fournie** pour l'écriture des données en cache.
    * **Buffer Interface** : **Interface fournie** pour la mise en file d'attente des données destinées à la persistance asynchrone.
    * *ib\_async* : **Package/Framework requis** pour la gestion de l'écoute asynchrone des événements de l'API de courtage.

* **Data Classes :**
    * **TickData** : Représente l'état instantané d'un actif (bid/ask, dernière transaction, volumes). C'est la donnée brute du marché.
    * **SnapshotHeader** : Représente l'en-tête d'un instantané global du marché à une fréquence donnée (ex: '1m', '5m').
    * **MarketQuote** : Représente la cotation consolidée d'un actif au sein d'un SnapshotHeader pour une période donnée.

#### Notes

* **Cohérence des Ticks :** Inclusion d'un mécanisme de vérification pour détecter les **sauts (gaps)** ou les incohérences dans la séquence des *ticks* reçus, afin de garantir la qualité des **SnapshotHeader** générés.
* **Suivi de Latence :** Enregistrement du **`receive_timestamp`** (temps de réception par le *Hub*) en plus du `timestamp` du marché. Cela permet de calculer la latence entre le courtier et le système et d'auditer la performance.


---
## II. Real-Time Core

### **Order Manager**

Le rôle de ce composant est de **centraliser la gestion du cycle de vie des ordres**. Il reçoit les **requêtes de création d'ordre** provenant de différents émetteurs (**Portfolio State Manager** pour le rééquilibrage, **Risk Monitor** pour les ordres d'urgence comme le *stop loss*). Il crée l'objet **Order** structuré et le transmet pour exécution au **Job Manager**. Il est également responsable de la mise à jour du statut de l'ordre tout au long de son cycle via une fonction `updateStatus`.

* **Interfaces Fournies / Requises :**
    * **IOrderCreator** : **Interface fournie** pour la réception des requêtes de création d'ordre (utilisée par **Portfolio State Manager** et **Risk Monitor**).
    * **IJobSubmission** : **Interface requise** pour l'envoi de l'ordre nouvellement créé vers le **Job Manager** pour l'exécution asynchrone.

* **Data Classes :**
    * **Order** : Représente une instruction d’achat ou de vente d’un actif, définissant son type, sa quantité, son prix et son statut. Elle centralise les relations avec l’actif, les exécutions et les événements.

#### Notes

* **Gestion des IDs :** Maintenir un *mapping* fiable entre l'**ID interne** (`order_id`) de l'objet `Order` et l'**ID du courtier** (`broker_order_id`). Cette correspondance est vitale pour la traçabilité, la gestion des exécutions et les opérations d'annulation (*cancelation*) via l'API de courtage.
Ce cœur gère les opérations critiques nécessitant une faible latence, notamment l'exécution d'ordres et la surveillance immédiate.


### **Portfolio State Manager (PSM)**

**Description :** Le PSM est le composant pivot qui maintient l'état financier et les métriques de performance du portefeuille. Il consolide les mouvements (entrées/sorties de *cash*, exécutions d'ordres lues via la base) pour générer l'état actuel (agrégé par lot). Il exécute la fonction de rééquilibrage : il compare l'état actuel à un état cible (futur) pour générer les **requêtes d'ordres** (*rebalancing*), assurant la gestion des lignes de *cash* et l'émission des ordres via l'**Order Manager**.

* **Interfaces Fournies / Requises :**
    * **IPortfolioStateReader** : **Interface fournie** pour exposer l'état actuel et les métriques de performance.
    * **IOrderCreator** : **Interface requise** pour soumettre les ordres de rééquilibrage à l'**Order Manager**.
    * **IDataReader** : **Interface requise** pour récupérer l'état des exécutions et les données de marché nécessaires.

* **Data Classes :**
    * **Portfolio** : Représente le conteneur de l'état global du portefeuille (liquidités, capital initial, devise).
    * **CashFlow** : Représente un mouvement de liquidité (dépôt, retrait) affectant la ligne de trésorerie.
    * **Position** : Représente la quantité agrégée d'un actif détenu.

#### Notes

* **Simulation de l'État Cible (Lookahead) :** Le PSM doit être capable de **simuler** l'état futur (`Portfolio`) en intégrant les ordres de rééquilibrage, les coûts de transaction et le *slippage* anticipé **avant** de soumettre les ordres.
* **Gestion de l'Atomicité du Rééquilibrage :** Les requêtes d'ordres générées par le rééquilibrage doivent être traitées comme une **transaction atomique**. Si l'ensemble des requêtes ne peut pas être soumis ou validé, aucune partie des ordres ne doit être envoyée.


### **Risk Monitor**

Ce composant est actif **uniquement durant l'ouverture du marché**. Son rôle est de surveiller en continu l'état du marché par rapport aux positions actives et aux limites de risque prédéfinies. Il lit les prix les plus récents depuis l'**Interface Cache** du **Live Data Hub**. Si une métrique de risque (ex: niveau de stop-loss atteint, dépassement de la tolérance maximale) est déclenchée, il génère des **requêtes d'ordres d'urgence** qui sont envoyées à l'**Order Manager** pour une exécution rapide.

* **Interfaces Fournies / Requises :**
    * **ICacheReader** : **Interface requise** pour lire les cotations de prix marché en temps réel depuis le **Live Data Hub**.
    * **IPortfolioStateReader** : **Interface requise** pour lire l'état actuel du portefeuille (valorisation, marges, etc.) du **Portfolio State Manager**.
    * **IOrderCreator** : **Interface requise** pour émettre des ordres d'urgence (*stop loss* ou de couverture) vers l'**Order Manager**.
    * **IDataReader** : **Interface requise** (utilisée en phase de *post-market*) pour charger le `RiskSnapshot` initial depuis la base de données.

* **Data Classes :**
    * **RiskSnapshot** : Data Class interne qui contient, après chargement initial, l'ensemble des données de risque nécessaires à la surveillance en temps réel (positions, stop-loss, tolérances maximales par actif, etc.).

#### Notes

* **Priorisation d'Urgence :** Les requêtes d'ordres émises par le *Risk Monitor* doivent inclure un **attribut de priorité maximale** pour garantir que l'**Order Manager** soumette l'ordre sans délai (*fast-lane*).
* **Robustesse aux Inputs Extrêmes :** Le module doit faire l'objet de **tests unitaires rigoureux** simulant des scénarios extrêmes (ex: chute de prix soudaine, prix nul/négatif) afin d'assurer que la logique de déclenchement d'urgence est robuste et stable.
* **Filtrage du Bruit (*Noise Filtering*) :** Intégration d'une **logique de confirmation** des seuils de risque (ex: seuil atteint sur deux *ticks* consécutifs ou maintenu pendant une durée minimale) pour éviter les faux déclenchements basés sur des bruits de marché éphémères.
* **Mécanisme de *Kill Switch* :** Le *Risk Monitor* doit être capable de déclencher un **mécanisme d'arrêt d'urgence global** en cas de défaillance critique, qui comprend l'annulation de tous les ordres actifs et la désactivation des algorithmes de trading.


### **Job Manager**

Le **Job Manager** est l'**ordonnanceur central** et l'**orchestrateur du workflow** du système. Ses objectifs principaux sont :
1.  **Orchestration :** Il est cadencé par les événements du **Market Clock** et gère l'exécution des tâches selon leur planification et leurs **dépendances** prédéfinies (`ScheduledJob`).
2.  **Files d'Attente :** Il implémente un **mécanisme de file d'attente prioritaire** pour traiter les ordres urgents (Risk Monitor) devant les tâches régulières (Rebalancing).
3.  **Tolérance aux Pannes et Reprise :** Il assure la **tolérance aux pannes** et la **reprise** des tâches non-terminales en cas d'échec, en utilisant l'historique de `JobExecution`.

* **Interfaces Fournies / Requises :**
    * **IJobSubmission** : **Interface fournie** pour recevoir les requêtes de tâches immédiates ou prioritaires (ex: Ordres du **Order Manager**).
    * **IMarketEventSubscriber** : **Interface requise** pour écouter les événements de cadencement du **Market Clock**.
    * **IDatabaseWriter** : **Interface requise** (via le DIL) pour la persistance des statuts d'exécution et d'ordres.
    * **ILogService** : **Interface requise** pour journaliser les détails de l'exécution (`JobExecution`).

* **Data Classes :**
    * **ScheduledJob** : Représente la définition d'une tâche planifiée au sein du système.
    * **JobExecution** : Représente une instance unique de l'exécution d'une tâche (historique, statut, horodatages).

###  Notes

* **Gestion des Dépendances (Workflow) :** Mise en œuvre d'un moteur de *workflow* permettant de définir des **dépendances strictes** entre les tâches (ex: Tâche B ne s'exécute que si Tâche A a le statut `COMPLETED_SUCCESS`).
* **Mécanisme de File d'Attente Prioritaire :** La file d'attente doit garantir que les ordres urgents (avec l'attribut de priorité maximale) sont traités et soumis à l'**IBKR Gateway** avant toutes les autres tâches, y compris l'envoi en masse d'ordres de *rebalancing*.
* **Tolérance aux Pannes et Reprise :** Implémentation d'une **logique de *retry*** limitée pour les échecs transitoires, ainsi qu'un mécanisme de notification critique pour les échecs non récupérables, en se basant sur le statut de `JobExecution`.
* **Atomicité de l'Ordre :** Lors de la soumission d'ordres (via `IJobSubmission`), le Job Manager doit s'assurer que l'intégralité du *payload* d'ordres est bien transmise à l'**IBKR Order Sender** pour maintenir le principe d'**Atomicité du Rééquilibrage** défini dans le PSM.


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
