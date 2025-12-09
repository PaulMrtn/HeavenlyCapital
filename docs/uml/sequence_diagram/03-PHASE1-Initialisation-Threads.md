## `03-PHASE1-Initialisation-Threads`

<p align="center">
  <img src="img/03-PHASE1-Initialisation-Threads.jpg" width="900">
</p>


### 1. Objectif

La finalité de ce module est d'allouer les **ressources d'exécution physiques** du système en créant les **Pools de Threads spécialisés** (`CRITICAL` et `STANDARD`). Il doit garantir que ces ressources sont disponibles, persistantes, correctement isolées, et que le Pool Critique opère avec la **priorité maximale** promise.

---

### 2. Contexte

Ce module s'inscrit après la lecture des configurations globales (**02-PHASE1-Instanciation-Configs-Globaux**) et avant la création des managers métier. Il est une étape **d'allocation de ressources coûteuses** et définit le fondement de la performance du système. Sans cette étape, aucun traitement asynchrone (ordres, *fills*, ingestion de données) ne peut être exécuté.

---

### 3. Logique Générale

Le processus est orchestré par le **`Thread Manager (TM)`**.

1.  Le `TM` récupère les tailles et les priorités des pools auprès du **`Configuration Store`** (mémoire).
2.  Il lance des boucles d'itération pour instancier les objets **`PoolWorker`** (les conteneurs de threads persistants).
3.  Immédiatement après l'instanciation, chaque `PoolWorker` démarre sa boucle d'exécution (se met en veille) pour être **prêt instantanément** à recevoir un travail.
4.  Le `TM` exécute ensuite un **test de validation actif (`HCheckPriorityTest`)** sur le Pool Critique pour confirmer l'isolation et la performance.
5.  Le succès du test et de l'initialisation est logué et notifié au `System Manager`.

---

### 4. Règles Critiques

* **Threads Persistants :** Les objets **`PoolWorker`** sont créés au démarrage et ne sont **jamais détruits** pendant la session de trading. Ils restent en attente, éliminant la latence de création de thread lors de l'exécution d'une tâche.
* **Priorité Assurée (QoS) :** Le **`HCheckPriorityTest`** est obligatoire sur le Pool Critique. Il garantit que le Système d'Exploitation honore la priorité maximale allouée, préservant ainsi la **faible latence** pour les ordres d'urgence. Un échec sur ce test doit être traité comme une alerte critique (bien qu'il ne nécessite pas l'arrêt total ici, car la connectivité est assurée, il compromet la sécurité opérationnelle).
* **Isolation :** Les threads sont créés avec des priorités distinctes, assurant que les tâches lentes (futur Pool Bulk) ne peuvent pas cannibaliser les ressources du Pool Critique.

---

### 5. Conclusion

Le module **`03-PHASE1-Initialisation-Threads`** garantit que la couche d'exécution du système est **entièrement pré-allouée, segmentée par priorité** et **validée en performance**. Il établit une base d'exécution fiable et à faible latence, essentielle avant l'instanciation des managers métier qui dépendront de ces ressources.
