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
