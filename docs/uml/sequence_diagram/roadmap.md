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

| Étape | Séquence | Objectif de la Séquence (Résumé) | Actions Clés |
| :---: | :---: | :--- | :--- |
| **1** | **Connectivité Critique** (`01-PHASE1-Connectivite-Critique`) | Valider la **disponibilité** des services fondamentaux (DB, Courtier) et la **pertinence** du contexte de marché (Jour Ouvré) avant toute allocation de ressources. | \* Utiliser `00-RESILIENT-CHECK-CONNECTION-SVC` pour vérifier **DB** (Critique).<br>\* Utiliser `00-RESILIENT-CHECK-CONNECTION-SVC` pour vérifier **IBKR Gateway** (Critique).<br>\* Calculer et persister l'objet **`MarketDayStatus`**.<br>\* **Si non-ouvré** : Transition immédiate vers `Off-Cycle` (Veille). |
| **2** | **Instanciation des Configs Globaux** (`02-PHASE1-Instanciation-Configs-Globaux`) | Optimiser la lecture des configurations statiques (I/O) et instancier les **Singletons globaux** (IBKR Gateway, LDH) en leur injectant immédiatement leurs configurations. | \* Ordonner au **DAL** de lire **toutes les configs globales** en **un seul bloc** (Optimisation I/O).<br>\* Instancier l'`IBKR Gateway` avec sa config. Exécuter un **H-Check unitaire**.<br>\* Instancier le `Live Data Hub` (LDH) avec sa config. Exécuter un **H-Check unitaire**. |
| **3** | **Initialisation des Threads** (`03-PHASE1-Initialisation-Threads`) | Allouer les ressources d'exécution critiques (**Pools de Threads**) et valider leur performance/priorité auprès du système d'exploitation. | \* Récupérer les tailles/priorités des pools (mémoire).<br>\* Créer les objets `PoolWorker` persistants (`CRITICAL`, `STANDARD`).<br>\* Exécuter le **`HCheckPriorityTest`** sur le Pool CRITICAL (Validation QoS). |
| **4** | **Instanciation des Managers Locaux** (`04-PHASE1-Instanciation-Managers-Locaux`) | Créer la structure métier **par session** en instanciant les triplets (`PM`, `RM`, `OM`) et établir les **canaux de communication critiques** (Ordre et Urgence). | \* Boucle sur chaque `TradingSession` (LIVE/PAPER).<br>\* Créer l'entité `TradingSession`.<br>\* Instancier et injecter les dépendances dans `PM`, `RM`, et `OM`.<br>\* Établir les liens de communication : **PM $\rightarrow$ OM**, **RM $\rightarrow$ OM**, **RM $\rightarrow$ PM** (`setPortfolioReference`).<br>\* Exécuter le **`HCheckSessionReady`** (Validation des canaux locaux). |
| **5** | **Chargement Parallèle** (`05-PHASE1-Chargement-Parallele`) | Charger l'état initial des données (Positions, Limites de Risque) de **toutes les sessions en parallèle** pour masquer la latence I/O de la base de données. | \* Créer les Jobs `loadInitialState` (PM) et `loadRiskSnapshot` (RM) pour chaque session.<br>\* Soumettre les Jobs au **Thread Manager** en mode **parallèle**.<br>\* Chaque manager exécute son **`HCheckDataIntegrity`** (Validation de la cohérence métier des données lues).<br>\* Collecter les `JobStatusList` et lancer **`SM-evaluateBootstrapStatus`** (Gestion des arrêts LIVE vs PAPER). |
| **6** | **Initialisation Flux Temps Réel** (`06-PHASE1-Initialisation-Flux-Temps-Reel`) | Établir la connexion physique au flux de prix et **valider** la preuve de vie (réception du premier `tick`) avant de valider la session. | \* Récupérer la liste des actifs à surveiller de toutes les sessions.<br>\* Ordonner à l'`IBKR Gateway` de s'abonner et de commencer le flux.<br>\* Exécuter le **`HCheckFirstTickReceived`** sur le **LDH** (avec Timeout).<br>\* **Si échec** : Arrêt immédiat et fatal (`systemStop(CRITICAL_ERROR)`). |
| **7** | **Validation Croisée (HeartCheck)** (`07-PHASE1-Validation-Croisee-HeartCheck`) | Effectuer la validation finale (HeartCheck) de la **cohérence métier** et de l'état opérationnel entre les managers. | \* Exécuter les vérifications unitaires (`HCheckPortfolioReady`, `HCheckRiskMonitorReady`).<br>\* Exécuter les validations croisées (`ValidateRiskLimits`, `ValidatePortfolioState`).<br>\* Exécuter les vérifications d'infrastructure (`HCheckExternalConnection`, `HCheckMarketDataAvailable`).<br>\* Collecter les résultats finaux et lancer **`SM-evaluateBootstrapStatus`** (Point de non-retour sécurisé). |
| **8** | **Transition Mode Veille** (`08-PHASE2-Transition-Mode-Veille`) | Faire passer le système à l'état **opérationnel de veille** et attendre l'événement temporel déclencheur de la phase In-Trade. | \* Mettre à jour l'état du système à **`READY_FOR_TRADING`**.<br>\* Démarrer la boucle de **Heartbeat** périodique (OM $\rightarrow$ IBKR Gateway).<br>\* Entrer en attente asynchrone (`Wait for MarketOpenEvent()`).<br>\* À la réception de l'événement : Loguer l'événement et transition vers la **Phase II (In-Trade)**. |
---

### 3. Diagrammes de la Phase In-Trade (Temps Réel)

