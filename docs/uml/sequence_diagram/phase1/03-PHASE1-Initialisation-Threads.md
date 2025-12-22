## `03-PHASE1-Initialisation-Threads`

<p align="center">
  <img src="../img/03-PHASE1-Initialisation-Threads.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'allouer les ressources d'exécution physiques du système en créant quatre **Pools de Threads spécialisés** (`CRITICAL`, `STANDARD`, `BULK`, `AUDIT`). Il garantit que ces ressources sont entièrement pré-allouées, isolées, et que le Pool Critique opère avec une priorité garantie par l'OS avant tout engagement de trading.

### 2. Contexte

Ce module intervient après la lecture des configurations globales. C'est une étape d'**allocation de ressources lourdes**. Le système ne peut passer à la phase 04 (Instanciation des Managers Locaux) sans une validation explicite de la couche d'exécution, car la sécurité opérationnelle et la faible latence du système en dépendent.

### 3. Logique Générale & Architecture des Pools

Le processus est orchestré par le **`Thread Manager (TM)`** selon une hiérarchie stricte d'isolation :

1. **Récupération des Configs :** Le `TM` extrait les tailles et priorités depuis le `Configuration Store`.
2. **Pré-allocation Systématique :** Le `TM` instancie les `PoolWorker` pour les quatre segments :
* **CRITICAL_POOL (Priorité Maximale / Real-Time) :** Ordres d'urgence, liquidations Risk Management (RM) et transmission Order Manager (OM).
* **STANDARD_POOL (Priorité Haute) :** Stratégies Portfolio Manager (PM), flux LDH et logique métier standard.
* **BULK_POOL (Priorité Basse / Background) :** Écritures I/O non critiques, archivage des logs, persistance lente (DIL).
* **AUDIT_POOL (Priorité Normale) :** Réconciliations post-trade et génération des SessionBooks.


3. **Boucle Persistante :** Chaque thread démarre une boucle d'attente (`startExecutionLoop`) immédiatement. Ils ne sont **jamais détruits** pendant la session pour éliminer la latence de création.
4. **Validation OS (HCheckPriorityTest) :** Un test actif vérifie que le scheduler de l'OS honore réellement la priorité du `CRITICAL_POOL`.

### 4. Règles Critiques & Zero-Tolerance

* **Politique Zero-Tolerance :** Si un seul `PoolWorker` échoue à l'instanciation ou si le `HCheckPriorityTest` renvoie un échec (priorité non honorée), le `Thread Manager` doit retourner un état `CRITICAL_FAILURE`.
* **Arrêt Immédiat :** En cas de `CRITICAL_FAILURE`, le `System Manager` doit exécuter un `systemStop()` immédiat. Le trading ne peut être engagé sans la certitude d'une isolation parfaite.
* **Isolation Stricte :** Aucun pool ne doit interférer avec un autre. Les tâches lourdes du `BULK_POOL` ne peuvent en aucun cas cannibaliser les ressources du `CRITICAL_POOL`.


---

### 5. Conclusion

Le module **`03-PHASE1-Initialisation-Threads`** garantit que la couche d'exécution du système est **entièrement pré-allouée, segmentée par priorité** et **validée en performance**. Il établit une base d'exécution fiable et à faible latence, essentielle avant l'instanciation des managers métier qui dépendront de ces ressources.

---


