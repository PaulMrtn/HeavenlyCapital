## `14-PHASE3-Persistance-Config-Cloture`

<p align="center">
  <img src="../img/14-PHASE3-Persistance-Config-Cloture.jpg" width="900">
</p>

---

### 1. Objectif

Ce module assure la sauvegarde de l'**État de Reprise (Configuration de Clôture)** du système. Il garantit la persistance atomique des métadonnées de la session pour assurer un redémarrage sécurisé et intègre lors du prochain *bootstrapping* (Phase I).

---

### 2. Contexte

S'inscrivant dans la **Phase III (Post-Trade)**, ce processus verrouille les **règles opérationnelles**. Il est structurellement distinct de la persistance financière et constitue le dernier rempart de sécurité avant l'arrêt physique du moteur (Étape 15).

---

### 3. Logique Générale

Le **System Manager** déclenche le **Session Manager**, qui orchestre la collecte séquentielle auprès des managers métiers (**RM, OM, PM**).

* **Consolidation & Santé :** La fonction `mapToEntity()` transforme les DTO en une entité technique immuable et génère un bilan de santé unique.
* **Persistance Résiliente :** L'entité est soumise au **Job Manager** qui gère de manière autonome les tentatives d'écriture DB et le repli sur fichier local en cas d'échec critique.

---

### 4. Règles Critiques

* **Bilan de Santé Global (Optimisation) :** Si une configuration est incomplète ou manquante lors de la collecte, le système ne génère qu'**un seul log et une seule notification** consolidée. Le processus n'est pas bloqué ; le système privilégie la continuité en s'appuyant sur la logique de récupération de la Phase I.
* **Résilience de Persistance (Internalisée) :** Le Job Manager exécute une boucle de **3 tentatives (Retry)** via le DIL. En cas d'échec persistant, il déclenche un **Emergency Local Dump** (format JSON/Fichier plat) via l'AuditThread pour garantir qu'aucune donnée de reprise n'est perdue.
* **Extensibilité :** L'architecture est dite `«extensible»`. Le Session Manager peut agréger des configurations de composants d'instance (multi-instances) dynamiquement sans modifier la structure du Job Manager ou du DIL.
* **Validation de Clôture :** Le System Manager ne peut valider l'arrêt que sur réception d'un statut `SUCCESS` ou `DEGRADED` (Local Dump actif).

---

### 5. Conclusion

Le module **14-PHASE3-Persistance-Config-Cloture** garantit l'établissement d'un **point de vérité immuable** pour la configuration du moteur de trading. Il est la vérification finale que les paramètres de sécurité et les compteurs internes ont été correctement verrouillés, permettant un redémarrage du système dans un état d'intégrité opérationnelle absolue. Il transforme une potentielle défaillance critique d'infrastructure en un mode de fonctionnement dégradé maîtrisé, assurant l'intégrité opérationnelle absolue pour la prochaine ouverture de session.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|requestFinalConfigSnapshot(session_id)|SystemManager|SessionManager|Initialise le processus de clôture pour une session spécifique.|
|2|getRiskManagerConfig()|SessionManager|RiskMonitor|Collecte les paramètres de risque actifs (seuils, limites).|
|3|getOrderManagerConfig()|SessionManager|OrderManager|Récupère l'état des compteurs et des séquences d'ordres.|
|4|getPortfolioManagerConfig()|SessionManager|PortfolioManager|Récupère les pondérations et allocations du portefeuille.|
|5|mapToEntity(RiskDTO,OrderDTO,PortDTO)|SessionManager|SessionManager|Mapping interne et consolidation des DTO en une Entité technique unique.|
|6|logClosureWarning(Report)|SessionManager|LogService|Enregistre un bilan de santé si des données de config sont manquantes.|
|7|sendCriticalAlert(REPORT_INCOMPLETE)|SessionManager|NotificationManager|Alerte les opérateurs d'une clôture avec des données partielles.|
|8|submitAtomicPersist(SessionConfigEntity, PRIORITY_CRITICAL)|SessionManager|JobManager|Soumission asynchrone de l'entité pour persistance prioritaire.|
|9|requestThread(POOL_CRITICAL,DIL_TASK)|JobManager|ThreadManager|Demande d'allocation d'un thread dédié au pool d'Audit/IO.|
|10|threadAllocated(CriticalThreadRef)|ThreadManager|JobManager|Confirmation de l'allocation d'une ressource de calcul pour l'IO.|
|11|DIL.atomicWrite(SessionConfigEntity)|JobManager|DataIngestionLayer|Tentative d'écriture transactionnelle en base de données.|
|12|jobCompleted(ValidationStatus.OK/ERROR)|DataIngestionLayer|JobManager|Retour de l'état d'exécution (déclenche le fallback interne si ERROR).|
|13|persistenceConfirmed(Status)|JobManager|SessionManager|Confirmation finale du stockage (Nominal ou Dégradé/Local Dump).|
|14|configPersistedOK()|SessionManager|SystemManager|Signal final autorisant l'arrêt physique sécurisé du moteur.|

