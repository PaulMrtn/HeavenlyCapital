##  Feuille de Route Détaillée (Roadmap / To-Do List)

### 1. Diagrammes Transversaux et Processus Critiques

**Nom du Package:** CORE_CRITICAL_PROCESSES

Ces diagrammes doivent être réalisés en premier, car ils sont utilisés dans les phases Pre-Trade, In-Trade et Post-Trade.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| **02** | `02-CORE-Persistance-Atomique-FILL.puml` | Décrit le traitement asynchrone d'une exécution de bout en bout, de l'**IBKR Gateway** à la persistance en base de données. | * Décomposition : **IBKR Gateway** $\to$ **Event** $\to$ **Order Manager** / **Portfolio Manager**. * Détail : Mettre en évidence la soumission au **Job Manager** (Pool I/O Real-Time) et l'écriture **DIL** $\to$ **Database**. |
| **03** | `03-CORE-Soumission-Job-Prioritaire.puml` | Illustre la réception d'un ordre (Urgent ou Standard) par l'**Order Manager** et l'arbitrage par le **Job Manager**. | * Décomposition : **Order Manager** $\to$ **Job Manager** $\to$ **Thread Manager** $\to$ **IBKR Gateway**. * Détail : Utiliser des fragments alt pour l'arbitrage **Prioritaire / Standard** et l'allocation du **Pool I/O Critical**. |
| **04** | `04-CORE-Persistance-Bulk-Snapshot.puml` | Décrit le processus d'ingestion massive des **Snapshots** dans le **Pool I/O Bulk** du **DIL** pour isoler le **Bulk I/O** du **Critical I/O**. | * Décomposition : **Live Data Hub** $\to$ **DIL** $\to$ **Job Manager** (Pool I/O Bulk) $\to$ **Database**. |

---

### 2. Diagrammes de la Phase Pre-Trade (Bootstrapping)

**Nom du Package:** PHASE_01_BOOTSTRAPPING

#### I. Phase Pre-Trade (Préparation à l'Ouverture)

| Étape | Composant(s) Cible(s) | Tâche(s) à Développer / Valider | Priorité |
| :--- | :--- | :--- | :--- |
| **1. Initialisation du Cycle de Marché** | **System Manager**, Market Clock, Database Connector, Session Manager | 1.1 **Implémenter la routine `MarketDayStatus`** (via `pandas_market_calendars`). <br> 1.2 **Développer la fonction `evaluateBootstrapStatus()`** pour gérer l'arrêt/la continuation sur `MarketDayStatus.is_trading_day`. | Critique |
| **2. Vérifications Préalables (Intégrité et Connexion)** | **Database Connector**, **IBKR Gateway**, System Manager, IDatabaseWriter | 2.1 **Intégrer le fragment `00-RESILIENT-CHECK-CONNECTION-SVC`** aux vérifications DB et IBKR. <br> 2.2 **Mettre en place la procédure d'arrêt sécurisé** (`systemStop`) avec notification en cas d'échec persistant (Tolérance Zéro). <br> 2.3 **Valider la liaison `IDatabaseWriter`** pour la persistance des journaux de session (via DIL). | Critique |
| **3. Chargement et Préparation des Données** | **Portfolio Manager (PM)**, **Risk Monitor (RM)**, IBKR Gateway | 3.1 **Développer la fonction `PM.loadRebalancingOrders()`** pour charger les ordres post-marché stockés. <br> 3.2 **Développer la fonction `RM.loadRiskSnapshot()`** pour charger les données de Stop-Loss/Take-Profit pour la session. <br> 3.3 **Valider l'initialisation de la connexion de données** de l'IBKR Gateway pour les *tick data*. | Haute |
| **4. Synchronisation et Transition vers In-Trade** | **System Manager**, Market Clock, Job Manager | 4.1 **Implémenter la logique d'attente/synchronisation** pour la complétion des tâches de chargement (étape 3). <br> 4.2 **Configurer l'écoute asynchrone** du signal `MARKET_OPEN` émis par le Market Clock (Transition vers Phase II). | Critique |

