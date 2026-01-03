## `09a-PHASE2-Flux-Critique-FastLane`

<p align="center">
  <img src="../img/09a-PHASE2-Flux-Critique-FastLane.jpg" width="900">
</p>


---

### 1. Objectif

La finalité de ce module est de garantir la **disponibilité immédiate** des prix de marché les plus récents dans le cache en mémoire (`DataCache`), avec une **latence minimale**, en assurant que le thread de réception de données ne soit **jamais bloqué** par des opérations d'écriture ou de logging.

---

### 2. Contexte

Ce module est le **cœur opérationnel** de la Phase II (In-Trade). Il s'inscrit directement dans la boucle principale d'exécution. Il est activé dès l'ouverture du marché et représente la **Fast-Lane** des données, qui est critique pour la prise de décision en temps réel et la surveillance du risque. Il est **isolé** de toutes les opérations lentes (Bulk I/O, persistance base de données) et intègre également des mécanismes d'autodéfense contre la volatilité extrême (burst de ticks).

---

### 3. Logique Générale

Le découplage Producteur / Consommateur est découplé par une **Queue Non Bloquante** (`FastLaneQueue`) de type SPSC (Single Producer / Single Consumer), garantissant une latence minimale, l’absence de contention et un comportement strictement déterministe :

* **Le Producteur (`LiveDataHub`)** reçoit les `TickData` bruts, applique une politique de **Backpressure (Drop Oldest)** en cas de saturation, puis vérifie la latence. Si le flux est sain, il agrège les Ticks en un objet **`MarketQuote`** immuable. En cas de latence, il bascule en **Mode Dégradé** via le `SystemManager`. Il **dépose** ensuite ce `MarketQuote` dans la `FastLaneQueue` de manière asynchrone.
* **Le Consommateur** (un thread dédié du `ThreadManager` / `Pool I/O Real-Time`) est en **boucle d'écoute persistante** sur la `FastLaneQueue`. Dès qu'un `MarketQuote` est disponible, il le retire et l'écrit dans le `DataCache`.

---

### 4.1 Règles Critiques

* **Priorité Sécurité & Backpressure :** La gestion de charge (Drop Oldest) et la vérification de la latence (`checkLatency()`) sont exécutées **avant** toute agrégation. En cas de latence critique, le `LiveDataHub` alerte le `SystemManager` qui peut ordonner un basculement en **Mode Dégradé**.
* **Non-Blocage Absolu :** L'opération d'enregistrement des incidents (`logEvent`) est strictement **asynchrone**. L'opération `enqueue` sur la `FastLaneQueue` reste non bloquante, garantissant que l'agrégateur absorbe le flux maximum sans gigue (jitter).
* **Isolation des Tâches :** Le calcul (agrégation en `MarketQuote`) est effectué par le Producteur, tandis que l'I/O (écriture cache) est effectuée par le Consommateur, isolant le CPU du temps I/O.
* **Structure de Données :** Seul l'objet **`MarketQuote`** (cotation consolidée immuable) transite par la queue, minimisant la charge utile.
* **Intégrité des Données :** Seul l'objet MarketQuote transite par la queue. Il est immuable et versionné dès sa création ; les consommateurs accèdent exclusivement à des versions validées, garantissant une isolation totale contre les données corrompues ou incomplètes.

### 4.2 Politique de Gestion de Charge et Dégradation Contrôlée

Le **Live Data Hub (LDH)** applique une politique explicite de gestion de charge visant à garantir **la continuité de la diffusion des données de marché**, y compris en conditions de volatilité extrême, sans jamais bloquer le producteur ni interrompre le système.

**Principe Général :**
  * Le flux de ticks entrants est absorbé via une **queue bornée** en amont de l’agrégation. En cas de saturation, la politique **Drop Oldest** est appliquée afin de préserver en priorité les données de marché les plus récentes.
  * Les seuils de capacité de la queue, ainsi que les critères précis de dégradation, ne sont **pas figés à ce stade** et seront calibrés lors des **phases de stress test et de mock de charge**, en fonction des caractéristiques réelles du marché et de la fréquence de snapshot retenue (ex. 1 minute).

**Niveaux de Fonctionnement :** La Fast-Lane reste non bloquante en toutes circonstances, garantissant que l’agrégation critique reste prioritaire. Le système supporte plusieurs niveaux de fonctionnement, activés dynamiquement sans interruption :

* **Fonctionnement nominal**
  * Agrégation complète des données de marché (bid, ask, volumes, last price)
  * Snapshots produits à l’intervalle nominal
  * Aucun drop significatif, métriques stables

* **Stress de marché (volatilité élevée)**
  * Politique Drop Oldest active sur la queue d’entrée
  * Agrégation maintenue sans interruption
  * Le `MetricManager` est notifié d’un taux de drop élevé
  * Le `RiskMonitor` et le `PortfolioManager` continuent d’opérer sur le **dernier snapshot valide**

