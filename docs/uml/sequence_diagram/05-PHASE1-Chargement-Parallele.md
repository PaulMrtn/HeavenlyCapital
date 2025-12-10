## `05-PHASE1-Chargement-Parallele`

<p align="center">
  <img src="img/05-PHASE1-Chargement-Parallele.png" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de charger l'état initial complet de toutes les sessions de trading **en parallèle**. Il vise à minimiser le temps de latence au démarrage en exécutant les opérations de lecture de base de données (I/O) de manière concurrente.

---

### 2. Contexte

Cette étape se situe immédiatement après l'**instanciation des managers locaux** (Phase 04) et utilise les **Pools de Threads** (initialisés en Phase 03). Elle est la première phase à exploiter la parallélisation pour préparer les managers (`PM` et `RM`) avec les données nécessaires à leur fonctionnement.

---

### 3. Logique Générale

Le **`System Manager`** délègue entièrement la charge de travail au **`Thread Manager`**. Pour chaque session active :

1.  Deux commandes de travail (`Job`) sont créées : une pour le **`Portfolio Manager`** (`loadInitialState`) et une pour le **`Risk Monitor`** (`loadRiskSnapshot`).
2.  Ces commandes sont soumises au `Thread Manager` avec l'instruction d'exécution **parallèle**.
3.  Des **PoolWorkers** distincts (issus des pools alloués) exécutent les tâches, demandant simultanément leurs données respectives au `Database Connector`.
4.  Une fois les données reçues, chaque manager (PM et RM) effectue son **contrôle d'intégrité métier** (`HCheckDataIntegrity`) sur les objets chargés.
5.  Le `Thread Manager` attend la complétude de **toutes** les tâches soumises avant de notifier le `System Manager` du succès de l'opération.

---

### 4. Règles Critiques

* **Non-Blocage :** Le thread du **`System Manager`** ne doit pas être bloqué par l'attente de la base de données. Il est libéré dès la soumission des tâches.
* **I/O Maximisation :** Le parallélisme est essentiel car les opérations de lecture de la base de données (I/O) sont les plus lentes et bénéficient le plus de l’exécution simultanée.
* **Vérification Métier :** Le **`HCheckDataIntegrity`** est un garde-fou crucial. Il garantit que les données, bien que techniquement valides dans la base, sont **opérationnellement cohérentes** (ex. : la somme des lots correspond à la position totale) avant la mise en service du manager.
* **Point de Synchronisation :** La phase ne peut se terminer que lorsque le `Thread Manager` confirme que **toutes** les sessions ont chargé et validé leurs données.

---

### 5. Conclusion

Ce module garantit un **démarrage rapide** du système en gérant efficacement l'attente I/O. Il assure également que chaque manager local (PM et RM) entre en service avec un **état initial validé et cohérent** avec les règles de la stratégie, préparant ainsi le système pour l'étape finale de validation croisée.
