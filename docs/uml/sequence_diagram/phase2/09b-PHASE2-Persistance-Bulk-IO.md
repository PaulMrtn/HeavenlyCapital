## `09b-PHASE2-Persistance-Bulk-IO`


<p align="center">
  <img src="../img/09b-PHASE2-Persistance-Bulk-IO.jpg" width="900">
</p>

---

### 1. Objectif

Garantir l'auditabilité et la traçabilité complète de l'activité de marché en enregistrant massivement les données agrégées (`MarketQuote` et `SnapshotHeader`) en base de données, sans jamais impacter la latence de la boucle d'exécution critique (Fast-Lane).

---

### 2. Contexte

Ce module existe pour **isoler l'opération la plus lourde en I/O** du système : l'écriture en masse (*Bulk Insert*) des données historiques dans la base de données. Il s'inscrit en parallèle de la boucle de trading et utilise des ressources de **basse priorité** pour opérer en tâche de fond. Le point de départ est le **`SnapshotHeader` complet** (créé dans le `LiveDataHub` par la Fast-Lane), qui sert d'objet cohérent pour l'historique.

---

### 3. Logique Générale

1.  **Accumulation des Enveloppes :** Le `LiveDataHub` reçoit le flux de Ticks et crée les `SnapshotHeader` complets (contenant les `MarketQuote`). En plus de les envoyer à la `FastLaneQueue`, il les accumule dans un **buffer interne** destiné uniquement à la persistance.
2.  **Déclenchement du Job :** Lorsque ce buffer atteint une taille critique (volume suffisant) et/ou qu'une période de temps définie s'est écoulée, le **LDH soumet le bloc de `SnapshotHeader`** au `Data Ingestion Layer` (`DIL`).
3.  **Encapsulation Job :** Le `DIL` reçoit les blocs de données déjà structurés (cohérence du `SnapshotHeader` garantie par le LDH) et les prépare en tant qu'objet `PersistenceObject` pour l'insertion. Ce Job est transmis au `Job Manager` (`JM`).
4.  **Exécution Asynchrone :** Le `JM` l'alloue au **`Pool I/O Bulk`** (Pool de basse priorité) via le `Thread Manager`. Un thread de ce pool exécute alors l'insertion massive et asynchrone des données dans la base de données.

---

### 4. Règles Critiques

* **Isolation Critique :** L'exécution de l'insertion (`bulkInsert`) est **asynchrone** par rapport au `LiveDataHub`. Le thread du LDH ne doit jamais attendre la fin de l'écriture en base.
* **Priorité Basse :** La tâche utilise exclusivement le **`Pool I/O Bulk`**. Ce pool a la plus basse priorité afin que ses threads soient suspendus ou ralentis si une tâche critique (Fast-Lane ou exécution d'ordre) nécessite des ressources I/O urgentes.
* **Condition de Déclenchement :** Le module ne s'active que de manière **périodique** ou **conditionnelle** (par taille de buffer atteinte) afin de maximiser l'efficacité du *Bulk Insert* et de minimiser la surcharge du système.
* **Cohérence Structurelle :** La cohérence des clés (`snapshot_id`, `asset_id_ref`) est garantie par le `LiveDataHub` en amont. Le rôle du `DIL` est de **préparer les blocs pour la transaction finale**.

---

### 5. Conclusion

Le module `09b-PHASE2-Persistance-Bulk-IO` est le garant de l'audit et de l'historique. En utilisant l'isolation des ressources du `Pool I/O Bulk` et la soumission par blocs cohérents (`SnapshotHeader`), il permet de capturer une image complète et cohérente du marché pour l'analyse Post-Trade, sans impacter la performance en temps réel de la boucle de trading.

---

### 6. Description des Fonctions

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | accumulate(SnapshotHeader) | LiveDataHub (LDH) | LiveDataHub (LDH) | Accumulation interne des snapshots dans un buffer pour atteindre le seuil de Bulk. |
| 2 | submitBulk(SnapshotHeader[]) | LiveDataHub (LDH) | DataIngestionLayer (DIL) | Envoi du bloc de données structurées pour préparation à la persistance. |
| 3 | createPersistenceJob(Data) | DataIngestionLayer (DIL) | JobManager (JM) | Encapsulation des données de marché dans une unité de travail (Job) traçable. |
| 4 | allocate(BulkJob) | JobManager (JM) | ThreadManager (TM) | Demande d'allocation de ressources spécifiques pour une tâche de fond. |
| 5 | runAsync(BulkPool) | ThreadManager (TM) | ThreadManager (TM) | Assignation du Job au pool de threads à basse priorité (BULK). |
| 6 | bulkInsert(PersistenceObject) | ThreadManager (TM) | Database (DB) | Exécution physique de l'écriture massive en base de données. |
| 7 | notifyCompletion() | ThreadManager (TM) | JobManager (JM) | Signalement de la fin de l'opération pour nettoyage du Job. |

---

### 6. Ports et Interfaces

**PersistencePort**
* **Implémenté par** : Data Integrity Layer (DIL)
* **Injecté dans / Utilisé par** : Live Data Hub (via fragment 09b)
* **Responsabilité opérationnelle** : Persistance massive (Bulk I/O) des journaux de marché pour l'audit et l'historique.
* **Règles d’accès ou d’usage** : Passage obligatoire par le DIL. Utilisation du pool de threads `BULK` pour ne pas impacter la latence.



---

Voici des **notes / memos / TODO**, **paragraphe par idée**, centrées uniquement sur la documentation **09b actuelle**, en tenant compte de **tout ce qui a été décidé dans 09 et 09a**.
Aucune reformulation de la doc ici, uniquement ce qui **ne va pas** et **doit être modifié**.

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

