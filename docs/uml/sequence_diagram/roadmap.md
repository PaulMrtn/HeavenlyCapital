##  Feuille de Route Détaillée (Roadmap / To-Do List)

### 1. Diagrammes Transversaux et Processus Critiques

**Nom du Package:** CORE_CRITICAL_PROCESSES

Ces diagrammes doivent être réalisés en premier, car ils sont utilisés dans les phases Pre-Trade, In-Trade et Post-Trade.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| **01** | `01-CORE-Check-Connectivite-Critique.puml` | Modélise la vérification séquentielle de la connexion **DB** et **IBKR**, incluant la logique de Retry et la notification d'erreur. | * Décomposition : **System Manager** $\to$ **Database Connector** $\to$ **IBKR Gateway**. * Détail : Ajouter les boucles de **Retry** et la condition d'arrêt (CRITICAL\_ERROR). |
| **02** | `02-CORE-Persistance-Atomique-FILL.puml` | Décrit le traitement asynchrone d'une exécution de bout en bout, de l'**IBKR Gateway** à la persistance en base de données. | * Décomposition : **IBKR Gateway** $\to$ **Event** $\to$ **Order Manager** / **Portfolio Manager**. * Détail : Mettre en évidence la soumission au **Job Manager** (Pool I/O Real-Time) et l'écriture **DIL** $\to$ **Database**. |
| **03** | `03-CORE-Soumission-Job-Prioritaire.puml` | Illustre la réception d'un ordre (Urgent ou Standard) par l'**Order Manager** et l'arbitrage par le **Job Manager**. | * Décomposition : **Order Manager** $\to$ **Job Manager** $\to$ **Thread Manager** $\to$ **IBKR Gateway**. * Détail : Utiliser des fragments alt pour l'arbitrage **Prioritaire / Standard** et l'allocation du **Pool I/O Critical**. |
| **04** | `04-CORE-Persistance-Bulk-Snapshot.puml` | Décrit le processus d'ingestion massive des **Snapshots** dans le **Pool I/O Bulk** du **DIL** pour isoler le **Bulk I/O** du **Critical I/O**. | * Décomposition : **Live Data Hub** $\to$ **DIL** $\to$ **Job Manager** (Pool I/O Bulk) $\to$ **Database**. |

---

### 2. Diagrammes de la Phase Pre-Trade (Bootstrapping)

**Nom du Package:** PHASE_01_BOOTSTRAPPING

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| **05** | `05-PHASE1-Bootstrapping-Global.puml` | Séquence principale du System Manager : Réveil, vérifications critiques (ref: 01), calcul `MarketDayStatus` et STOP si jour non ouvré. | Inclure la vérification `MarketDayStatus` avec un fragment alt pour la transition `Off-Cycle`. |
| **06** | `06-PHASE1-Bootstrapping-Threads.puml` |Modélise l'initialisation des Pools de Threads I/O CRITICAL/STANDARD par le Thread Manager (TM) au démarrage. | Montrer la lecture de la configuration en DB et les **boucles de création persistantes** des threads (PoolWorker). |
| **07** | `07-PHASE1-Initialisation-Session-Parallele.puml` | Modélise l'instanciation des sessions, des managers locaux (PM, RM, OM) et le chargement des données en parallèle. **(Utilisera les threads créés en 06)** | Montrer le lancement parallèle des requêtes DAL et le canal `Gateway` (Branche B). |

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








