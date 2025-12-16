## Feuille de Route Détaillée (Roadmap / To-Do List)

### 1. Diagrammes de la Phase Pre-Trade (Bootstrapping)

**Nom du Package:** PHASE_01_BOOTSTRAPPING

| Étape | Séquence | Nom du Diagramme (Futur) | Objectif de la Séquence (Résumé) | Actions Clés |
| :---: | :---: | :--- | :--- | :--- |
| **1** | **Connectivité Critique** | `01-PHASE1-Connectivite-Critique` | Valider la **disponibilité** des services fondamentaux (DB, Courtier) et la **pertinence** du contexte de marché (Jour Ouvré). | Vérifier **DB** et **IBKR Gateway**. Persister **`MarketDayStatus`**. Si non-ouvré, transition vers `Off-Cycle`. |
| **2** | **Instanciation des Configs Globaux** | `02-PHASE1-Instanciation-Configs-Globaux` | Optimiser la lecture des configurations statiques et instancier les **Singletons globaux** (IBKR Gateway, LDH). | Lire **toutes les configs globales** en **un seul bloc**. Instancier et exécuter **H-Check unitaire** sur `IBKR Gateway` et `Live Data Hub`. |
| **3** | **Initialisation des Threads** | `03-PHASE1-Initialisation-Threads` | Allouer les ressources d'exécution critiques (**Pools de Threads**) et valider leur performance/priorité. | Créer les objets `PoolWorker` persistants (`CRITICAL`, `STANDARD`). Exécuter le **`HCheckPriorityTest`** sur le Pool CRITICAL. |
| **4** | **Instanciation des Managers Locaux** | `04-PHASE1-Instanciation-Managers-Locaux` | Créer la structure métier **par session** en instanciant les triplets (`PM`, `RM`, `OM`) et établir les **canaux de communication critiques**. | Boucler sur chaque `TradingSession`. Instancier `PM`, `RM`, et `OM`. Établir les liens de communication : **PM $\rightarrow$ OM**, **RM $\rightarrow$ OM**, **RM $\rightarrow$ PM**. Exécuter le **`HCheckSessionReady`**. |
| **5** | **Chargement Parallèle** | `05-PHASE1-Chargement-Parallele` | Charger l'état initial des données (Positions, Limites de Risque) de **toutes les sessions en parallèle** pour masquer la latence I/O. | Créer les Jobs `loadInitialState` (PM) et `loadRiskSnapshot` (RM) pour chaque session. Soumettre les Jobs au **Thread Manager** en mode **parallèle**. Lancer **`SM-evaluateBootstrapStatus`**. |
| **6** | **Initialisation Flux Temps Réel** | `06-PHASE1-Initialisation-Flux-Temps-Reel` | Établir la connexion physique au flux de prix et **valider** la preuve de vie (réception du premier `tick`) avant de valider la session. | Ordonner à l'`IBKR Gateway` de s'abonner. Exécuter le **`HCheckFirstTickReceived`** sur le **LDH** (avec Timeout). **Si échec** : Arrêt immédiat et fatal. |
| **7** | **Validation Croisée (HeartCheck)** | `07-PHASE1-Validation-Croisee-HeartCheck` | Effectuer la validation finale (HeartCheck) de la **cohérence métier** et de l'état opérationnel entre les managers. | Exécuter les vérifications unitaires et croisées (`ValidateRiskLimits`, `ValidatePortfolioState`). Lancer **`SM-evaluateBootstrapStatus`** (Point de non-retour sécurisé). |
| **8** | **Transition Mode Veille** | `08-PHASE2-Transition-Mode-Veille` | Faire passer le système à l'état **opérationnel de veille** et attendre l'événement temporel déclencheur de la phase In-Trade. | Mettre l'état du système à **`READY_FOR_TRADING`**. Démarrer la boucle de **Heartbeat**. Entrer en attente asynchrone (`Wait for MarketOpenEvent()`). |
---

### 2. Diagrammes de la Phase In-Trade (Temps Réel)

**Nom du Package:** PHASE_02_LIVE_EXECUTION

