## `03-PHASE1-Initialisation-Threads`

<p align="center">
  <img src="../img/03-PHASE1-Initialisation-Threads.jpg" width="900">
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

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | initializePools() | System Manager | Thread Manager | Commande synchrone d'allocation des ressources de calcul. |
| 2 | getConfig(PoolSizes, Priorities) | Thread Manager | Config | Récupération des paramètres d'allocation (Nombres de threads et niveaux de priorité OS). |
| 3 | new PoolWorker(CRITICAL_PRIORITY) | Thread Manager | PoolWorker | Instanciation de threads persistants pour les tâches ultra-prioritaires (ordres, urgences). |
| 4 | startExecutionLoop() | Thread Manager | Thread Manager | Mise en veille active des threads pour éliminer la latence de création à l'usage. |
| 5 | new PoolWorker(STANDARD_PRIORITY) | Thread Manager | PoolWorker | Instanciation de threads pour les traitements métier standards (calculs tactiques). |
| 6 | startExecutionLoop() | Thread Manager | Thread Manager | Activation de la boucle d'attente du Pool Standard. |
| 7 | HCheckPriorityTest(CRITICAL_POOL) | Thread Manager | Thread Manager | Test de validation actif mesurant si l'OS honore la priorité maximale. |
| 8 | logInfo(PriorityTestStatus) | Thread Manager | Logger | Enregistrement du résultat du test pour l'audit opérationnel. |
| 9 | Initialization_Complete(Status) | Thread Manager | System Manager | Retour de l'état final (SUCCESS ou CRITICAL_FAILURE). |
| 10 | call_04-PHASE1... | System Manager | System Manager | Passage à l'étape suivante si le statut permet la poursuite. |


--- 

### 6. Ports et Interfaces


## 1. ThreadManagerPort
- **Implémenté par :** Thread Manager
- **Injecté dans / Utilisé par :** System Manager
- **Responsabilité opérationnelle :** Allocation et gestion des pools de threads, démarrage des loops persistantes, reporting de l’état initialisation
- **Règles d’accès ou d’usage :**
  - Invocation synchrone depuis System Manager uniquement.
  - Retour obligatoire de `Initialization_Complete` avant passage à la séquence suivante.
  - Interdiction d’accéder directement aux PoolWorkers depuis d’autres modules.

## 2. PoolWorkerInterface
- **Implémenté par :** PoolWorker
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Exécution persistante des jobs selon priorité (CRITICAL, STANDARD, BULK, AUDIT)
- **Règles d’accès ou d’usage :**
  - Priorité définie à l’instanciation et non modifiable.
  - Ne jamais détruire le PoolWorker pendant la session.
  - Isolation stricte : aucun partage inter-pools des jobs critiques.

## 3. ConfigurationStorePort
- **Implémenté par :** Configuration Store
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Fournir tailles et priorités des pools
- **Règles d’accès ou d’usage :**
  - Lecture seule pendant l’initialisation.
  - Interdiction de modification en runtime.
  - Doit être disponible avant la création des PoolWorkers.

## 4. LoggerPort
- **Implémenté par :** Logger
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Journalisation des étapes d’initialisation, tests de priorité et reporting des erreurs critiques
- **Règles d’accès ou d’usage :**
  - Log synchronisé pour toutes les étapes critiques.
  - Toute alerte critique doit être loguée avant propagation à System Manager.
  - Aucun bypass possible pour écriture directe par les PoolWorkers.

## 5. HCheckPriorityInterface
- **Implémenté par :** Thread Manager
- **Injecté dans / Utilisé par :** PoolWorker CRITICAL_POOL
- **Responsabilité opérationnelle :** Vérifier que la priorité maximale OS est respectée
- **Règles d’accès ou d’usage :**
  - Test obligatoire avant retour SUCCESS au System Manager.
  - Échec → signal CRITICAL_FAILURE et déclenchement de `systemStop`.
  - Ne pas utiliser pour pools non critiques.

## 6. SystemManagerPort
- **Implémenté par :** System Manager
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Recevoir le statut final d’initialisation (`SUCCESS` / `CRITICAL_FAILURE`) et orchestrer la séquence suivante
- **Règles d’accès ou d’usage :**
  - Ne pas exécuter d’opérations métier tant que l’initialisation des pools n’est pas confirmée.
  - Cycle de vie synchronisé avec ThreadManagerPort.

---

### NOTE

**Liste Exhaustive des Pools :** Pour garantir l'isolation des ressources tout au long du cycle de vie du système, les types de pools suivants doivent être initialisés :
  * **CRITICAL_POOL** (Priorité : **Maximale / Real-Time**) : Dédié aux ordres d'urgence, aux liquidations RM et à la transmission OM.
  * **STANDARD_POOL** (Priorité : **Haute**) : Dédié à la stratégie standard PM, au traitement des flux LDH et à la logique métier courante.
  * **BULK_POOL** (Priorité : **Basse / Background**) : Dédié aux écritures I/O non critiques, à l'archivage des logs et à la persistance lente via le DIL.
  * **AUDIT_POOL** (Priorité : **Normale**) : Dédié aux réconciliations de fin de journée et à la génération des SessionBooks.


**Politique Zero-Tolerance** : Le message 9 (Initialization_Complete) ne tolère aucune ambiguïté. Si le HCheckPriorityTest échoue (priorité non honorée par l'OS) ou si un seul PoolWorker ne peut être instancié, le Thread Manager doit retourner un état FAILED. Le System Manager doit alors exécuter un systemStop immédiat. Le trading ne peut être engagé sans la certitude d'une isolation parfaite des threads.
