## `09b-PHASE2-Persistance-Bulk-IO`


<p align="center">
  <img src="../img/09b-PHASE2-Persistance-Bulk-IO.jpg" width="900">
</p>

---

### 1. Objectif

Garantir l'auditabilité et la traçabilité complète de l'activité de marché en enregistrant les données reconstruites (`MarketQuote` et `SnapshotHeader`) en base de données. L'opération est conçue pour isoler les traitements lourds en I/O afin de ne jamais impacter la latence de la boucle d'exécution critique (Fast-Lane).

---

### 2. Contexte

Ce module gère l'écriture en masse (*Bulk Insert*) des données historiques. Il opère en **Slow-Lane**, de manière totalement asynchrone par rapport à la réception des flux. Le point d'entrée est  le **`Data Cache`**, où sont récupérées les cotations consolidées pour assembler une image cohérente du marché (le `SnapshotHeader`) destinée à l'historique.

---

### 3. Logique Générale

1. **Extraction du Cache :** Le `Data Ingestion Layer` (DIL) interroge périodiquement le `Data Cache` pour récupérer les dernières `MarketQuote` immuables déposées par la Fast-Lane.
2. **Reconstruction du Snapshot :** Le DIL exécute la fonction `validateAndBuildSnapshot()`. Il génère un `snapshot_id` unique et vérifie la présence de tous les actifs attendus.
3. **Qualification (Auditabilité) :** Si des données manquent ou sont obsolètes, le snapshot est marqué comme `DEGRADED` ou `PARTIAL`. S'il est complet, il est marqué `NOMINAL`. Cette qualification garantit la fidélité de l'audit post-trade.
4. **Encapsulation et Job :** Les données sont préparées en tant qu'objet `PersistenceObject`. Ce "Job" est transmis au `Job Manager` (JM).
5. **Exécution Asynchrone :** Le `JM` alloue la tâche au **`Pool I/O Bulk`** (basse priorité) via le `Thread Manager`. Un thread dédié exécute l'insertion massive en base de données sans bloquer les autres processus.
---

### 4. Règles Critiques

* **Isolation Totale :** La Slow-Lane est strictement séparée de la Fast-Lane. Elle consomme les données du cache sans que le `LiveDataHub` n'ait connaissance du processus de persistance.
* **Priorité Basse :** Les tâches utilisent exclusivement le **`Pool I/O Bulk`**. Ce pool est configuré avec la priorité la plus basse pour ne pas entrer en compétition avec les ressources CPU/IO requises par l'exécution d'ordres ou le calcul de risque.
* **Auditabilité vs Exhaustivité :** Le système privilégie l'enregistrement de l'état réel "vu" par le système. Un snapshot incomplet est persisté avec son statut de dégradation pour assurer une transparence totale lors de l'analyse historique.
* **Déclenchement Temporel :** Le cycle de persistance est déclenché par un timer ou un seuil de volume. Ces paramètres seront calibrés lors des phases de stress-test pour optimiser la charge système.

---

### 5. Conclusion

Ce module est le garant de l'audit et de l'historique par la reconstruction asynchrone des données. En utilisant l'isolation des ressources du `Pool I/O Bulk` et la qualification des blocs cohérents (`SnapshotHeader`), il permet de capturer une image fidèle et horodatée du marché pour l'analyse Post-Trade. Cette architecture garantit la transparence de l'audit, incluant les états dégradés, sans jamais impacter la performance en temps réel de la boucle de trading.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | fetchLatestQuotesFromCache() | Data Ingestion Layer | Data Cache | Requête synchrone pour extraire les dernières MarketQuotes immuables stockées en mémoire. |
| 2 | List< MarketQuote > | Data Cache | Data Ingestion Layer | Retour de la liste des cotations consolidées disponibles pour le cycle actuel. |
| 3 | validateAndBuildSnapshot() | Data Ingestion Layer | Data Ingestion Layer | Auto-appel pour reconstruire le SnapshotHeader global et vérifier l'intégrité des données (Nominal vs Dégradé). |
| 4 | createPersistenceObjects(FullSnapshot) | Data Ingestion Layer | Data Ingestion Layer | Branche 'if Valid' : Préparation des objets de données complets pour l'insertion en base. |
| 5 | createPersistenceObjects(DegradedSnapshot) | Data Ingestion Layer | Data Ingestion Layer | Branche 'else' : Préparation des objets avec marquage spécifique pour les snapshots partiels ou corrompus. |
| 6 | createJob(Pool: I/O Bulk, Data: PersistenceObject) | Data Ingestion Layer | Job Manager | Création et soumission d'une tâche de persistance asynchrone avec priorité basse. |
| 7 | delegateJob(Bulk I/O) | Job Manager | Thread Manager | Allocation de la tâche au pool de threads dédié aux opérations d'entrées/sorties massives. |
| 8 | executeBulkInsert(DataBlock) | Thread Manager | Data Ingestion Layer | Signal d'exécution permettant au thread alloué de piloter l'écriture des données. |
| 9 | bulkInsert(SnapshotHeader, MarketQuote) | Data Ingestion Layer | Database | Exécution physique de l'insertion massive (Bulk) dans les tables historiques de la base de données. |
| 10 | notifyCompletion() | Database | Job Manager | Signalement de la fin de l'opération d'écriture pour clôture du Job et libération des ressources. |

---

### 6. Ports et Interfaces

**IMarketDataCacheReader**
* **Implémenté par** : `DataCache`
* **Injecté dans / Utilisé par** : `Data Ingestion Layer (DIL)` (dans le cadre de la séquence 09b)
* **Responsabilité opérationnelle** : Fournir un accès en lecture seule, non bloquant, aux derniers `MarketQuote` immuables versionnés pour permettre la reconstruction du snapshot.
* **Règles d’accès ou d’usage** : Lecture lock-free (sans verrou). Aucun accès aux structures internes du cache. Usage exclusif d'objets immuables. Ne doit jamais bloquer la Fast-Lane.

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

