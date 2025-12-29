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
