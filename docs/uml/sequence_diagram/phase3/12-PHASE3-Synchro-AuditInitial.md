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

1. **Synchronisation Forcée** 
   Le `SystemManager` ordonne au `JobManager` de **bloquer** l'exécution jusqu'à ce que tous les I/O critiques en cours soient **atomiquement confirmés** par le `DIL`.

2. **Réconciliation Typée**
   Le `PortfolioManager` récupère l'état final auprès du courtier (`IBKR Gateway`) et le compare avec l'état interne gelé.
   Cette comparaison retourne désormais un **statut typé**, permettant trois chemins explicites :

   * **RECONCILED_OK** : cohérence fonctionnelle atteinte (écarts négligeables ou arrondis).
   * **DEGRADED_OK** : écarts mesurés mais tolérés (différences de quantité dans une marge définie).
   * **CRITICAL_FAILURE** : incohérence bloquante (instrument manquant, position inversée, écart hors seuil).

Seul le statut **CRITICAL_FAILURE** empêche la poursuite du workflow Post-Trade.

---

### 4. Règles Critiques

* **Atomicité Précédente**
  L'audit ne peut démarrer qu'après confirmation explicite du `DIL`.

* **Log de Transition**
  Le `marketCloseEvent` est journalisé de manière synchrone.

* **Gestion de la Gravité**
  La réconciliation finale doit classifier l’écart selon trois niveaux :

  * **CRITICAL_FAILURE** : arrêt immédiat du workflow stratégique.
  * **DEGRADED_OK** : poursuite contrôlée avec log d’anomalie et alerte humaine.
  * **RECONCILED_OK** : poursuite nominale sans action corrective.

* **Tolérance Paramétrée**
  Les seuils de tolérance (quantité, arrondis, micro-écarts) sont **définis statiquement** et versionnés pour audit.


---

### 5. Conclusion

Ce module garantit que le passage en Phase III s’effectue sur un **état final cohérent, qualifié et auditable**.
L’introduction de niveaux de gravité explicites renforce la **résilience opérationnelle**, évite les arrêts excessifs et améliore l’exploitabilité post-incident sans compromettre l’intégrité financière.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|marketCloseEvent()|Market Clock|System Manager|Signal de clôture horaire déclenchant la transition vers le mode Post-Trade.|
|2|LogCriticalEvent("Market Closed...")|System Manager|Log Session|Journalisation synchrone et immuable de l'heure exacte de réception du signal de clôture.|
|3|updateSystemStatus(POST_TRADE)|System Manager|System Manager|Auto-appel pour basculer l'état interne du système et verrouiller les fonctions d'exécution.|
|4|forcePendingJobCompletion()|System Manager|Job Manager|Commande prioritaire ordonnant la finalisation forcée de toutes les tâches asynchrones en cours.|
|5|flushCriticalBuffers()|Job Manager|Data Integrity Layer|Ordre de transfert immédiat des buffers mémoire (Fills, Quotes) vers la couche de persistance.|
|6|validationConfirmed()|Data Integrity Layer|Job Manager|Confirmation atomique que l'intégralité des buffers critiques est sécurisée en base de données.|
|7|validationConfirmed()|Job Manager|System Manager|Signal global confirmant que le système est gelé et que toutes les données sont persistées.|
|8|startFinalReconciliation()|System Manager|Portfolio Manager|Déclenchement de la procédure d'audit de cohérence entre l'inventaire local et externe.|
|9|fetchBrokerPosition(session_id)|Portfolio Manager|IBKR Gateway|Requête réseau vers la passerelle du courtier pour récupérer l'inventaire financier réel.|
|10|brokerPositionData|IBKR Gateway|Portfolio Manager|Transmission des données d'inventaire consolidées provenant du courtier.|
|11|logCriticalError(DATA_INTEGRITY...)|Portfolio Manager|Log Session|Journalisation immédiate en cas d'incohérence détectée entre les états local et distant.|
|12|sendCriticalAlert(RECON_FAILURE)|Portfolio Manager|Notification Manager|Envoi d'une alerte urgente asynchrone aux opérateurs en cas de désynchronisation critique.|
|13|CRITICAL_FAILURE(FailureCode)|Portfolio Manager|System Manager|Signal d'arrêt immédiat du workflow si l'écart de réconciliation dépasse les seuils tolérés.|
|14|reconciliationResult(status, severity, details)|Portfolio Manager|System Manager|Retour du statut typé (OK ou DEGRADED) permettant la poursuite contrôlée du workflow.|

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

**IDataIntegrityCheckPort**
* **Implémenté par** : `PortfolioManager`  
* **Utilisé par** : `System Manager`
* **Responsabilité** : Exécute la **réconciliation finale Post-Trade** entre l’état interne gelé (via DIL) et l’état réel du broker (IBKR) avant le démarrage de l’audit.
**Statuts de retour** :
  * **RECONCILED_OK** : cohérence atteinte, écarts négligeables.
  * **DEGRADED_OK** : écart toléré (dans un seuil défini), poursuite avec alerte.
  * **CRITICAL_FAILURE(FailureCode)** : incohérence bloquante, arrêt immédiat.
**Règles d’usage** :
  * Appel autorisé uniquement après `validationConfirmed`.
  * État strictement en lecture (système gelé).
  * Seuils de tolérance statiques, auditables.
  * Toute sortie ≠ `RECONCILED_OK` est journalisée synchronement.

---

### NOTE 

* **Timeout :** L'appel fetchBrokerPosition doit intégrer une limite temporelle stricte ; en cas de dépassement, le système doit lever une alerte de connectivité et stopper l'audit.


