

## Stratégie de Modélisation des Diagrammes de Séquence

### 1. Liste des Scénarios Fonctionnels Clés

| Bloc Fonctionnel | Scénarios de Diagramme de Séquence (DDS) | Objectif du DDS |
| :--- | :--- | :--- |
| **A. Initialisation & Résilience** (Phase I) | **A.1** `DDS_A1_Bootstrapping_System_OK` | Séquence de démarrage jusqu'à l'état `System Ready`. |
| | **A.2** `DDS_A2_Connectivite_Echouee_CRITIQUE` | Gestion d'un échec persistant de la connexion DB/IBKR (logique de Retry et Shutdown). |
| | **A.3** `DDS_A3_Chargement_Session_Jour_Ferie` | Processus de vérification de jour ouvré et bascule immédiate en `Off-Cycle`. |
| **B. Flux Temps Réel & Risque** (Phase II) | **B.1** `DDS_B1_Acquisition_Tick_Distribution_Fast_Slow` | Réception du Tick, génération Snapshot, Fork vers Cache et Queue d'écriture (Bulk I/O). |
| | **B.2** `DDS_B2_Declenchement_StopLoss_Urgence` | Lecture du Cache, condition de risque atteinte, émission Ordre d'Urgence (Priorité Max). |
| | **B.3** `DDS_B3_Latence_Flux_Critique_Kill_Switch` | Détection Latence Critique par Live Data Hub $\rightarrow$ Alerte $\rightarrow$ Déclenchement `Kill Switch`. |
| **C. Ordre & Exécution Atomique** (Phase II) | **C.1** `DDS_C1_Envoi_Ordre_Standard_Priorisation` | Ordre Standard (via PM) $\rightarrow$ OM $\rightarrow$ Job Manager (Arbitrage) $\rightarrow$ IBKR Gateway. |
| | **C.2** `DDS_C2_Reception_Fill_Mise_a_Jour_Atomique` | Réception Fill $\rightarrow$ Mise à jour OM/PM (Parallèle) $\rightarrow$ Persistance Critique (Pool I/O Real-Time). **CRITIQUE**. |
| **D. Décision & Audit Fin de Journée** (Phase III) | **D.1** `DDS_D1_Cloture_Synchronisation_Audit_Financier` | Signal `MARKET_CLOSE` $\rightarrow$ Synchronisation I/O Critique (Attente) $\rightarrow$ Réconciliation PM. |
| | **D.2** `DDS_D2_Execution_Strategie_Target_Persistance_ATOMIQUE` | Jour de Rebalancement $\rightarrow$ Lancement Strategy Engine $\rightarrow$ Calcul Target $\rightarrow$ Persistance du Target et Config (Pool I/O Post-Trade). |


##  Roadmap Détaillée et Check-List UML


### A. Bloc Initialisation & Résilience (Phase I)

| $\checkmark$ | Fichier (Filename) | Description Détaillée |
| :--- | :--- | :--- |
| [ ] | **DDS_A1_Bootstrapping_System_OK.md** | 1. `Market Clock` envoie `SYSTEM_WAKEUP` au `System Manager`. 2. Vérifications séquentielle `Database Connector` (Retry OK) puis `IBKR Gateway` (Retry OK). 3. `System Manager` calcule `MarketDayStatus` et le persiste (via DIL). 4. Boucle d'instanciation/injection de dépendances (PM, RM, OM) via `Session Manager`. 5. Lancement des tâches de chargement de données (PM/RM) et de test de flux (IBKR) en **parallèle**. 6. Synchronisation et attente du signal `MARKET_OPEN`. |
| [ ] | **DDS_A2_Connectivite_Echouee_CRITIQUE.md** | 1. Séquence de l'étape A.1. 2. Échec de la connexion DB (max_retry atteint). 3. `Database Connector` notifie `System Manager`. 4. `System Manager` enregistre `CRITICAL_ERROR` (via `Log Service`) et notifie `Notification Manager`. 5. `System Manager` bascule l'état `TradingSystem` à `ERROR` et s'arrête. |
| [ ] | **DDS_A3_Chargement_Session_Jour_Ferie.md** | 1. Séquence de l'étape A.1 jusqu'au point de contrôle `MarketDayStatus`. 2. `System Manager` vérifie `is_trading_day == FALSE`. 3. Persistance du `MarketDayStatus` (via DIL). 4. `System Manager` envoie un message de changement de statut (`SESSION_STATUS_UPDATE`) au `Session Manager`. 5. `System Manager` bascule à `Off-Cycle` sans instancier les sessions. |

