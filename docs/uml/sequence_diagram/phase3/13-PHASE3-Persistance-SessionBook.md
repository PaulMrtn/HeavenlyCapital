## `13-PHASE3-Persistance-SessionBook`


<p align="center">
  <img src="../img/13-PHASE3-Persistance-SessionBook.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'assurer l'**enregistrement atomique et auditable** des résultats financiers définitifs de la session. Ce processus cristallise la **source du broker** (l'état réconcilié et certifié avec le courtier) pour servir de point de départ immuable à la session de trading suivante.

---

### 2. Contexte

Ce module s'exécute immédiatement après la validation de l'intégrité des données (Étape 12). Il transforme l'inventaire validé en une archive persistante, garantissant que le système redémarrera sur des positions 100 % alignées avec le courtier, éliminant ainsi toute dérive de calcul interne.

---

### 3. Logique Générale

1. **Génération de l'état certifié** : Le `PortfolioManager` instancie le `SettledSessionBook` à partir des données réconciliées issues de la **source du broker**.
2. **Idempotence** : Le DTO inclut un identifiant unique (`PortfolioID` + `Date`) permettant au **DIL** d'empêcher toute double écriture accidentelle.
3. **Isolation** : Le job est envoyé au pool **I/O Audit** pour garantir que cette opération critique dispose de ressources dédiées sans contention avec les flux de trading.
4. **Gestion des échecs** : En cas de rejet par la base de données, l'échec est logué par l'**AuditThread** mais l'alerte opérationnelle est gérée par le **JobManager**.

**Gestion du Failure Job (Résilience) :** E
En cas d'échec de la persistance, les mécanismes suivants sont activés :
  * **Retry avec Exponential Backoff** : Le système ne retente pas l'opération immédiatement. Il programme 3 tentatives avec un délai croissant (ex: 1s, 5s, 30s).
  * **Circuit Breaker** : Si les 3 tentatives échouent, le `JobManager` bascule le statut en `CRITICAL_STALL`. Au lieu de retenter, il déclenche une alerte via le `NotificationManager`.
  * **Mode "Emergency Local Dump"** : En cas d'échec persistant en base de données, le thread d'audit tente d'écrire le `SessionBookDTO` dans un fichier plat local (JSON/CSV). Cela permet au `SystemManager` de confirmer la fermeture tout en laissant une trace physique pour une récupération manuelle le lendemain.

---

### 4. Règles Critiques

* **Pool d'Isolation :** L'écriture doit obligatoirement utiliser le **Pool I/O Audit** pour s'assurer qu'elle n'est pas retardée par des tâches I/O moins critiques.
* **Audit avant Persistance** : Ce module ne démarre que si la réconciliation (Étape 12) a renvoyé un statut `OK` ou `DEGRADED_OK`.
* **Primauté de la source du broker** : Le contenu du `SettledSessionBook` doit refléter les positions du courtier en cas d'écart mineur, assurant la synchronisation pour le lendemain.
* **Zéro Doublon** : Le DIL doit rejeter toute tentative d'écriture si l'UID (Portfolio + Date) existe déjà en base de données.
* **Garantie ACID :** L'exécution de la persistance doit impérativement utiliser le fragment `DIL-AtomicDBWriteProces` pour s'assurer que l'enregistrement du livre de compte final est **atomique** et que la connexion est relâchée après le `COMMIT` ou le `ROLLBACK`.

---

### 5. Conclusion

