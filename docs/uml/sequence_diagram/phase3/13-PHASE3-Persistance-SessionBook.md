## `13-PHASE3-Persistance-SessionBook`


<p align="center">
  <img src="../img/13-PHASE3-Persistance-SessionBook.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'assurer l'**enregistrement atomique et auditable** des résultats financiers définitifs de la journée (Position finale, PnL, ...) dans l'objet `SettledSessionBook`. Ce processus crée la **source de vérité** de la performance de la session.

---


### 2. Contexte

Ce module s'inscrit immédiatement après la validation de l'intégrité des données lors de l'Audit Initial (Étape 12). Il est crucial car il **prépare les données nécessaires** au calcul stratégique du prochain rebalancement (Étape 15). Contrairement aux enregistrements en temps réel (Fills), celui-ci est un enregistrement d'état global unique qui ne peut être exécuté qu'une seule fois à la clôture.

---


### 3. Logique Générale

Le `SystemManager` donne l'ordre au `PortfolioManager` de **cristalliser** son état en mémoire. Le `PortfolioManager` génère alors le DTO (`SettledSessionBook`) et le soumet au `JobManager`. Ce dernier alloue une ressource d'exécution (`AuditThread`) provenant du **Pool I/O Audit** pour garantir la priorité. Le thread exécute l'écriture via le `DIL` qui, en utilisant le processus **`DIL-AtomicDBWriteProces`**, garantit une transaction ACID (tout ou rien). Une fois l'écriture réussie et confirmée, le `JobManager` émet un signal au `SystemManager` pour débloquer la suite du cycle.

---


### 4. Règles Critiques

* **Dépendance Strict :** Ce module ne se lance que si l'Audit Initial (Étape 12) a réussi sans erreur critique.
* **Pool d'Isolation :** L'écriture doit obligatoirement utiliser le **Pool I/O Audit** pour s'assurer qu'elle n'est pas retardée par des tâches I/O moins critiques.
* **Garantie ACID :** L'exécution de la persistance doit impérativement utiliser le fragment `DIL-AtomicDBWriteProces` pour s'assurer que l'enregistrement du livre de compte final est **atomique** et que la connexion est relâchée après le `COMMIT` ou le `ROLLBACK`.
* **Validation de Flux :** Le `SystemManager` attend le signal **asynchrone** de `jobValidationConfirmed` pour considérer le module achevé, et non le simple retour de l'appel de soumission du job.

---

### 5. Conclusion

Ce module garantit que l'état financier de la session est **enregistré de manière sûre, complète et auditable** avant d'entamer la phase d'analyse et de planification du jour suivant. Il est le point de vérité pour le PnL final.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|requestSettledSessionBook()|System Manager|Portfolio Manager|Commande de cristallisation de l'état financier final de la session.|
|2|createSessionBook()|Portfolio Manager|SettledSessionBook|Instanciation de l'objet métier représentant le bilan de clôture.|
|3|sessionBookDTO|SettledSessionBook|Portfolio Manager|Retour de l'objet de transfert de données (DTO) immuable.|
|4|submitPersistenceJob(SessionBook, Pool: I/O Audit)|Portfolio Manager|JobManager|Soumission de la tâche de sauvegarde asynchrone au gestionnaire de travaux.|
|5|requestThread(Pool: I/O Audit)|JobManager|ThreadManager|Demande d'allocation d'une ressource d'exécution dans le pool dédié à l'audit.|
|6|threadAllocated(AuditThread)|ThreadManager|JobManager|Confirmation et assignation d'un thread spécifique pour la tâche.|
|7|runPersistenceJob(SettledSessionBook)|JobManager|AuditThread|Lancement effectif de la logique de persistance sur le thread alloué.|
|8|executeAtomicWrite(SettledSessionBook)|AuditThread|Data Ingestion Layer|Appel au DIL pour l'exécution de la transaction atomique vers la base de données.|
|9|writeResult(SUCCESS/FAILURE)|Data Ingestion Layer|AuditThread|Retour du statut de la transaction ACID (Commit ou Rollback).|
|10|logJobCompletion(Job_ID, Result)|Data Ingestion Layer|Log Service|Journalisation immuable de l'issue de l'opération de persistance pour audit.|
|11|jobExecutionFinished()|AuditThread|JobManager|Notification de fin de cycle de vie du thread de travail.|
|12|jobValidationConfirmed(Job_ID)|JobManager|System Manager|Signal de déblocage asynchrone confirmant la persistance de la source de vérité.|
|13|releaseThread()|AuditThread|ThreadManager|Libération de la ressource et retour du thread dans le pool disponible.|
