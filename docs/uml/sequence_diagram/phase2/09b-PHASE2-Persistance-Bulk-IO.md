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

* **`checkBufferStatus()`** : Auto-appel périodique qui vérifie l'état du buffer de `SnapshotHeader` en attente de persistance. Il compare le temps écoulé et la taille du bloc avec les seuils configurés pour déclencher l'insertion.

* **`submitTask(SnapshotHeaderBuffer)`** : Le `LDH` transfère le bloc de `SnapshotHeader` complets et structurés au `DIL`. Le `LDH` efface ensuite son buffer pour commencer une nouvelle accumulation.

* **`createPersistenceObjects()`** : Fonction de préparation. Le `DIL` reçoit les `SnapshotHeader` déjà cohérents et les formate dans la structure la plus efficace pour le pilote de base de données (ex : conversion en un grand tableau de lignes SQL). Il ne crée plus les clés primaires/étrangères.

* **`createJob(Pool: I/O Bulk, Data: PersistenceObject)`** : Le `DIL` encapsule le bloc de données finalisé et spécifie le type de ressource requis : `Pool I/O Bulk` (basse priorité). Le `JM` prend le relais, enregistre le Job et le met en file d'attente.

* **`delegateJob(Bulk I/O)`** : Lorsque c'est le tour du Job d'être exécuté, le `JM` demande au `TM` de lui fournir un thread libre et de basse priorité du `Pool I/O Bulk`.

* **`executeBulkInsert(DataBlock)`** : Le thread alloué lance la fonction d'insertion réelle via le `DIL`. Cet appel est asynchrone du point de vue de la boucle critique du système.

* **`bulkInsert(SnapshotHeader, MarketQuote)`** : C'est l'opération physique. Le `DIL` exécute la requête optimisée d'insertion en masse (y compris le `SnapshotHeader` parent et toutes les lignes `MarketQuote` enfants) en une seule transaction lourde. Le thread est bloqué sur cette I/O jusqu'à la confirmation de la base de données.

* **`Job Completed`** : Après la confirmation de la transaction, l'état du Job est mis à jour. Le `JM` est notifié, lui permettant de clôturer la tâche et d'enregistrer l'audit de fin d'exécution.
