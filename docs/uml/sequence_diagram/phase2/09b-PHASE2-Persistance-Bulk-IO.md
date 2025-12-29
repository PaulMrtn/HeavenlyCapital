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
| 2 | List<MarketQuote> | Data Cache | Data Ingestion Layer | Retour de la liste des cotations consolidées disponibles pour le cycle actuel. |
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

**PersistencePort**
* **Implémenté par** : Data Integrity Layer (DIL)
* **Injecté dans / Utilisé par** : Live Data Hub (via fragment 09b)
* **Responsabilité opérationnelle** : Persistance massive (Bulk I/O) des journaux de marché pour l'audit et l'historique.
* **Règles d’accès ou d’usage** : Passage obligatoire par le DIL. Utilisation du pool de threads `BULK` pour ne pas impacter la latence.


---

### MEMO 1 — Responsabilité de création du SnapshotHeader (ERREUR MAJEURE)

La documentation indique que le `SnapshotHeader` est créé dans le `LiveDataHub` par la Fast-Lane. Cette hypothèse est désormais **fausse et incohérente** avec l’architecture validée. La Fast-Lane ne doit jamais créer de snapshot global ni garantir une cohérence inter-assets. Le `SnapshotHeader` doit être **construit exclusivement en Slow-Lane**, à partir des `MarketQuote` reçues, sur la base d’un cycle logique (`snapshot_id`, timestamp). Toute mention laissant penser que la Fast-Lane produit des snapshots complets doit être supprimée ou déplacée.

---

### MEMO 2 — Accumulation interne côté LDH (ANTI-PATTERN)

Le texte décrit une accumulation de `SnapshotHeader` dans un buffer interne du `LiveDataHub`. Cela introduit une **responsabilité de persistance et de batching dans un composant critique**, ce qui viole le principe d’isolation stricte Fast-Lane / Slow-Lane. Le LDH ne doit jamais bufferiser des structures destinées à la persistance. Il doit uniquement **émettre des MarketQuote immuables** vers une queue asynchrone Slow-Lane. Toute logique de buffering, seuil, fenêtre temporelle ou regroupement doit être déplacée dans le Dispatcher / DIL.

---

### MEMO 3 — Point de départ logique de la Slow-Lane mal positionné

La doc présente le `SnapshotHeader` comme point d’entrée de la Slow-Lane. C’est conceptuellement incorrect. Le **point de départ réel de la Slow-Lane est le flux de MarketQuote** produit par la Fast-Lane. Le snapshot global est une **reconstruction a posteriori**, pas un artefact amont. La logique actuelle inverse la causalité et doit être corrigée pour refléter un modèle événementiel unidirectionnel.

---

### MEMO 4 — Garantie de cohérence attribuée au mauvais composant

La cohérence structurelle (`snapshot_id`, `asset_id_ref`) est présentée comme garantie par le LiveDataHub. En réalité, le LDH garantit uniquement la **cohérence locale d’une MarketQuote** (immutabilité, horodatage, version). La **cohérence globale du snapshot (complétude, cardinalité, statut)** ne peut être évaluée qu’en Slow-Lane. Cette responsabilité doit être explicitement déplacée dans le périmètre du DIL / persistance.

---

### MEMO 5 — Confusion entre auditabilité et exhaustivité

La documentation laisse entendre que les données persistées représentent une image complète et cohérente du marché. Or, avec une politique Drop Oldest et une dégradation contrôlée, la persistance peut être **partielle par design**. La doc doit être alignée sur le fait que l’audit porte sur **ce qui a été effectivement observé et produit**, pas sur une garantie d’exhaustivité. Le snapshot peut être valide tout en étant incomplet.

---

### MEMO 6 — Absence de statut de snapshot en persistance

Le modèle présenté ne prévoit aucun mécanisme explicite pour qualifier un snapshot persisté (complet, partiel, dégradé). Sans cela, l’audit post-trade est ambigu. La doc 09b doit introduire explicitement que la Slow-Lane est responsable de qualifier chaque snapshot via des métadonnées (statut, compte attendu vs reçu), même si l’implémentation est différée.

---

### MEMO 7 — Temporalité mal définie (fenêtrage implicite)

Le déclenchement du Bulk Insert est décrit comme dépendant d’une taille critique ou d’un intervalle de temps, sans préciser à quel niveau temporel cela s’applique (tick, snapshot, cycle). Cette ambiguïté est problématique. La Slow-Lane doit être clairement définie comme **fenêtrée sur des cycles de snapshot**, pas sur des événements arbitraires. La doc doit refléter cette temporalité logique.

---

### MEMO 8 — Couplage conceptuel excessif LDH ↔ DIL

Le texte décrit un LDH qui soumet directement des blocs structurés au DIL, ce qui implique une connaissance forte du format de persistance. Cela va à l’encontre du découplage souhaité. Le LDH ne doit connaître ni le format final, ni la structure transactionnelle. Il doit publier des événements (MarketQuote) ; la Slow-Lane décide comment les transformer en objets persistables.

---

### MEMO 9 — 09b encore trop proche d’une “seconde Fast-Lane”

La logique décrite donne l’impression d’une seconde pipeline orchestrée par le LDH, alors que 09b devrait être un **consommateur asynchrone autonome**, tolérant au retard, à la perte et à la reconstitution différée. La doc doit être réalignée pour montrer que 09b vit à son propre rythme et ne fait aucune hypothèse temps réel.
