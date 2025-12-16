## `14-PHASE3-Persistance-Config-Cloture`

<p align="center">
  <img src="../img/14-PHASE3-Persistance-Config-Cloture.jpg" width="900">
</p>

---

### 1. Objectif

Ce module a pour finalité d'enregistrer l'**État de Reprise** du système de trading. Il garantit la persistance atomique de la configuration finale de la session pour assurer un redémarrage (Phase I - Bootstrapping) sécurisé et conforme à l'état laissé à la fermeture.

---


### 2. Contexte

Ce processus s'inscrit dans la **Phase III (Post-Trade)**, immédiatement après la Réconciliation Finale (Étape 12) et la Persistance du SessionBook (Étape 13). Son existence est justifiée par la nécessité de **séparer les données transactionnelles** (positions, PnL) des **données d'état du moteur de risque et d'exécution** (limites, compteurs). Il est un prérequis critique pour la Phase IV (Préparation du Target) et la Phase I (Bootstrapping) suivantes.

---


### 3. Logique Générale

Le **System Manager** déclenche le **Session Manager**, qui est responsable de la collecte des données d'état auprès du **Risk Monitor (RM)** et du **Portfolio Manager (PM)** (état des `RiskSession`, `PortfolioState`, compteurs, etc.). Ces données sont agrégées dans un objet **`SessionConfigDTO`**. Le Session Manager soumet ensuite la tâche de persistance au **Job Manager**, en exigeant l'utilisation d'un **Pool I/O Critique**. Le **Job Manager** alloue un thread via le **Thread Manager** et délègue l'écriture atomique au **Data Integrity Layer (DIL)**, qui gère la transaction en base de données.

---


### 4. Règles Critiques

* **Priorité I/O :** L'écriture doit s'effectuer sur un **Pool I/O Critique** pour garantir l'isolation et la complétion immédiate, sans être ralentie par des tâches de nettoyage (Bulk I/O).
* **Atomicité :** La persistance est exécutée via le processus **`DIL-AtomicDBWriteProces`**. L'écriture doit être intégralement validée (`COMMIT`) ou intégralement annulée (`ROLLBACK`).
* **Dépendance :** Le **System Manager** ne peut pas passer à l'étape suivante (Arrêt Sécurisé - Étape 15) tant que le Session Manager n'a pas confirmé la validation réussie de cette persistance.
* **Gestion d'Erreur :** En cas d'échec du `COMMIT` (erreur critique de base de données), le processus atomique doit immédiatement déclencher une alerte fatale (`CRITICAL_DB_FAILURE`) pour empêcher le système de passer en veille non sécurisée.

---

### 5. Conclusion

Le module **14-PHASE3-Persistance-Config-Cloture** garantit que le système se couche avec une **preuve d'intégrité opérationnelle** et une configuration de reprise connue. Cette étape est le **point de non-retour sécurisé** qui permet au système de redémarrer le lendemain avec une continuité totale de ses limites de risque et de ses mécanismes de protection.
