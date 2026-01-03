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

Le système repose sur un découplage strict entre la réception des flux et leur distribution en mémoire via une **Queue Non Bloquante** (`FastLaneQueue`) de type **SPSC** (Single Producer / Single Consumer). Cette structure garantit une latence minimale, l’absence de contention et un comportement strictement déterministe.

#### 3.1 Le Producteur : Live Data Hub (LDH)

* **Réception et Contrôle** : Le LDH reçoit les `TickData` bruts, applique une politique de **Backpressure (Drop Oldest)** en cas de saturation de la queue d'entrée, et vérifie systématiquement la latence du flux.
* **Agrégation** : Si le flux est sain, il agrège les ticks en un objet **`MarketQuote`** immuable. En cas de latence critique, il alerte le `SystemManager` pour basculer en **Mode Dégradé**.
* **Transmission** : Le `MarketQuote` consolidé est déposé de manière asynchrone et non bloquante dans la `FastLaneQueue`.

#### 3.2 Le Consommateur : Thread Manager (Pool I/O Real-Time)

Un thread unique dédié, en boucle d'écoute persistante sur la `FastLaneQueue`, assure le traitement séquentiel pour garantir l'intégrité totale sans overhead de verrouillage :

* **Extraction** : Le thread retire le `MarketQuote` dès sa disponibilité dans la queue.
* **Double Écriture Séquentielle** :
1. **Data Cache** : Il met d'abord à jour le cache en mémoire vive pour le prix instantané (Instant T).
2. **Historic Live Buffer (LHB)** : Il indexe immédiatement après la donnée dans le buffer historique de la session.


* **Cohérence temporelle** : Cette distribution synchrone par un thread unique garantit que les lecteurs (RM/PM) voient toujours un état cohérent entre le dernier prix et la trajectoire de session.

#### 3.3 Signal de Disponibilité : EventBus

* **Notification** : Une fois la double écriture validée (Cache + LHB), le thread de consommation émet le signal `notifyDataReady` via l'**EventBus**.
* **Déclenchement** : Ce message réveille les boucles de calcul du **Risk Monitor** et du **Portfolio Manager**, leur indiquant que les données sont prêtes à être lues (modèle *Signal-then-Pull*) via leurs interfaces respectives (`IMarketDataCacheReader` et `ILiveDataReader`).

---

### 4. Règles Critiques

#### 4.1. Séquençage et Déterminisme

* **Séquençage Déterministe en RAM** : Pour garantir une intégrité totale sans overhead de verrouillage, les écritures sont effectuées de manière strictement séquentielle par un thread consommateur unique. L'ordre d'exécution est immuable : mise à jour du **Data Cache** (Instant T), puis indexation dans le **Historic Live Buffer** (LHB), et enfin notification via l'**EventBus**.
* **Priorité au Cache** : L'écriture dans le Data Cache est systématiquement déclenchée en premier afin de minimiser la latence du "Last Price". L'indexation dans le LHB suit immédiatement pour assurer la continuité de la série temporelle sans rupture de flux.
* **Atomicité Logique de la Fast-Lane** : Le transfert vers le Cache et le LHB est considéré comme une opération indivisible. Un snapshot ne peut être considéré comme "disponible" que s'il est présent simultanément dans les deux structures, évitant ainsi toute divergence entre les calculs de risque (prix flash) et les calculs de volatilité (historique).

#### 4.2. Performance et Non-Blocage

* **Non-Blocage Absolu** : Le thread producteur (`LiveDataHub`) ne doit jamais être ralenti par les consommateurs ou les services annexes. L'enregistrement des incidents (`logEvent`) et la notification de disponibilité (`notifyDataReady`) sont strictement asynchrones.
* **Performance du LHB (Lock-Free)** : L'ingestion dans le Historic Live Buffer doit impérativement respecter le mécanisme de **Double Buffering**. Cette approche garantit que l'ajout de données historiques ne crée aucune contention ni gigue (jitter) sur la boucle de consommation critique.
* **Isolation des Tâches** : Le cycle de vie d'une donnée est physiquement isolé : le calcul de l'agrégation (`MarketQuote`) est dévolu au Producteur, tandis que les opérations d'I/O mémoire (Cache/LHB) sont la responsabilité exclusive du Consommateur.

#### 4.3. Intégrité et Gestion de la Charge

* **Sécurité & Backpressure (Drop Oldest)** : La santé du flux est vérifiée par `checkLatency()` avant toute agrégation. En cas de saturation de la queue d'entrée, la politique **Drop Oldest** est appliquée pour privilégier systématiquement la fraîcheur des données de marché sur l'exhaustivité.
* **Dégradation Contrôlée** : En cas de stress extrême, le système maintient la diffusion des snapshots en dégradant la richesse de l'agrégation (ex: priorité au `last_price` sur le `bid/ask`) plutôt que de risquer un blocage ou une interruption du flux.
* **Immuabilité des Données** : Seuls des objets `MarketQuote` immuables transitent par la queue. Chaque objet est versionné et validé dès sa création, garantissant une isolation totale des consommateurs contre les données corrompues.

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

