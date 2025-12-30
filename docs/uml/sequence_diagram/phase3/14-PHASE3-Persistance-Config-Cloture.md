## `14-PHASE3-Persistance-Config-Cloture`

<p align="center">
  <img src="../img/14-PHASE3-Persistance-Config-Cloture.jpg" width="900">
</p>

---

### 1. Objectif

Ce module a pour finalité d'enregistrer l'**État de Reprise (Configuration de Clôture)** du système. Il garantit la persistance atomique des métadonnées de la session pour assurer un redémarrage sécurisé et intègre lors du prochain *bootstrapping* (Phase I).

---


### 2. Contexte

Ce processus s'inscrit dans la **Phase III (Post-Trade)**, se concentrant sur la sauvegarde des **règles**. Il est essentiel pour distinguer les données d'audit financier de la configuration opérationnelle. Son exécution est un prérequis critique pour la transition vers l'arrêt sécurisé (Étape 15).

---


### 3. Logique Générale

Le **System Manager** déclenche le **Session Manager**, qui orchestre la collecte des configurations de reprise auprès des trois managers métiers : **Risk Monitor (RM)**, **Portfolio Manager (PM)** et **Order Manager (OM)**. Ces configurations (`RiskManagerConfigDTO`, `PortfolioManagerConfigDTO`, `OrderManagerConfigDTO`) sont agrégées dans un unique objet **`SessionConfigDTO`**. Ce DTO est ensuite soumis au **Job Manager** pour une exécution atomique via le **Data Integrity Layer (DIL)**, en utilisant obligatoirement un thread du **Pool I/O Critique**.

---


### 4. Règles Critiques

* **Cohérence de Reprise :** L'écriture doit inclure les métadonnées des trois managers (RM, PM, OM) pour garantir une vision complète des règles actives au moment de l'arrêt.
* **Priorité I/O et Atomicité :** La persistance doit être exécutée avec la plus haute priorité et de manière atomique (tout ou rien) grâce au processus DIL, assurant que l'état de la configuration est intégralement enregistré ou annulé.
* **Dépendance Fatale :** Le **System Manager** ne peut jamais progresser vers l'arrêt sécurisé (Étape 15) tant que la validation réussie de cette écriture critique n'a pas été confirmée par le Session Manager. En cas d'échec du `COMMIT`, une alerte fatale est levée.
* **Isolation :** Cette étape vise à enregistrer uniquement les *configs* (règles de démarrage/protection), et non l'état financier (géré en Étape 13).

---

### 5. Conclusion

Le module **14-PHASE3-Persistance-Config-Cloture** garantit l'établissement d'un **point de vérité immuable** pour la configuration du moteur de trading. Il est la vérification finale que les paramètres de sécurité et les compteurs internes ont été correctement verrouillés, permettant un redémarrage du système dans un état d'intégrité opérationnelle absolue.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|requestFinalConfigSnapshot(session_id)|SystemManager|SessionManager|Ordre global de capture de l'état de reprise pour la session spécifiée.|
|2|getRiskManagerConfig()|SessionManager|RiskMonitor|Requête de collecte des seuils et limites de risque actifs en clôture.|
|3|RiskManagerConfigDTO|RiskMonitor|SessionManager|Retour des métadonnées de risque sous forme d'objet de transfert immuable.|
|4|getOrderManagerConfig()|SessionManager|OrderManager|Requête de collecte de l'état des compteurs d'ordres et paramètres de routage.|
|5|OrderManagerConfigDTO|OrderManager|SessionManager|Retour des métadonnées de l'Order Manager.|
|6|getPortfolioManagerConfig()|SessionManager|PortfolioManager|Requête de collecte des paramètres de gestion de portefeuille (hors inventaire financier).|
|7|PortfolioManagerConfigDTO|PortfolioManager|SessionManager|Retour des métadonnées du Portfolio Manager.|
|8|submitAtomicPersist(SessionConfigDTO, PRIORITY_CRITICAL)|SessionManager|JobManager|Soumission du snapshot agrégé pour persistance asynchrone prioritaire.|
|9|requestThread(POOL_CRITICAL, DIL_TASK)|JobManager|ThreadManager|Demande d'allocation d'une ressource d'exécution dans le pool critique I/O.|
|10|threadAllocated(CriticalThreadRef)|ThreadManager|JobManager|Confirmation et assignation d'un thread de haute priorité.|
|11|DIL.atomicWrite(SessionConfigDTO)|JobManager|DataIngestionLayer|Exécution de la transaction ACID via le fragment AtomicDBWriteProcess.|
|12|jobCompleted(ValidationStatus.OK/ERROR)|DataIngestionLayer|JobManager|Notification de l'issue de l'écriture (Commit ou Rollback).|
|13|persistenceConfirmed()|JobManager|SessionManager|Signal de confirmation de la sauvegarde de l'état de reprise.|
|14|configPersistedOK()|SessionManager|SystemManager|Signal final de déblocage autorisant la transition vers l'arrêt sécurisé.|