---

### 6. Ports et Interfaces

**ISessionConfigProvider**
* **Implémenté par** : `SessionManager` (via agrégation des DTO)
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Fournir l'état final immuable des règles (Risque, Portefeuille, Ordres) avant l'arrêt.
* **Règles d’accès ou d’usage** : Lecture seule. Snapshot immuable généré par `mapToEntity`.

**IBootstrapReadinessCheck**
* **Implémenté par** : `RiskMonitor`, `OrderManager`, `PortfolioManager`
* **Injecté dans / Utilisé par** : `SessionManager`
* **Responsabilité opérationnelle** : Fournir les configurations de reprise via les appels `get...Config()`.
* **Règles d’accès ou d’usage** : Appel synchrone obligatoire en Phase Post-Trade.

**PersistencePort**
* **Implémenté par** : `Data Ingestion Layer (DIL)`
* **Injecté dans / Utilisé par** : `JobManager`
* **Responsabilité opérationnelle** : Point d’accès unique pour la persistance atomique de la `SessionConfigEntity`.
* **Règles d’accès ou d’usage** : Passage obligatoire par le fragment `AtomicDBWrite`. Isolation totale des objets métier.

**IJobSubmissionPort**
* **Implémenté par** : `JobManager`
* **Injecté dans / Utilisé par** : `SessionManager`
* **Responsabilité opérationnelle** : Soumission asynchrone de la tâche de persistance critique (`submitAtomicPersist`).
* **Règles d’accès ou d’usage** : Appel non-bloquant. Priorité `PRIORITY_CRITICAL` requise pour l'arbitrage.

**IThreadDelegatePort**
* **Implémenté par** : `ThreadManager`
* **Injecté dans / Utilisé par** : `JobManager`
* **Responsabilité opérationnelle** : Allocation d'un thread spécifique depuis le pool `POOL_CRITICAL` pour l'exécution physique.
* **Règles d’accès ou d’usage** : Utilisation exclusive du pool réservé à l'audit et à l'IO critique.

**ILogger**
* **Implémenté par** : `LogService`
* **Injecté dans / Utilisé par** : `SessionManager`
* **Responsabilité opérationnelle** : Enregistrement du rapport de santé (`logClosureWarning`) si les données sont incomplètes.
* **Règles d’accès ou d’usage** : Un seul log consolidé par session pour éviter le bruit.

**INotificationService**
* **Implémenté par** : `NotificationManager`
* **Injecté dans / Utilisé par** : `SessionManager`, `JobManager`
* **Responsabilité opérationnelle** : Envoi d'alertes en cas de données incomplètes ou d'activation de l'Emergency Local Dump.
* **Règles d’accès ou d’usage** : Doit être non-bloquant. Utilisé uniquement pour les messages `sendCriticalAlert`.

**IProcessControlPort**
* **Implémenté par** : `SystemManager`
* **Injecté dans / Utilisé par** : `SessionManager`
* **Responsabilité opérationnelle** : Autoriser la transition vers l'arrêt physique via `configPersistedOK()`.
* **Règles d’accès ou d’usage** : Bloqué tant que le statut `SUCCESS` ou `DEGRADED` (Local Dump) n'est pas confirmé par le `JobManager`.

---