* **Stress extrême**
  * Toujours aucun blocage ni arrêt du système
  * Maintien impératif de la fraîcheur des snapshots
  * Dégradation contrôlée de l’agrégation (ex. priorité au `last_price`, enrichissement bid/ask optionnel)
  * Snapshots potentiellement moins riches mais **toujours exploitables pour la gestion du risque**

---

### 5. Conclusion

Ce module garantit un flux de prix **déterministe et ultra-rapide**. Il assure la disponibilité des données immuables pour le `RiskMonitor` et le `PortfolioManager`, tout en intégrant une résilience dynamique face à la latence ou aux pics de volume via une orchestration avec le `SystemManager`.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|tickData(tick_id,asset_id_ref,...)|IBKR Gateway|Live Data Hub|Réception du flux de marché brut en temps réel.|
|2|applyBackpressure()|Live Data Hub|Live Data Hub|Application de la politique "Drop Oldest" si la queue d'entrée sature.|
|3|checkLatency()|Live Data Hub|Live Data Hub|Mesure de l'écart temporel entre le tick et l'heure système.|
|4|notifyHighLatency()|Live Data Hub|System Manager|Alerte au superviseur en cas de franchissement de seuil de latence.|
|5|setOperatingMode(DEGRADED)|System Manager|Live Data Hub|Commande de basculement vers une agrégation simplifiée.|
|6|logEvent(details)|Live Data Hub|Log Service|Journalisation asynchrone et non-bloquante de l'incident.|
|7|createMarketQuote(AccumulatedTicks)|Live Data Hub|Live Data Hub|Agrégation des ticks en un objet immuable et versionné.|
|8|enqueue(MarketQuote)|Live Data Hub|FastLaneQueue|Dépôt non-bloquant du snapshot dans la queue SPSC.|
|9|dequeue()|Thread Manager|FastLaneQueue|Récupération de la quote par le thread du Pool I/O Real-Time.|
|10|writeToCache(MarketQuote)|Thread Manager|Data Cache|Mise à jour prioritaire par écrasement atomique (Instant T).|
|11|pushToBuffer(MarketQuote)|Thread Manager|Historic Live Hub|Indexation séquentielle dans le buffer circulaire de session.|
|12|notifyDataReady()|Thread Manager|EventBus|Signal de disponibilité déclenchant le "Pull" des consommateurs.|

---

### 6. Ports et Interfaces

**IMarketDataCacheWriter**
* **Implémenté par** : Data Cache
* **Injecté dans / Utilisé par** : Live Data Hub (via fragment 09a)
* **Responsabilité opérationnelle** : Mise à jour ultra-rapide des `MarketQuotes` agrégés en mémoire vive pour une disponibilité immédiate.
* **Règles d’accès ou d’usage** : Accès non-bloquant. Priorité `CRITICAL`. Utilisation d'une queue asynchrone pour garantir la faible latence. Usage exclusif de MarketQuotes immuables. Le port garantit l'accès aux seules versions validées (Atomic Versioning).

**ILiveDataControlPort**
* **Implémenté par** : `Live Data Hub`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Permettre le changement dynamique du mode de traitement des données de marché suite à une alerte de latence.
* **Règles d’accès ou d’usage** : Appel synchrone via le message `setOperatingMode(Mode)`. Définit si l'agrégation doit être `NOMINAL` ou `DEGRADED`.

**IMarketDataHealthPort**
* **Implémenté par** : `Live Data Hub (LDH)`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Validation de la preuve de vie du flux, vérification de la couverture et **contrôle de la fraîcheur (fraîcheur des ticks)**.
* **Règles d’accès ou d’usage** : Utilisé ici pour le message `notifyHighLatency()`. Toute anomalie de fraîcheur doit être remontée immédiatement.

**ILiveDataOrchestrator**
* **Implémenté par** : `Live Data Hub`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Point d'entrée pour le pilotage du cycle de vie des données de marché (Message 1 : `startMarketDataService`).
* **Règles d’accès ou d’usage** : Gère la transition vers le mode "In-Trade". Doit confirmer que les deux flux (Fast/Slow) sont opérationnels.

**ILogger**
* **Implémenté par** : `Logger Global`
* **Utilisé par** : Tous les managers (dont le `LiveDataHub`)
* **Responsabilité opérationnelle** : Journalisation globale du système (logs techniques, opérationnels et audit).
* **Règles d’accès ou d’usage** : Mode synchrone pour bootstrapping et erreurs fatales ; **mode non-bloquant en runtime** (essentiel pour la Fast-Lane).
 
**IThreadManagerPort**
  * **Implémenté par** : Thread Manager
  * **Utilisé par :** System Manager
  * **Responsabilités :** Allocation des pools, Démarrage des loops persistantes, Reporting de l’état d’initialisation
  * **Règles :** Invocation synchrone uniquement, BOOTSTRAP_ONLY, Aucun accès direct aux PoolWorkers

---

### NOTE 

**Kill Switch** : Interface `ISystemKillSwitchPort` définie, usage strictement contrôlé : aucun composant métier ne déclenche l’arrêt directement, toute action réelle passe par `IProcessControlPort`. À vérifier que l’orchestration respecte cette règle lors de la relecture finale.

---