#### II. Étapes Détaillées d'Initialisation (Bootstrapping)

| Étape | Composant(s) Cible(s) | Tâche(s) à Développer / Valider | Priorité |
| :--- | :--- | :--- | :--- |
| **02. Instanciation des Configs Globaux** | **DAL**, **System Manager**, IBKR Gateway, Live Data Hub (LDH) | 2.1 **Optimiser le `DAL.readAllConfigs()`** pour une requête I/O atomique (lecture en un seul bloc). <br> 2.2 **Développer les constructeurs des Singletons** (`IBKR Gateway`, `LDH`) avec injection immédiate des configurations. <br> 2.3 **Implémenter le `H-Check unitaire`** après chaque instanciation de Singleton. | Critique |
| **03. Initialisation des Pools de Threads** | **Thread Manager (TM)**, System Manager | 3.1 **Développer la création des `PoolWorker` persistants** (Pools `CRITICAL` et `STANDARD`). <br> 3.2 **Implémenter le `HCheckPriorityTest`** sur le Pool CRITICAL pour valider la QoS (Qualité de Service) au niveau OS. | Critique |
| **04. Instanciation des Managers Locaux** | **Session Manager**, PM, RM, OM | 4.1 **Développer la boucle d'instanciation des `TradingSession`** (gestion des sessions LIVE et PAPER). <br> 4.2 **Implémenter l'injection de dépendances croisées** : `PM` $\leftrightarrow$ `OM`, `RM` $\leftrightarrow$ `OM` (Ordres d'Urgence), `RM` $\leftrightarrow$ `PM` (Référence pour Kill Switch). | Haute |
| **05. Chargement Parallèle** | **Thread Manager**, PM, RM, Database Connector | 5.1 **Orchestrer l'exécution parallèle** des `PM.loadInitialState()` et `RM.loadRiskSnapshot()` via le TM. <br> 5.2 **Implémenter le `HCheckDataIntegrity`** (vérification de la cohérence interne des données chargées par chaque manager). <br> 5.3 **Appliquer la règle `evaluateBootstrapStatus()`** sur les résultats de ce Job pour gérer l'arrêt LIVE/continuation PAPER. | Critique |
| **06. Initialisation du Flux Temps Réel** | **IBKR Gateway**, **LDH**, System Manager | 6.1 **Développer le mécanisme d'abonnement aux données de marché** (`LDH.subscribeToTicks()`). <br> 6.2 **Implémenter le contrôle `HCheckFirstTickReceived`** (attente avec *timeout* du premier prix de marché). <br> 6.3 **Configurer la séquence d'arrêt d'urgence** si le `HCheck` échoue (défaillance de l'infrastructure de données). | Critique |
| **07. Validation Croisée (HeartCheck)** | System Manager, PM, RM, OM, LDH | 7.1 **Développer les vérifications unitaires** (`HCheckPortfolioReady`, `HCheckRiskMonitorReady`). <br> 7.2 **Implémenter la Validation Croisée** : `RM` vérifie l'état du `PM` et vice-versa (cohérence des limites/positions). <br> 7.3 **Appliquer la règle `evaluateBootstrapStatus()`** une dernière fois sur les résultats agrégés. | Critique |
| **08. Transition Mode Veille** | **System Manager**, Order Manager (OM), Market Clock | 8.1 **Développer la mise à jour atomique du statut** vers `READY_FOR_TRADING`. <br> 8.2 **Implémenter la boucle de surveillance (Heartbeat)** périodique de l'OM vers l'IBKR Gateway. <br> 8.3 **Assurer l'audit (Log Critique)** à la réception du signal `MarketOpenEvent()` avant de lancer la Phase II. | Critique |

---

### 3. Diagrammes de la Phase In-Trade (Temps Réel)

**Nom du Package:** PHASE_02_LIVE_EXECUTION