Ce module garantit que l'état financier de la session est **enregistré de manière sûre, complète et auditable** avant d'entamer la phase d'analyse et de planification du jour suivant. Il est le point de vérité pour le PnL final.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | requestSettledSessionBook() | System Manager | Portfolio Manager | Ordre de cristallisation de l'état financier final basé sur la réconciliation broker effectuée en étape 12. |
| 2 | createSessionBook() | Portfolio Manager | SettledSessionBook | Instanciation de l'objet bilan. Les positions sont alignées sur la "Golden Source" du courtier. |
| 3 | sessionBookDTO(UID, State) | SettledSessionBook | Portfolio Manager | Génération du DTO incluant l'ID unique (PortfolioID + Date) pour garantir l'idempotence au niveau du DIL. |
| 4 | submitPersistenceJob(...) | Portfolio Manager | JobManager | Envoi de la tâche au pool "I/O Audit" pour isoler cette écriture critique des flux de trading. |
| 5 | requestThread(Pool: I/O Audit) | JobManager | ThreadManager | Demande d'allocation d'un thread prioritaire pour l'audit de fin de session. |
| 6 | threadAllocated(AuditThread) | ThreadManager | JobManager | Confirmation de l'assignation d'une ressource d'exécution dédiée. |
| 7 | runPersistenceJob(...) | JobManager | AuditThread | Lancement de la procédure de persistance sur le thread alloué. |
| 8 | executeAtomicWrite(...) | AuditThread | Data Ingestion Layer | Appel au DIL. Le système vérifie l'unicité de l'UID avant de déclencher la transaction ACID. |
| 9 | writeResult(SUCCESS/FAILURE) | Data Ingestion Layer | AuditThread | Retour du statut de l'écriture (Commit réussi ou Rollback en cas d'erreur/doublon). |
| 10 | logJobCompletion(Job_ID, FAIL, Details) | AuditThread | Log Service | [Branche Failure] Journalisation immédiate de l'échec technique avec détails pour audit. |
| 11 | jobExecutionFinished(ERROR) | AuditThread | JobManager | [Branche Failure] Notification au manager que la tâche a échoué. |
| 12 | notifyPersistenceError(Job_ID, Code) | JobManager | System Manager | [Branche Failure] Alerte à l'orchestrateur : la source de vérité financière n'a pas pu être sauvegardée. |
| 13 | sendCriticalAlert(SESSION_BOOK_FAIL) | JobManager | Notification Manager | [Branche Failure] Déclenchement d'une alerte externe (SMS/Pager) pour action humaine urgente. |
| 14 | logJobCompletion(Job_ID, SUCCESS, Hash) | AuditThread | Log Service | [Branche Success] Journalisation de la réussite avec empreinte numérique (Hash) du SessionBook. |
| 15 | jobExecutionFinished() | AuditThread | JobManager | [Branche Success] Notification de fin de tâche nominale. |
| 16 | jobValidationConfirmed(Job_ID) | JobManager | System Manager | [Branche Success] Signal de déblocage permettant de passer à la suite du workflow Post-Trade. |
| 17 | releaseThread() | AuditThread | ThreadManager | Libération de la ressource et retour du thread dans le pool I/O Audit. |

---


### 6. Ports et Interfaces

**PersistencePort**
* **Implémenté par** : `Data Integrity Layer (DIL)` / `AtomicDBWriteProcess`
* **Injecté dans / Utilisé par** : `AuditThread` (via `JobManager`)
* **Responsabilité opérationnelle** : Exécuter le vidage physique et atomique du `SettledSessionBook` vers la base de données. Elle garantit que l'enregistrement du livre de compte final est atomique (ACID) et que la connexion est relâchée après le COMMIT ou le ROLLBACK.
* **Règles d’accès ou d’usage** : Transactions atomiques obligatoires. Elle est invoquée dans cette séquence via le fragment `DIL-AtomicDBWriteProcess`.

**IJobSubmissionPort**
* **Implémenté par** : `Job Manager`
* **Injecté dans / Utilisé par** : `Portfolio Manager`
* **Responsabilité opérationnelle** : Permettre au `PortfolioManager` de soumettre de manière asynchrone la tâche de persistance du livre de compte. Elle découple la décision de cristallisation de l'exécution physique de l'écriture.
* **Règles d’accès ou d’usage** : Appel non-bloquant. Doit impérativement inclure la définition du pool cible `I/O Audit` pour l'arbitrage.

**IThreadDelegatePort**
* **Implémenté par** : `ThreadManager`
* **Injecté dans / Utilisé par** : `JobManager`
* **Responsabilité opérationnelle** : Allocation d'une ressource d'exécution spécifique (`AuditThread`) depuis le pool `I/O Audit`.
* **Règles d’accès ou d’usage** : Utilisation obligatoire du pool d'isolation "I/O Audit" pour garantir la priorité de la source du broker sur les autres tâches I/O.

**ILogger**
* **Implémenté par** : `Log Service`
* **Injecté dans / Utilisé par** : `AuditThread` (Success/Failure)
* **Responsabilité opérationnelle** : Journalisation immuable de l'issue de l'opération (Message 10 ou 14). En cas de succès, elle archive l'empreinte numérique (Hash) du DTO.
* **Règles d’accès ou d’usage** : Mode synchrone requis pour garantir que la trace d'audit est écrite avant la confirmation de fin de job.

**INotificationService**
* **Implémenté par** : `AlertingService` (Email, SMS, PagerDuty)
* **Injecté dans / Utilisé par** : `JobManager`
* **Responsabilité opérationnelle** : Envoi immédiat d'alertes critiques (`SESSION_BOOK_FAIL`) aux opérateurs humains en cas d'échec de la persistance après épuisement des retries.
* **Règles d’accès ou d’usage** : Doit être non-bloquant (Asynchrone). Usage strictement limité aux erreurs de sévérité CRITICAL.

**IProcessControlPort**
* **Implémenté par** : `System Manager`
* **Injecté dans / Utilisé par** : `JobManager`
* **Responsabilité opérationnelle** : Signaler au `System Manager` l'issue de la tâche de persistance via `jobValidationConfirmed` (Succès) ou `notifyPersistenceError` (Echec).
* **Règles d’accès ou d’usage** : Le `System Manager` utilise ce retour pour débloquer la suite du cycle (Phase III - Rebalancement) ou geler le système en cas d'erreur de la source du broker.

