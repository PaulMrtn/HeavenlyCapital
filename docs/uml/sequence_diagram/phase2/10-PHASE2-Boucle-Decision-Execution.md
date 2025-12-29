## `10-PHASE2-Boucle-Decision-Execution`

<p align="center">
  <img src="../img/10-PHASE2-Boucle-Decision-Execution.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de garantir la **disponibilité immédiate et cohérente** des prix de marché les plus récents dans le cache en mémoire (`DataCache`). L'objectif est d'atteindre une **latence minimale absolue** en assurant que le thread de réception de données ne soit **jamais bloqué** par les opérations d'écriture et en transmettant l'état du marché par **blocs cohérents**.

---

### 2. Contexte

Ce module est le **cœur opérationnel** de la Phase II (In-Trade). Il s'inscrit directement dans la boucle principale d'exécution. Activé dès l'ouverture du marché, il représente la **Fast-Lane** des données, essentielle pour la prise de décision en temps réel et la surveillance du risque. Il est **isolé** de toutes les opérations lentes (Bulk I/O base de données), mais assure la **cohérence en bloc** des données transitées.

---

### 3. Logique Générale

Le fonctionnement repose sur un modèle **Producteur/Consommateur** découplé par une **Queue Non Bloquante** (`FastLaneQueue`) :

* Le **Producteur** (`:LiveDataHub`) reçoit les `TickData` bruts, vérifie leur intégrité et leur latence. Si le flux est sain, il agrège les Ticks accumulés localement et crée l'objet **`SnapshotHeader` complet** (contenant tous les `MarketQuote` consolidés pour l'instant $T$). Il **dépose** cet objet `SnapshotHeader` complet dans la `FastLaneQueue` de manière asynchrone et continue immédiatement à écouter le prochain Tick, sans attendre la fin de l'écriture.
* Le **Consommateur** (un thread dédié du `Pool I/O Real-Time`) est en **boucle d'écoute persistante** sur la `:FastLaneQueue`. Dès qu'un `SnapshotHeader` est disponible, il le retire de la queue et exécute son unique mission : l'écriture en **Bulk I/O en mémoire** de tous les `MarketQuote` contenus dans le `SnapshotHeader` vers le `DataCache`.

---

### 4. Règles Critiques

* **Priorité Sécurité :** La vérification de la latence (`checkLatency()`) est exécutée **avant** toute agrégation. En cas de défaillance, l'enregistrement de l'incident (`logCriticalError`) est synchrone et prioritaire avant d'alerter le `SystemManager` (`REF: SM-HandleCriticalDataLoss`).
* **Non-Blocage Absolu :** L'opération clé (`enqueue` sur la `FastLaneQueue`) doit être **non bloquante** pour le thread du `LiveDataHub`. Le thread agrégateur ne doit jamais perdre de temps à attendre l'I/O du cache.
* **Cohérence de Bloc :** Le transit et l'écriture des données se font au niveau de l'objet **`SnapshotHeader`**. Ceci garantit que l'ensemble des cotations utilisées par le Consommateur appartient au même instant $T$.
* **Isolation des Tâches :** Le calcul intensif (agrégation et création du `SnapshotHeader`) est effectué par le Producteur (`LiveDataHub`), tandis que l'I/O critique (écriture en cache) est effectuée par le Consommateur (`ThreadManager`).

---

### 5. Conclusion

Ce module garantit un flux de prix **déterministe, ultra-rapide et cohérent** pour le système. Il assure que des blocs complets de données de marché (`SnapshotHeader`) sont disponibles en mémoire avec la plus faible latence possible pour la surveillance du risque (Risk Monitor) et l'exécution des stratégies (Portfolio Manager), en isolant la charge de calcul de la charge d'écriture en mémoire.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | snapshotHeaderUpdated(snapshot_id) | Data Cache | Thread Manager | Notifie le gestionnaire de threads qu'une nouvelle version cohérente des données de marché (snapshot) est disponible dans le cache. |
| 2 | allocateThreads(RM, PM) | Thread Manager | Thread Manager | Auto-appel permettant d'allouer les ressources de calcul nécessaires aux modules Risk Monitor (RM) et Portfolio Manager (PM) pour traiter le nouveau snapshot. |
| ref | 10a-PHASE2-Surveillance-Urgence | Thread Manager | Risk Monitor | Bloc de référence (parallèle) déclenchant la logique de surveillance critique et de gestion des risques en temps réel. |
| ref | 10b-PHASE2-Strategie-Standard | Thread Manager | Portfolio Manager | Bloc de référence (parallèle) déclenchant l'exécution des stratégies d'investissement basées sur les dernières données de marché. |
| 3 | enqueueOrder(Order, Priority) | Risk Monitor | OrderInputQueue | Envoie un ordre (généralement d'urgence ou de couverture) vers la file d'attente avec un niveau de priorité spécifique. |
| 4 | enqueueOrder(Order, Priority) | Portfolio Manager | OrderInputQueue | Envoie les ordres générés par la stratégie standard vers la file d'attente pour exécution ultérieure. |
| 5 | dequeueOrder() | Order Manager | OrderInputQueue | Le gestionnaire d'ordres récupère les ordres en attente dans la queue (selon la priorité) pour les transmettre au marché. |