Cette phase est principalement asynchrone et repose sur l'événement MINUTE\_TICK et le flux continu de **Tick Data**.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| **07** | `07-PHASE2-Flux-Temps-Reel-LDH.puml` | Modélise l'acquisition **Tick Data**, la **Surveillance Critique** et la distribution parallèle du **Snapshot** vers le **Cache** (Fast-Lane) et le **Buffer** (Slow-Lane). | * Décomposition : **IBKR Gateway** $\to$ **Live Data Hub**. * Détail : Inclure la vérification de **Latence Critique** et le fork vers le **Cache** et la soumission du **Bulk I/O** (ref: 04). |
| **08** | `08-PHASE2-Surveillance-Urgence-RiskMonitor.puml` | Séquence critique du **Risk Monitor** lisant le **Cache**, déclenchant un **Ordre d’Urgence** et utilisant la soumission prioritaire (ref: 03). | * Décomposition : **Risk Monitor** $\to$ **Cache** $\to$ **Order Manager**. * Détail : Se concentrer sur la haute priorité et l'utilisation de ref: 03. |
| **09** | `09-PHASE2-Boucle-Decision-Standard.puml` | Modélise la décision de **Rééquilibrage** du **Portfolio Manager** (PM) et la soumission d'**Ordres Standards** via l'**Order Manager** (ref: 03). | * Décomposition : **Market Clock** $\to$ **PM** $\to$ **Order Manager**. * Détail : Utiliser un fragment alt pour la condition **Jour de Rééquilibrage** et l'utilisation de ref: 03. |

---

### 4. Diagrammes de la Phase Post-Trade (Clôture Atomique)

**Nom du Package:** PHASE_03_POST_AUDIT

Cette phase est séquentielle et critique pour l'intégrité des données. Elle utilise les deux processus de persistance atomique.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| **10** | `10-PHASE3-Cloture-Audit-Reconciliation.puml` | Modélise la synchronisation du système, la **Réconciliation Finale** par le **PM**, et le lancement du **Rapport d’Audit Primaire**. | * Décomposition : **System Manager** $\to$ **Job Manager** (Attente de vidage buffers) $\to$ **PM** (**Reconciliation**). * Détail : Insister sur l'attente du vidage des buffers (Verrou/Latch) et l'émission de l'**Alerte Critique** en cas d'écart. |
| **11** | `11-PHASE3-Preparation-Atomique-Cycle-Suivant.puml` | Modélise la dernière étape : le **Strategy Engine** calcule le **Portfolio Target**, puis la persistance atomique du **Target** et de la **Configuration** (Pool I/O Post-Trade). | * Décomposition : **Strategy Engine** $\to$ **DIL** (Target) / **Session Manager** (Config). * Détail : Montrer la double soumission au **Pool I/O Post-Trade** et la transition finale **Off-Cycle** uniquement après validation des deux écritures. |

---

### 5. Diagrammes Optionnels (Robustesse & R&D)

**Nom du Package:** OPTIONAL_RND_ROBUSTNESS

Ces scénarios offrent une valeur ajoutée significative pour la résilience et l'optimisation.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| **12** | `12-CRITICAL-KillSwitch-Execution.puml` | **Gestion des Erreurs (Kill-Switch)** : Chemin exact d'une **CRITICAL\_ERROR** (ex: perte IBKR Gateway) à l'annulation de tous les ordres **WORKING**. | * Décomposition : **Live Data Hub** $\to$ **System Manager** (CRITICAL\_ERROR) $\to$ **Order Manager** $\to$ **IBKR Gateway** (Action : Annulation/`CancelAllOrders`). * Détail : Mettre en évidence l'arrêt sécurisé (arrêt des soumissions et mise en statut $\text{HALTED}$). |
| **13** | `13-RND-Backtest-Optimization.puml` | **Backtest & Optimisation** : Interaction entre le **Parametric Optimizer**, le **Backtest Engine** et la **Pipeline Core** (pour un seul pas de temps). | * Décomposition : **Parametric Optimizer** $\to$ **Backtest Engine** (Boucle) $\to$ **Pipeline Core** $\to$ **IBacktestRunner**. * Détail : Montrer l'injection de nouveaux **StrategyParameters** par l'Optimizer et la collecte des **Metrics** par le Backtest Engine. |

---