| Étape | Séquence/Module | Nom du Diagramme (Futur) | Objectif de la Séquence (Résumé) | Actions Clés |
| :---: | :---: | :--- | :--- | :--- |
| **9** | **Flux de Données Globaux** | `09-PHASE2-Flux-Donnees-Globaux` | Démarrer l'acquisition haute fréquence et distribuer les `Snapshots` agrégés dans les canaux **rapides** (Cache) et **lents** (Persistance Bulk). | Lancer l'écoute asynchrone des `Tick Data`. LDH reçoit, agrège en Snapshot. Distribution Fast-Lane (Cache) et Slow-Lane (Buffer DIL). |
| **9a** | **Flux Critique Fast-Lane** | `09a-PHASE2-Flux-Critique-FastLane` | Flux ultra-rapide et non bloquant conduisant les `MarketQuote` agrégés vers le `DataCache` via une queue asynchrone pour disponibilité immédiate. | Vérification de latence, agrégation en `MarketQuote`, `enqueue` non bloquant. Consommateur écrit dans le `DataCache`. |
| **9b** | **Persistance Bulk I/O** | `09b-PHASE2-Persistance-Bulk-IO` | Flux périodique et auditable qui transfère les buffers de données agrégées vers le `DIL` pour une persistance en masse (Bulk I/O) vers la base de données. | LDH accumule, soumet au DIL. DIL prépare, soumet au **Pool I/O Bulk** (basse priorité). |
| **10** | **Boucle Décision/Exécution** | `10-PHASE2-Boucle-Decision-Execution` | Assurer la **disponibilité immédiate et cohérente** des prix en mémoire via `SnapshotHeader` pour la décision. | Création du **`SnapshotHeader` complet** (bloc cohérent). `enqueue` non bloquant du `SnapshotHeader` vers la file de cache. |
| **10a** | **Surveillance d'Urgence** | `10a-PHASE2-Surveillance-Urgence` | Détection immédiate d'une violation de risque critique et exécution d'un ordre de liquidation avec **priorité maximale absolue**. | **RM** lit prix/position. `checkThresholds`. **Audit synchrone**. Soumettre Ordre d'Urgence (`CRITICAL`) à l'OM. |
| **10b** | **Stratégie Standard** | `10b-PHASE2-Strategie-Standard` | Exécuter de manière tactique les ordres de trading standards, en sélectionnant le moment optimal (timing) pour la soumission. | **PM** évalue le prix/timing. **Audit synchrone** de la décision. Soumettre Ordre Standard (`STANDARD`) à l'OM. |
| **11** | **Gestion des Exécutions (Fills)** | `11-PHASE2-Reception-Execution-Fill` | Réceptionner l'exécution de l'ordre (`Fill`) et orchestrer la mise à jour **atomique** et **critique** des structures de position et d'ordre. | Parallélisation : `Fill` $\to$ **OM** (Statut) et **PM** (Position). Coordination DIL. Persistance Atomique (**Pool I/O Real-Time**). |
| **--** | **Arbitrage et Transmission** | `OM-RouteOrderToBroker` (Référence Externe) | Transmettre les ordres de trading au courtier, en appliquant une **politique de priorité globale** (CRITICAL, STANDARD) et **sessionnelle** (Live vs Paper). | OM (Dequeue Processor) $\to$ **Global Order Router** $\to$ **Job Manager** (Pool I/O approprié) $\to$ **IBKR Gateway**. |
| **--** | **Surveillance du Système** | `{?}-PHASE2-Surveillance-Transition-PostTrade` | Surveiller l'état général du système et attendre la fin de l'activité. | **Monitoring Module** collecte `SystemMetric`. Attente de l'événement **`MARKET_CLOSE`**. Transition vers la Phase III. |
---

### 3. Diagrammes de la Phase Post-Trade (Audit & Clôture)

**Nom du Package:** PHASE_03_POST_TRADE

