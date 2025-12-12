## `10-PHASE2-Boucle-Decision-Execution`

<p align="center">
  <img src="../img/10-PHASE2-Boucle-Decision-Execution.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de déterminer et de déclencher les actions d'exécution et de gestion des risques du système, en réponse immédiate à la mise à jour des prix de marché. Il garantit que le contrôle du risque et l'évaluation de la stratégie sont exécutés en **parallèle** et que la soumission des ordres est **non bloquante**.

---


### 2. Contexte

Ce module s'inscrit directement après la Phase 09 (distribution des données Fast-Lane). Il existe pour exploiter la très faible latence des prix disponibles dans le `DataCache` et traduire cette donnée brute en décisions d'exécution (ordres de trading).

---


### 3. Logique Générale

Le fonctionnement repose sur l'orchestration du `ThreadManager` et l'exploitation de mécanismes asynchrones :

1.  **Déclenchement :** La boucle de décision est activée par un événement **asynchrone** (`marketQuoteUpdated`) émis par le `DataCache` dès qu'une nouvelle cotation est écrite (à la fin de la séquence 09a). Cet événement signale au `ThreadManager` qu'un nouveau cycle de décision peut commencer.
2.  **Parallélisme d'Exécution :** Le `ThreadManager` alloue immédiatement des threads dédiés à l'instance du `RiskMonitor` et à celle du `PortfolioManager`, permettant à leurs logiques respectives de s'exécuter **simultanément**.
3.  **Soumission Non Bloquante :** Chaque manager dépose tout ordre généré (Urgent ou Standard) dans la **`OrderInputQueue`** asynchrone. Cette queue sert de zone tampon ultra-rapide, garantissant que les threads des managers sont libérés immédiatement pour être recyclés.
4.  **Consommation :** L'OMS (Order Manager System) consomme cette queue via ses propres threads, lançant la séquence d'arbitrage et d'exécution (Séquence 11).

---


### 4. Règles Critiques

* **Priorité Asynchrone :** L'événement déclencheur (`marketQuoteUpdated`) doit être asynchrone pour ne jamais bloquer le thread d'écriture du cache (Pool I/O Real-Time).
* **Contrainte de Parallélisme :** Le Risk Monitor (`10a`) et le Portfolio Manager (`10b`) doivent toujours s'exécuter en parallèle (grâce à `allocateThreads`) pour minimiser la latence globale de la décision.
* **Isolation de la Congestion :** La soumission des ordres par les managers (`enqueueOrder`) doit se faire vers une **Queue Non-Bloquante** (`OrderInputQueue`). Ceci élimine tout risque de congestion à l'entrée de l'Order Manager, assurant que les threads du RM/PM sont libérés instantanément.
* **Règles du PM :** Le Portfolio Manager conditionne sa logique stratégique par la lecture de l'état de session. S'il s'agit d'un jour de rééquilibrage, il exécute la tactique des ordres de rééquilibrage pré-chargés. Sinon, il peut rester silencieux ou exécuter d'autres ordres standards.
* **Libération de Threads :** Une fois qu'un manager a soumis son ordre à la queue asynchrone, son thread est considéré comme terminé et est immédiatement mis à disposition pour recyclage par le `ThreadManager`.

---

### 5. Description des Fonctions

* **`marketQuoteUpdated(asset_id, quote_id)`** : Événement asynchrone notifiant la disponibilité d'un nouveau prix. Le thread ayant mis à jour le cache signale au `ThreadManager` que le travail est prêt.

* **`allocateThreads(RM, PM)`** : Le `ThreadManager` soumet les méthodes d'exécution du RM (`runRiskCheck`) et du PM (`runStrategy`) à deux threads séparés et simultanés de son pool de calcul. L'opération est synchrone pour le `ThreadManager` qui confirme le lancement des deux processus parallèles.

* **`REF: 10a-Surveillance-Urgence` (Risk Monitor)** : Le thread exécute la logique du RM. Celle-ci consiste à lire le prix, lire l'état de la position (`PositionManager`), évaluer les limites Stop/Take et créer un ordre d'urgence si nécessaire.

* **`REF: 10b-Strategie-Standard` (Portfolio Manager)** : Le thread exécute la logique du PM. Celle-ci inclut la vérification des conditions de la stratégie (en tenant compte du statut de rééquilibrage) et la création d'un ordre standard si les critères sont remplis.

* **`enqueueOrder(Order, Priority)`** : La fonction par laquelle le manager soumet l'ordre. C'est une opération **asynchrone et non bloquante** qui garantit le transfert de l'objet `Order` à la queue. Dès que l'ordre est en queue, le thread du manager est libéré.

* **`dequeueOrder()`** : Opération continue effectuée par les threads internes de l'OM. Il retire les ordres de la queue (en respectant la priorité) pour commencer la phase de validation, d'arbitrage et d'exécution (Séquence 11).
