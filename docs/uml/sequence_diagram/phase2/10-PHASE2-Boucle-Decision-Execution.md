## `10-PHASE2-Boucle-Decision-Execution`

<p align="center">
  <img src="../img/10-PHASE2-Boucle-Decision-Execution.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'assurer l'exécution **parallèle** et **non bloquante** de l'ensemble de la boucle de décision du système de trading. Il garantit que le contrôle du risque et l'évaluation de la stratégie sont déclenchés de manière synchronisée par l'état global du marché.

---

### 2. Contexte

Ce module est le **cœur de l'intelligence** opérationnelle du système. Il s'inscrit directement comme la réponse en temps réel à la mise à jour des prix (`SnapshotHeaderUpdated`) par la *Fast-Lane* (Séquence 09a). Il est conçu pour orchestrer les managers (`RiskMonitor` et `PortfolioManager`) sans latence d'attente mutuelle, traduisant les données de prix rapides en ordres d'exécution.

---

### 3. Logique Générale

Le fonctionnement repose sur l'exploitation d'une architecture Producteur/Consommateur asynchrone à deux niveaux :

1.  **Déclenchement Global :** L'itération de la boucle est initiée par un événement **asynchrone** (`snapshotHeaderUpdated`) émis par le `DataCache`. Ce signal indique que l'instantané complet du marché pour un temps $T$ est prêt.
2.  **Parallélisme d'Exécution :** Le `ThreadManager` alloue immédiatement des threads distincts à l'instance du `RiskMonitor` et à celle du `PortfolioManager`. Les deux managers exécutent leurs logiques (`REF: 10a` et `REF: 10b`) **simultanément** pour minimiser la latence globale.
3.  **Soumission Non Bloquante (Queue) :** Si un manager génère un ordre, il le dépose immédiatement via la fonction `enqueueOrder` dans la **`OrderInputQueue`**. Cette file d'attente non bloquante découple les managers de l'Order Manager (OM), évitant la congestion et libérant les threads de calcul pour le recyclage.
4.  **Consommation OM :** L'OM fonctionne en boucle de consommation continue (`dequeueOrder`) sur la `OrderInputQueue`, commençant la phase d'arbitrage et d'exécution des ordres (Séquence 11) de manière asynchrone par rapport à la boucle de décision.
8
---

### 4. Règles Critiques

* **Granularité du Déclenchement :** Le déclencheur doit être le **`snapshotHeaderUpdated(snapshot_id)`** (ou son équivalent logique) et non une simple mise à jour d'actif, garantissant que les décisions sont prises sur l'état global et cohérent du marché.
* **Contrainte de Parallélisme :** L'étape `allocateThreads` doit garantir l'exécution stricte des managers en parallèle pour assurer que le contrôle du risque ne soit pas retardé par le calcul de stratégie.
* **Isolation de Congestion :** L'utilisation de la **`OrderInputQueue`** est obligatoire pour la soumission des ordres. Cette file d'attente élimine le risque de contention entre les threads du RM et du PM au point d'entrée de l'OM.
* **Recyclage de Threads :** Immédiatement après avoir déposé l'ordre dans la file d'attente (via `enqueueOrder`), le thread du manager doit se terminer, permettant au `ThreadManager` de le recycler pour la prochaine itération de la boucle de décision.
* **Logique du PM :** La logique du Portfolio Manager (`10b`) est conditionnelle à l'état de la session (`is_rebalancing_day`). S'il y a rééquilibrage, il exécute la tactique des ordres pré-chargés.

---

### 5. Description des Fonctions

* **`snapshotHeaderUpdated(snapshot_id)`** : Événement asynchrone signalant que l'ensemble des cotations (`MarketQuote` pour tous les actifs) d'un instant $T$ est prêt dans le cache. Il déclenche le `ThreadManager`.

* **`allocateThreads(RM, PM)`** : Soumission des fonctions d'exécution du RM et du PM à deux threads distincts du pool de calcul, lançant l'exécution parallèle.

* **`REF: 10a-Surveillance-Urgence`** : Renvoient aux séquences détaillées où le manager lit les données du cache et exécute sa logique métier (surveillance des risques vs. opportunités stratégiques).

* **`enqueueOrder(Order, Priority)`** : La fonction critique de soumission. L'ordre est inséré dans la file d'attente. Cette opération est ultra-rapide et garantit la libération immédiate du thread du manager, transformant ainsi une attente potentielle en un transfert instantané.

* **`dequeueOrder()`** : Fonction exécutée par les threads internes de l'OM. Il retire les ordres de la queue (en respectant la priorité) pour lancer l'arbitrage et le processus d'exécution.