| ID | Fonction / Message | Émetteur | Récepteur | Description |
| --- | --- | --- | --- | --- |
| 1 | **initThreads()** | System Manager | Thread Manager | Commande synchrone d'initialisation de la couche d'exécution. |
| 2 | **getThreadConfigs()** | Thread Manager | Config Store | Récupération des paramètres (tailles des 4 pools et niveaux de priorité). |
| 3 | **new PoolWorker()** | Thread Manager | PoolWorker | Instanciation (Loop) des 4 types de pools (Critical, Std, Bulk, Audit). |
| 4 | **startPersistentLoop()** | PoolWorker | PoolWorker | Auto-activation du thread en mode veille active (Ready-to-work). |
| 5 | **runPriorityValidation()** | Thread Manager | HCheckPriorityTest | Vérification technique de la priorité Real-Time du pool critique. |
| 6 | **logStatus()** | Thread Manager | LoggerPort | Journalisation du résultat du test et de l'état des pools. |
| 7 | **Initialization_Complete** | Thread Manager | System Manager | Retour du statut final : **SUCCESS** ou **CRITICAL_FAILURE**. |
| 8 | **systemStop()** | System Manager | System Manager | Déclenché immédiatement si le statut est CRITICAL_FAILURE. |
| 9 | **Phase_04_Start** | System Manager | System Manager | Poursuite de la séquence d'initialisation uniquement si SUCCESS. |

--- 

### 6. Ports et Interfaces


**IThreadManagerPort**
- **Implémenté par :** Thread Manager
- **Injecté dans / Utilisé par :** System Manager
- **Responsabilité opérationnelle :** Allocation et gestion des pools de threads, démarrage des loops persistantes, reporting de l’état initialisation
- **Règles d’accès ou d’usage :**
  - Invocation synchrone depuis System Manager uniquement.
  - Retour obligatoire de `Initialization_Complete` avant passage à la séquence suivante.
  - Interdiction d’accéder directement aux PoolWorkers depuis d’autres modules.
  - Phase autorisée : BOOTSTRAP_ONLY
  - Interdit en runtime métier

**IThreadPoolConfigPort**
- **Implémenté par :** Configuration Store
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Fournir tailles et priorités des pools
- **Règles d’accès ou d’usage :**
  - Lecture seule pendant l’initialisation.
  - Interdiction de modification en runtime.
  - Doit être disponible avant la création des PoolWorkers.
  - Phase autorisée : BOOTSTRAP_ONLY

**ILogger**
- **Implémenté par :** Logger
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Journalisation des étapes d’initialisation, tests de priorité et reporting des erreurs critiques
- **Règles d’accès ou d’usage :**
  - Log synchronisé pour toutes les étapes critiques.
  - Toute alerte critique doit être loguée avant propagation à System Manager.
  - Aucun bypass possible pour écriture directe par les PoolWorkers.

**SystemManagerPort**
- **Implémenté par :** System Manager
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Recevoir le statut final d’initialisation (`SUCCESS` / `CRITICAL_FAILURE`) et orchestrer la séquence suivante
- **Règles d’accès ou d’usage :**
  - Ne pas exécuter d’opérations métier tant que l’initialisation des pools n’est pas confirmée.
  - Cycle de vie synchronisé avec ThreadManagerPort.



---

### Note

**Monitoring & Alerting Thread Pools** : Ajouter un suivi temps réel des pools de threads via un port de monitoring interne, avec alertes synchronisées sur saturation ou blocage des threads critiques. Complète les H-Checks et garantit la visibilité continue sans affecter les pools non critiques.

**PoolWorkerInterface**
- **Implémenté par :** PoolWorker
- **Injecté dans / Utilisé par :** Thread Manager
- **Responsabilité opérationnelle :** Exécution persistante des jobs selon priorité (CRITICAL, STANDARD, BULK, AUDIT)
- **Règles d’accès ou d’usage :**
  - Priorité définie à l’instanciation et non modifiable.
  - Ne jamais détruire le PoolWorker pendant la session.
  - Isolation stricte : aucun partage inter-pools des jobs critiques.


**HCheckPriorityInterface**
- **Implémenté par :** Thread Manager
- **Injecté dans / Utilisé par :** PoolWorker CRITICAL_POOL
- **Responsabilité opérationnelle :** Vérifier que la priorité maximale OS est respectée
- **Règles d’accès ou d’usage :**
  - Test obligatoire avant retour SUCCESS au System Manager.
  - Échec → signal CRITICAL_FAILURE et déclenchement de `systemStop`.
  - Ne pas utiliser pour pools non critiques.
