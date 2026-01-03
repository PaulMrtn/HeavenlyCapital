## `09b-PHASE2-Persistance-Bulk-IO`


<p align="center">
  <img src="../img/09b-PHASE2-Persistance-Bulk-IO.jpg" width="900">
</p>

---

### 1. Objectif

Garantir l'auditabilité et la traçabilité complète de l'activité de marché en enregistrant les données reconstruites (DTO `SnapshotHeader` et `MarketQuote`) en base de données. L'opération est conçue pour isoler les traitements lourds en I/O afin de ne jamais impacter la latence de la boucle d'exécution critique (Fast-Lane) grâce à une architecture **Trigger-then-Pull**.

---

### 2. Contexte

Ce module gère l'écriture en masse (*Bulk Insert*) des données historiques en **Slow-Lane**, de manière totalement asynchrone. Le point d'entrée n'est plus un timer, mais un signal provenant de l'**`EventBus`**. Les données sont extraites du **`Historic Live Hub (LHB)`**, qui sert de zone tampon structurée avec accès .
L'architecture distingue deux flux après la qualification par le `Data Ingestion Layer` (DIL) :
  * **Flux d'Audit :** Persistance exhaustive via le `Job Manager`.
  * **Flux d'Observabilité :** Diffusion passive de signaux d'état (Nominal/Degraded) vers le `MetricManager` via l'interface `IMarketDataObserverPort`.
  
---

### 3. Logique Générale

1. **Notification (Trigger) :** L'**EventBus** notifie le `Data Ingestion Layer` (DIL) dès qu'un nouveau slot de minute est stabilisé dans le buffer.
2. **Extraction (Pull) :** Le DIL effectue une lecture synchrone sur le buffer "gelé" du **LHB** (mécanisme de Double Buffering) pour garantir une isolation totale sans verrous.
3. **Construction du DTO :** Le DIL exécute la fonction `validateAndBuildSnapshot()`. Il instancie le DTO `SnapshotHeader` et y injecte les `MarketQuote` extraites.
4. **Qualification :** Si le LHB ou le DIL détecte des données incomplètes, l'objet est créé via `createPersistenceObject(DegradedSnapshot)`. Sinon, il est marqué `NOMINAL` via `FullSnapshot`.
5. **Délégation de Job :** Le DIL soumet l'objet au **`Job Manager`** (JM) et se libère immédiatement.
6. **Exécution Bulk I/O :** Le `JM` délègue la tâche au **`Thread Manager`** qui alloue un thread du **`Pool I/O Bulk`** (basse priorité) pour l'insertion physique en base de données.
7. **Clôture :** Une fois l'écriture confirmée par la **Database**, le `Job Manager` est notifié pour clôturer le job et libérer la mémoire du DTO.

---

### 4. Règles Critiques


* **Zéro Verrou (Lock-Free) :** L'isolation entre la Fast-Lane et la Slow-Lane est garantie par le mécanisme de **Double Buffering** du LHB : le DIL effectue son Pull dans le buffer "gelé" pendant que la Fast-Lane écrit dans le buffer actif, éliminant toute contention mémoire.
* **Isolation et Priorité Basse :** Les tâches de persistance utilisent exclusivement le **`Pool I/O Bulk`**. Ce pool est configuré avec la priorité la plus basse pour ne jamais entrer en compétition avec les ressources CPU/IO requises par l'exécution d'ordres ou le calcul de risque.
* **Fidélité de l'Audit :** Le système privilégie l'enregistrement de l'état réel "vu" par le système au moment du trading. Un snapshot incomplet est persisté avec son statut de dégradation (`DEGRADED` ou `PARTIAL`) pour assurer une transparence totale lors de l'analyse historique post-trade.
* **Réactivité pilotée par l'EventBus :** Le cycle de persistance n'est plus déclenché par un timer approximatif, mais par l'arrivée effective des agrégats notifiée par l'**EventBus**, optimisant ainsi l'utilisation des ressources système.
* **Gestion de la Pression (Backpressure) :** En cas de ralentissement de la base de données, les jobs s'accumulent de manière asynchrone dans le `Job Manager`. Le LHB agit comme un tampon circulaire (jusqu'à 1000 slots) permettant au DIL de rattraper son retard sans perte de données.
* **Séparation des Rôles et Observabilité :** Le DIL ne produit que des signaux bruts ; le calcul et la qualification des métriques sont délégués au `MetricManager` via un modèle *Event-driven* en **Best-effort**, garantissant qu'aucune latence d'observabilité ne ralentisse la capture des données.
* **Sécurité par Immuabilité :** L'intégrité des données est assurée par le caractère strictement immuable des objets `MarketQuote` et `SnapshotHeader` (DTO) circulant entre le LHB, le DIL et la Database.

---

### 5. Conclusion