| Étape | Séquence/Module | Nom du Diagramme (Statut) | Objectif de la Séquence (Résumé) | Actions Clés |
| :---: | :---: | :--- | :--- | :--- |
| **12** | **Synchronisation et Audit Initial (Clôture Sûre)** | `12-PHASE3-Synchro-AuditInitial`| **Garantir l'état final atomique** et exécuter la **Réconciliation Finale** (Interne vs Courtier). | **Forcer la complétion** des Jobs I/O. **Réconciliation PM/IBKR**. **Si écart critique :** Alerte Manuelle et arrêt du processus. |
| **13** | **Persistance SessionBook Final** | `13-PHASE3-Persistance-SessionBook` | Enregistrer l'**état financier définitif** (`SettledSessionBook`) de la journée pour l'audit. | Générer le `SettledSessionBook`. Soumettre au `Job Manager` (Pool I/O Audit/Critical) pour persistance atomique. |
| **14** | **Persistance de l'État de Reprise** | `14-PHASE3-Persistance-Config-Cloture` | Sauvegarder l'**État de Configuration Final** critique (limites RM, état Throttlers) pour garantir un redémarrage sécurisé. | Générer la `session_config` finale. Soumettre au **DIL** (Pool I/O Critical). |
| **15** | **Arrêt Sécurisé et Transition** | `15-PHASE3-Arret-Securise` | Finaliser le processus Post-Trade en vérifiant la validation des écritures critiques et en mettant le système en **veille profonde (`Off-Cycle`)**. | Attendre la **double validation** des écritures 13 et 14. Loguer l'événement "System Shutdown". Basculer le système en phase **Off-Cycle**. |
---

### 4. Diagrammes de la Phase Pre-Market Setup (Stratégie)

**Nom du Package:** PHASE_04_PRE_MARKET_SETUP

| Étape | Séquence/Module | Nom du Diagramme (Statut) | Objectif de la Séquence (Résumé) | Actions Clés |
| :---: | :---: | :--- | :--- | :--- |
| **16** | **Déclenchement et Ingestion EOD** | `16-PHASE4-Ingestion-EOD-Init` | Démarrer le processus stratégique et ingérer les données de marché de fin de journée (EOD) les plus fiables et fraîches. | Market Clock réveille le système. Vérification DB et API Externe. Le **DIL** exécute l'Ingestion des données EOD et les persiste. |
| **17** | **Calcul de Stratégie (Target Plan)** | `17-PHASE4-Calcul-Strategie` | Exécuter le **Strategy Engine** pour déterminer le plan d'action du lendemain (**Portfolio Target**). | Vérifier l'état de l'audit initial (étape 14). Exécuter le **Strategy Engine** si c'est un jour de Rebalancement. |
| **18** | **Persistance Atomique du Target** | `18-PHASE4-Persistance-Atomique-Target` | Persister le **Plan d'Ordres Cible** (`TargetPortfolioDTO`) dans une transaction atomique isolée. | Soumettre le **Portfolio Target** au **DIL** pour Persistance Atomique (Pool I/O Critical). |
| **19** | **Finalisation et Déblocage** | `19-PHASE4-Transition-Pre-Bootstrap` | Finaliser la phase IV et mettre le système dans l'état final d'attente du *bootstrapping*. | Attendre la Validation de Persistance du Target. Mettre le système en état **`READY_TO_BOOTSTRAP`**. |
---

### 5. Diagrammes Optionnels (Robustesse & R&D)

**Nom du Package:** OPTIONAL_RND_ROBUSTNESS

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :---: | :---: | :--- | :--- |
| **20** | **Gestion des Erreurs (Kill-Switch)** | `20-CRITICAL-KillSwitch-Execution.puml` | Chemin exact d'une **CRITICAL\_ERROR** à l'annulation de tous les ordres **WORKING** par l'Order Manager. | Décomposition : **LDH** $\to$ **SM** $\to$ **OM** $\to$ **IBKR Gateway** (Action : Annulation/`CancelAllOrders`). |
| **21** | **Backtest & Optimisation** | `21-RND-Backtest-Optimization.puml` | Interaction entre le **Parametric Optimizer**, le **Backtest Engine** et la **Pipeline Core**. | Décomposition : **Parametric Optimizer** $\to$ **Backtest Engine** (Boucle) $\to$ **Pipeline Core**. |