---

### B. Bloc Flux Temps Réel & Risque (Phase II - Fast Lane)

| $\checkmark$ | Fichier (Filename) | Description Détaillée |
| :--- | :--- | :--- |
| [ ] | **DDS_B1_Acquisition_Tick_Distribution_Fast_Slow.md** | 1. `IBKR Gateway` reçoit `TickData` et l'envoie à `Live Data Hub`. 2. `Live Data Hub` effectue la vérification de latence (Self-Check). 3. Génération du `SnapshotHeader` et des `MarketQuote`. 4. **Nœud de Fork** : Envoi parallèle vers **a)** `Cache Interface` (Fast Lane) et **b)** `Buffer Interface` (Slow Lane). 5. Persistance différée des `Snapshot` : `Live Data Hub` $\rightarrow$ `DIL` $\rightarrow$ `Job Manager` (spécifiant `Pool I/O Bulk`). |
| [ ] | **DDS_B2_Declenchement_StopLoss_Urgence.md** | 1. `Risk Monitor` lit le prix le plus récent via `ICacheReader` du `Live Data Hub`. 2. `Risk Monitor` lit l'état de la position via `IPortfolioStateReader` du `Portfolio Manager`. 3. Condition `Stop-Loss` atteinte. 4. `Risk Monitor` crée un `Ordre d'Urgence` (Priorité Max) et l'envoie à `Order Manager`. 5. `Order Manager` soumet l'ordre au `Job Manager` (via `IJobSubmission`). 6. `Job Manager` utilise la priorité pour allouer immédiatement au `Pool I/O Critical` $\rightarrow$ `IBKR Order Sender` (via `IBKR Gateway`). |
| [ ] | **DDS_B3_Latence_Flux_Critique_Kill_Switch.md** | 1. Séquence B.1 : `Live Data Hub` détecte `Latence Critique` lors du Self-Check. 2. `Live Data Hub` émet `CRITICAL_ERROR` au `System Manager`. 3. `System Manager` ordonne au `Job Manager` d'exécuter la séquence `Kill Switch` (Annulation de tous les ordres via `IBKR Gateway`). 4. `System Manager` bascule l'état à `STOPPED`. |

---

### C. Bloc Ordre & Exécution Atomique (Phase II - Critical Lane)

| $\checkmark$ | Fichier (Filename) | Description Détaillée |
| :--- | :--- | :--- |
| [ ] | **DDS_C1_Envoi_Ordre_Standard_Priorisation.md** | 1. Le `Portfolio Manager` génère un `Ordre Standard` (Rééquilibrage) et l'envoie à `Order Manager`. 2. `Order Manager` crée l'objet `Order` (avec ID interne). 3. `Order Manager` soumet l'ordre (via `IJobSubmission`) au `Job Manager`. 4. `Job Manager` alloue au `Pool I/O Critical` (si prioritaire ou si file vide). 5. Exécution : `Job Manager` $\rightarrow$ `IBKR Order Sender` $\rightarrow$ `IBKR Gateway`. 6. `IBKR Gateway` retourne `broker_order_id` (mise à jour de l'objet `Order` via `Order Manager`). |
| [ ] | **DDS_C2_Reception_Fill_Mise_a_Jour_Atomique.md** | 1. `IBKR Gateway` reçoit `Fill` et émet l'événement `FILL_RECEIVED` (avec `session_id_ref`). 2. **Nœud de Fork** : Envoi parallèle vers **a)** `Order Manager` et **b)** `Portfolio Manager`. 3. **a)** `Order Manager` met à jour `Order.filled_qty`, `status`. 4. **b)** `Portfolio Manager` exécute la logique comptable : met à jour `Position`, crée/met à jour `AcquisitionLot` / `RealizationLot`. 5. **Synchronisation** (Join) : L'unité de travail PM/OM est soumise au `DIL` (via `IDatabaseWriter`). 6. `DIL` soumet au `Job Manager` (spécifiant `Pool I/O Real-Time`). **Cette persistance est atomique (ACID)**. |

---

### D. Bloc Décision & Audit Fin de Journée (Phase III)

| $\checkmark$ | Fichier (Filename) | Description Détaillée |
| :--- | :--- | :--- |
| [ ] | **DDS_D1_Cloture_Synchronisation_Audit_Financier.md** | 1. `Market Clock` envoie `MARKET_CLOSE` au `System Manager`. 2. `System Manager` envoie l'ordre de **synchronisation critique** au `Job Manager` (attendre la fin de tous les jobs `Pool I/O Real-Time` et vidage du `Bulk Buffer`). 3. **Attente Bloquante** (Barrière de Synchronisation). 4. `Job Manager` confirme la validation I/O. 5. `Portfolio Manager` exécute la **Réconciliation Finale** avec `IBKR Gateway`. 6. `PM` émet `DATA_INTEGRITY_CHECK` (OK ou Alerte Critique) via `Log Service`. |
| [ ] | **DDS_D2_Execution_Strategie_Target_Persistance_ATOMIQUE.md** | 1. `System Manager` vérifie `TradingCalendar` (`is_rebalancing_day == TRUE`). 2. `System Manager` ordonne au `Strategy Engine` d'exécuter. 3. `Strategy Engine` lance l'exécution de la `Pipeline Core` (via `IPipelineExecutor`). 4. `Pipeline Manager` retourne le `PortfolioTarget`. 5. `Strategy Engine` soumet le `PortfolioTarget` au `Portfolio Manager` (via `IPortfolioTargetSubmitter`) pour traduction en ordres (persistance atomique du plan). 6. **Persistance Atomique** : `Session Manager` persiste l'état final de la `TradingSession.session_config` et le `Target` (via DIL) en spécifiant le **Pool I/O Post-Trade**. 7. Validation de la persistance $\rightarrow$ `System Manager` bascule en `Off-Cycle`. |

---

## 💡 Remarques sur la Modélisation UML

### Utilisation de UML 2.0 pour la Séquence

Dans vos diagrammes de séquence, utilisez les notations suivantes pour maximiser la précision :

| Concept | Notation UML | Composant Cible |
| :--- | :--- | :--- |
| **Opération Asynchrone (Non Bloquante)** | Ligne avec tête de flèche ouverte (Ex: `Live Data Hub` $\rightarrow$ `DIL`) | Persistance Bulk (B.1) ou Envoi d'ordre (C.1). |
| **Opération Synchrone (Bloquante)** | Ligne pleine avec tête de flèche pleine (Ex: `System Manager` $\rightarrow$ `Database Connector`) | Vérification de connexion (A.1). |
| **Parallélisation (Fork)** | `par` (Fragment d'Interaction Parallèle) | Distribution du Snapshot vers Cache et Buffer (B.1), Réception du Fill par OM et PM (C.2). |
| **Condition** | `alt` (Fragment d'Interaction Alternative) | Contrôle `is_trading_day == TRUE/FALSE` (A.3), Condition `Stop-Loss` atteinte (B.2). |
| **Boucle de Retry** | `loop` (Fragment d'Interaction Boucle) | Tentatives de reconnexion DB/IBKR (A.2). |
| **Référence à un autre DDS** | `ref` (Fragment d'Interaction Référence) | Le scénario D.2 peut faire référence au scénario C.1 (soumission d'ordre) si l'exécution des ordres est incluse. |