Ce module assure l'auditabilité et la traçabilité du système par la reconstruction asynchrone des données via un modèle **Trigger-then-Pull**. En s'appuyant sur les notifications de l'**EventBus** et l'isolation physique offerte par le **Double Buffering** du **Historic Live Hub (LHB)**, il permet au **Data Ingestion Layer (DIL)** d'extraire des instantanés de marché sans aucune contention avec la Fast-Lane. L'utilisation du **Pool I/O Bulk** pour la persistance des DTO `SnapshotHeader` garantit que l'archivage des états, qu'ils soient nominaux ou dégradés, s'effectue avec une priorité basse sans jamais introduire de gigue dans la boucle de trading critique. Cette architecture consolide ainsi une base de données historique fidèle et hautement disponible pour l'analyse Post-Trade, tout en préservant l'intégrité de la performance en temps réel.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:--|:---|:---|:---|:---|
|1|notifyDataReady(index)|EventBus|Data Ingestion Layer|Signal asynchrone notifiant qu'un nouveau slot de données est stabilisé dans le buffer.|
|2|fetchSessionData(index)|Data Ingestion Layer|Historic Live Hub|Requête synchrone pour extraire l'agrégat de prix via l'interface ISlowLaneProvider.|
|3|MarketQuote+Metadata|Historic Live Hub|Data Ingestion Layer|Retour des données brutes et du statut d'intégrité depuis le buffer gelé (Double Buffering).|
|4|validateAndBuildSnapshot()|Data Ingestion Layer|Data Ingestion Layer|Analyse interne de la complétude des données pour qualifier le futur SnapshotHeader.|
|5|createPersistenceObject(FullSnapshot)|Data Ingestion Layer|Data Ingestion Layer|Instanciation du DTO avec le marquage NOMINAL (si les données sont complètes).|
|6|createPersistenceObject(DegradedSnapshot)|Data Ingestion Layer|Data Ingestion Layer|Instanciation du DTO avec le marquage DEGRADED (si les données sont partielles).|
|7|createJob(Pool:I/OBulk,Data:PersistenceObject)|Data Ingestion Layer|Job Manager|Soumission de la tâche de persistance ; libère immédiatement le DIL.|
|8|delegateJob(Bulk I/O)|Job Manager|Thread Manager|Ordonnancement de la tâche vers le pool de threads dédié aux écritures disque.|
|9|activatePoolThread()|Thread Manager|Thread Manager|Mécanisme interne d'allocation d'un thread de basse priorité du pool Bulk.|
|10|bulkInsert(SnapshotHeader)|Thread Manager|Database|Écriture physique du DTO et des métadonnées d'audit dans le stockage persistant.|
|11|notifyCompletion()|Database|Job Manager|Confirmation de transaction notifiée au gestionnaire pour clôture du cycle de vie du Job.|

---

### 6. Ports et Interfaces

**IMarketDataCacheReader**
* **Implémenté par** : `DataCache`
* **Injecté dans / Utilisé par** : `Data Ingestion Layer (DIL)` (dans le cadre de la séquence 09b)
* **Responsabilité opérationnelle** : Fournir un accès en lecture seule, non bloquant, aux derniers `MarketQuote` immuables versionnés pour permettre la reconstruction du snapshot.
* **Règles d’accès ou d’usage** : Lecture lock-free (sans verrou). Aucun accès aux structures internes du cache. Usage exclusif d'objets immuables. Ne doit jamais bloquer la Fast-Lane.

**IMarketDataObserverPort**
* **Implémenté par** : `MetricManager`
* **Injecté dans / Utilisé par** : `Data Ingestion Layer (DIL)`
* **Responsabilité opérationnelle** : Point d'entrée pour la consommation passive (push) des signaux bruts de performance et d'état des snapshots.
* **Règles d’accès ou d’usage** : Mode **Best-effort** uniquement. Aucun impact autorisé sur le temps de cycle du DIL. Accès strictement observatoire (pas de boucle de rétroaction sur le trading).

**PersistencePort**
* **Implémenté par** : `Data Integrity Layer (DIL)` / `AtomicDBWriteProcess`
* **Injecté dans / Utilisé par** : `Data Ingestion Layer (DIL)` (via fragment 09b)
* **Responsabilité opérationnelle** : Persistance massive (Bulk I/O) des snapshots de marché (`SnapshotHeader` et `MarketQuote`) pour l'audit et l'historique post-trade.
* **Règles d’accès ou d’usage** : Utilisation obligatoire du pool de threads `BULK`. Transactions atomiques requises. Isolation totale des objets métiers par rapport à la base de données.

**IThreadManagerPort**
* **Implémenté par** : `Thread Manager`
* **Injecté dans / Utilisé par** : `System Manager`, `Job Manager` (pour délégation du pool)
* **Responsabilité opérationnelle** : Allocation des pools de threads et gestion des boucles persistantes.
* **Règles d’accès ou d’usage** : Dans cette séquence, il est sollicité pour déléguer la tâche au pool `I/O Bulk`. Aucun accès direct aux `PoolWorkers` par les composants métiers.

**ILogger**
* **Implémenté par** : `Logger Global`
* **Injecté dans / Utilisé par** : `Data Ingestion Layer`, `Job Manager`
* **Responsabilité opérationnelle** : Journalisation des événements de persistance et des erreurs de snapshot.
* **Règles d’accès ou d’usage** : **Mode non-bloquant impératif** durant le runtime (Phase II) pour ne pas introduire de gigue (jitter).

**IJobSubmissionPort**
* **Implémenté par** : `Job Manager`
* **Injecté dans / Utilisé par** : `Data Ingestion Layer (DIL)`
* **Responsabilité opérationnelle** : Permettre au DIL de soumettre un `PersistenceObject` (Snapshot) dans la file d'attente asynchrone de la Slow-Lane.
* **Règles d’accès ou d’usage** : Appel asynchrone (Fire-and-forget du point de vue du DIL). Doit supporter l'encapsulation de métadonnées de priorité (Pool: I/O Bulk).


### NOTE

* La liste des « actifs attendus » est injectée via la configuration système lors du bootstrap et constitue la source de vérité pour la reconstruction des snapshots.

