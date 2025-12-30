## `12-PHASE3-Synchro-AuditInitial`

<p align="center">
  <img src="../img/12-PHASE3-Synchro-AuditInitial.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de garantir l'**intégrité totale et l'atomicité** de l'état du système à la clôture du marché, en synchronisant la fin de toutes les opérations d'exécution pour permettre le démarrage sécurisé de la phase d'audit.

---

### 2. Contexte

Ce module est le **point de transition critique** entre la Phase II (In-Trade) et la Phase III (Post-Trade). Déclenché par le signal de fermeture du marché (`marketCloseEvent`), il existe pour **geler** l'état du système et **vérifier la cohérence** des données financières avant toute analyse ou calcul stratégique. Il est le garant de la fiabilité des audits post-trade.

---

### 3. Logique Générale

Le processus est initié par le `SystemManager` recevant l'événement de fermeture. Il procède en deux étapes principales :

1. **Synchronisation Forcée :** Le `SystemManager` ordonne au `JobManager` de **bloquer** l'exécution jusqu'à ce que tous les I/O critiques en cours (persistance des derniers Fills, vidage des buffers de MarketQuote) soient **atomiquement confirmés** par le `DIL`.
2. **Réconciliation :** Le `PortfolioManager` récupère l'état final auprès du courtier (`IBKR Gateway`) et le compare avec l'état interne. Cette comparaison aboutit à deux chemins : soit le statut est **OK** (poursuite vers l'étape 13), soit il y a **échec critique**.

---

### 4. Règles Critiques

* **Atomicité Précédente :** La synchronisation (étape 3) est absolue. L'audit ne peut démarrer que si la validation de persistance du `DIL` est confirmée.
* **Log de Transition :** Le `marketCloseEvent` est journalisé de manière synchrone dès sa réception pour garantir une trace d'audit du moment exact de la fermeture.
* **Tolérance Zéro :** Si la Réconciliation révèle un **écart critique** (`data_discrepancy`), le `PortfolioManager` enregistre l'incident de manière **synchrone** (`logCriticalError`) et alerte immédiatement les opérateurs.
* **État de Poursuite :** Le système ne procède aux étapes Post-Trade suivantes (Persistance en Base de Données) qu'à la condition stricte que le `SystemManager` ait reçu la confirmation `reconciliationOK()`.

---

### 5. Conclusion

Ce module est essentiel pour l'intégrité financière. Il garantit que le système passe en Phase III sur un **état final, complet et audité**, en isolant les conséquences d'un écart critique par une annulation immédiate du flux de travail stratégique et une alerte à priorité maximale.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|marketCloseEvent()|Market Clock|System Manager|Signal de clôture déclenchant la fin de la session de trading.|
|2|LogCriticalEvent("Market Closed...")|System Manager|Log Session|Journalisation synchrone immédiate de l'événement de fermeture.|
|3|updateSystemStatus(POST_TRADE)|System Manager|System Manager|Changement interne d'état pour verrouiller les fonctions In-Trade.|
|4|forcePendingJobCompletion()|System Manager|Job Manager|Commande de vidage des files d'attente pour finaliser les tâches en cours.|
|5|flushCriticalBuffers()|Job Manager|Data Integrity Layer|Ordre de persistance immédiate des buffers de données critiques.|
|6|validationConfirmed()|Data Integrity Layer|Job Manager|Confirmation que toutes les écritures atomiques sont sécurisées en DB.|
|7|validationConfirmed()|Job Manager|System Manager|Notification globale de la fin de la synchronisation I/O.|
|8|startFinalReconciliation()|System Manager|Portfolio Manager|Déclenchement de la procédure de vérification des positions finales.|
|9|fetchBrokerPosition(session_id)|Portfolio Manager|IBKR Gateway|Requête externe pour récupérer l'inventaire réel chez le courtier.|
|10|brokerPositionData|IBKR Gateway|Portfolio Manager|Retour des données d'inventaire du courtier.|
|11|logCriticalError(DATA_INTEGRITY...)|Portfolio Manager|Log Session|Enregistrement d'un écart entre le local et le broker (chemin Failure).|
|12|sendCriticalAlert(RECON_FAILURE)|Portfolio Manager|Notification Manager|Alerte asynchrone pour intervention humaine immédiate.|
|13|CRITICAL_FAILURE|Portfolio Manager|System Manager|Signal d'arrêt du workflow suite à une corruption ou un écart de données.|
|14|reconciliationOK()|Portfolio Manager|System Manager|Confirmation de cohérence permettant la suite du cycle Post-Trade.|

---

### 6. Ports et Interfaces

**IProcessControlPort**
* **Implémenté par** : `Runtime Environment` / `System Manager`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Gérer les transitions d'état de vie du processus, notamment le passage à l'état `POST_TRADE` (Message 3) ou l'arrêt immédiat via `systemStop(CRITICAL_ERROR)` en cas d'échec de réconciliation (Message 13).
* **Règles d’accès ou d’usage** : L'appel doit être atomique et garantir la fermeture des descripteurs de fichiers ouverts lors d'un arrêt forcé.

**IJobSubmissionPort**
* **Implémenté par** : `Job Manager`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Permettre au System Manager de commander la finalisation forcée des tâches en cours via `forcePendingJobCompletion()` (Message 4).
* **Règles d’accès ou d’usage** : Dans cette séquence de clôture, l'appel est utilisé pour vider les files asynchrones et assurer que plus aucun job "In-Trade" ne sature les ressources durant l'audit.

**PersistencePort**
* **Implémenté par** : Data Integrity Layer (DIL) / AtomicDBWriteProcess
* **Utilisé par** : `Job Manager`
* **Responsabilité opérationnelle** : Exécuter le vidage physique des buffers critiques (`flushCriticalBuffers`, Message 5) pour garantir que l'audit porte sur des données persistées.
* **Règles d’accès ou d’usage** : Transactions atomiques obligatoires. L'audit ne peut démarrer qu'après la confirmation de cette couche.

**BrokerGatewayPort**
* **Implémenté par** : Gateway externe (IBKR)
* **Utilisé par** : `Portfolio Manager`
* **Responsabilité opérationnelle** : Fournir l'accès aux données réelles du courtier via `fetchBrokerPosition` (Message 9) pour comparaison avec l'état interne.
* **Règles d’accès ou d’usage** : Encapsulation totale. Le Portfolio Manager utilise ce port uniquement pour la lecture de l'inventaire final.

**INotificationService**
* **Implémenté par** : AlertingService (Email, SMS, PagerDuty)
* **Utilisé par** : `Portfolio Manager`
* **Responsabilité opérationnelle** : Envoi immédiat d'alertes critiques (`RECON_FAILURE`, Message 12) aux opérateurs humains en cas d'écart de données.
* **Règles d’accès ou d’usage** : Usage strictement limité aux erreurs de sévérité CRITICAL ou FATAL détectées lors de la réconciliation.

**IDataIntegrityAuditPort**
* **Implémenté par** : `PortfolioManager`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Point d'entrée de la logique de réconciliation finale (`startFinalReconciliation`, Message 8). Compare l'état interne (gelé via le DIL) et l'état externe (IBKR).
* **Règles d’accès ou d’usage** : Ne peut être invoqué qu'après réception de `validationConfirmed` en provenance du JobManager. Doit retourner un statut binaire : `reconciliationOK` ou `CRITICAL_FAILURE`.

---

### NOTE 

* **Timeout :** L'appel fetchBrokerPosition doit intégrer une limite temporelle stricte ; en cas de dépassement, le système doit lever une alerte de connectivité et stopper l'audit.