**Nom du Package:** PHASE_02_LIVE_EXECUTION

Cette phase est le cœur opérationnel, où l'exécution en temps réel, la surveillance du risque, la prise de décision, et la persistance critique doivent coexister avec une latence minimale.

| Étape | Séquence/Module | Objectif de la Séquence (Résumé) | Actions Clés |
| :---: | :---: | :--- | :--- |
| **9** | **Démarrage Flux Temps Réel et Distribution** | Démarrer l'acquisition haute fréquence des données de marché (`Tick Data`) et distribuer les `Snapshots` agrégés dans les canaux **rapides** (Cache) et **lents** (Persistance Bulk). | \* Lancer l'écoute asynchrone des `Tick Data` par l'**IBKR Gateway**.<br>\* Le **Live Data Hub (LDH)** : recevoir, agréger les Ticks en `MarketQuote/Snapshot`.<br>\* **Surveillance Critique du Flux :** Vérifier la latence du flux et alerter le **System Manager** en cas d'écart critique (prélude au Kill Switch).<br>\* **Distribution :** Écrire le Snapshot dans le **Cache Temps Réel** (Fast-Lane) pour le **RM** et le **PM**.<br>\* Mettre le Snapshot en **Buffer** pour le **DIL** (Slow-Lane). |
| **10** | **Surveillance de Risque et Ordres d'Urgence** | Exécuter la boucle de surveillance du **Risk Monitor (RM)** en temps réel et générer des ordres d'urgence (Stop-Loss/Take-Profit) de manière **prioritaire**. | \* Le **RM** lit le prix le plus récent dans le **Cache Temps Réel**.<br>\* Évaluer les conditions **Stop-Loss/Take-Profit** pour chaque `RiskSnapshot` chargé.<br>\* **Si condition atteinte :** Générer un **Ordre d'Urgence** (`Order`) avec Priorité Maximale.<br>\* Soumettre l'Ordre d'Urgence à l'**Order Manager (OM)** pour soumission immédiate (court-circuitant l'évaluation PM). |
| **11** | **Boucle de Stratégie et Ordres Standards** | Exécuter la logique de trading du **Portfolio Manager (PM)** (selon les règles de Rééquilibrage ou de Timing Intraday) et générer des ordres standards. | \* Le **PM** évalue si la journée est un **Jour de Rééquilibrage** (via `TradingCalendar`).<br>\* **Si Rééquilibrage :** Calculer le besoin de rééquilibrage, appliquer l'algorithme d'optimisation (VWAP/TWAP) pour **"timer"** la soumission.<br>\* **Si Non Rééquilibrage :** Le PM reste passif (sauf pour maintenance ou cash management explicite).<br>\* Générer un **Ordre Standard** (`Order`) avec Priorité Normale.<br>\* Soumettre l'Ordre Standard à l'**OM**. |
| **12** | **Arbitrage et Transmission des Ordres** | Arbitrer la soumission des ordres (Urgence vs Standard) via le **Job Manager** et les transmettre au courtier via le pool d'E/S critique. | \* L'**OM** reçoit tous les ordres (`Urgence` et `Standard`).<br>\* Soumettre les tâches d'envoi d'ordres au **Job Manager**.<br>\* Le **Job Manager** utilise la logique de priorité pour garantir la soumission des ordres **Urgence** avant les **Standard**.<br>\* Le **Thread Manager** alloue un thread du **Pool I/O Critical**.<br>\* L'**IBKR Gateway** exécute la transmission physique de l'ordre au courtier. |
| **13** | **Gestion des Exécutions (Fills) et Persistance** | Réceptionner l'exécution de l'ordre (`Fill`) et orchestrer la mise à jour **atomique** et **critique** des structures de position et d'ordre en mémoire et en base. | \* L'**IBKR Gateway** reçoit le `Fill` et émet un **Événement 'Fill Received'** (incluant `session_id_ref`).<br>\* **Parallélisation :** L'événement est distribué à l'**OM** (mise à jour du statut `Order`) et au **PM** (mise à jour `AcquisitionLot/Position`).<br>\* Le **PM** et l'**OM** soumettent l'unité de travail de mise à jour au **DIL**.<br>\* Le **DIL** soumet la tâche au **Job Manager**, spécifiant le **Pool I/O Real-Time** (Isolation des écritures transactionnelles vitales).<br>\* Le DIL exécute la transaction de base de données. |
| **14** | **Persistance des Données de Marché (Bulk I/O)** | Gérer l'écriture des **buffers de Snapshots/Ticks** en base de données en tâche de fond pour garantir que cette opération lourde n'affecte pas la boucle temps réel (étapes 10-13). | \* Le **LDH** soumet périodiquement la tâche de vidange de son buffer au **DIL**.<br>\* Le **DIL** soumet la tâche au **Job Manager**, spécifiant le **Pool I/O Bulk**.<br>\* Le **Thread Manager** alloue un thread du Pool I/O Bulk (basse priorité).<br>\* Le DIL exécute l'écriture massive des Snapshots. |
| **15** | **Surveillance du Système et Fin de Phase** | Surveiller l'état général et la fin de l'activité, et se préparer à la transition Post-Trade. | \* Le **Monitoring Module** collecte et agrège les `SystemMetric` (Latence, temps d'exécution des Jobs).<br>\* La boucle continue jusqu'à la réception de l'événement **`MARKET_CLOSE`** du **Market Clock**.<br>\* À la réception du signal : Le **System Manager** initie la transition vers la **Phase III (Post-Trade)**. |

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



