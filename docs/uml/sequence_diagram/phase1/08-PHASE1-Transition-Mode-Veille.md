## `08-PHASE2-Transition-Mode-Veille`

<p align="center">
  <img src="../img/08-PHASE1-Transition-Mode-Veille.jpg" width="900">
</p>

--- 

### 1. Objectif

La finalité de ce module est de faire passer le système de l'état d'initialisation réussie à l'état de **veille sécurisée et active** (`WAITING`), et d'attendre l'événement temporel déclencheur de l'ouverture du marché.

---

### 2. Contexte

Cette séquence marque la fin de la **Phase 1 (Bootstrapping / PreTrade)**. Elle est déclenchée après la validation finale (Étape 07) qui a confirmé la cohérence opérationnelle et l'intégrité de l'infrastructure. Son rôle est de maintenir la disponibilité opérationnelle du système sans exécuter de stratégie de trading.

---

### 3. Logique Générale

Le **`System Manager (SM)`** commence par mettre à jour l'état global du système à **`READY_FOR_TRADING`**. Le système entre ensuite dans un mode **d'attente asynchrone** (`Wait for MarketOpenEvent()`). Pendant cette attente passive, une boucle de surveillance est lancée en arrière-plan. Cette boucle exécute un **Heartbeat** périodique, où l'`Order Manager (OM)` vérifie activement la stabilité de la connexion avec l'`IBKR Gateway`. Le mode veille se termine uniquement lorsque le **`Market Clock`** envoie le signal **`MarketOpenEvent()`**. À la réception de ce signal, le SM enregistre l'événement dans les logs (audit), puis lance immédiatement la (InTrade).

---

### 4. Règles Critiques

* **Point de Non-Retour :** La mise à jour du statut vers **`READY_FOR_TRADING`** confirme que tous les contrôles de sécurité (LIVE vs PAPER) ont été passés avec succès.
* **Surveillance Obligatoire :** La boucle de **Heartbeat** doit être maintenue. Si la vérification périodique de la connexion externe par l'`OM` échoue durant cette phase, le `SM` doit déclencher un **arrêt d'urgence** (`systemStop(CRITICAL_ERROR)`) car l'exécution serait impossible à l'ouverture.
* **Déclenchement Auditable** : La réception du signal d'ouverture doit obligatoirement être enregistrée via un log critique. Cette trace auditable est essentielle pour la réconciliation des horaires et la preuve de l'heure exacte du début d'exécution.
* **Déclenchement Temporel :** Le seul événement qui met fin à l'attente est le signal asynchrone émis par le **`Market Clock`** à l'heure d'ouverture définie.

---

### 5. Conclusion

Ce module garantit que le système reste **sain et réactif** pendant la période d'attente. Il s'assure que toutes les conditions techniques sont remplies pour un démarrage immédiat et sécurisé, assurant une transition sans accroc de l'état de préparation à l'état d'exécution au moment précis de l'ouverture du marché.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|UpdateSystemStatus(READY_FOR_TRADING)|SystemManager|SystemManager|Auto-appel verrouillant la fin de la Phase 1 et autorisant la mise en veille.|
|2|Wait for MarketOpenEvent()|SystemManager|SystemManager|Transition vers l'état d'écoute asynchrone des signaux horaires.|
|3|HCheckLHBHealthHeartbeat()|SystemManager|HistoricLiveHub|Vérification synchrone de l'intégrité du buffer et de la fraîcheur des données.|
|4|Return Status|HistoricLiveHub|SystemManager|Réponse confirmant que le Double-Buffering et l'indexation sont opérationnels.|
|5|HCheckExternalConnectionHeartbeat()|SystemManager|OrderManager|Déclenchement de la routine de test de la liaison broker.|
|6|pingConnectionStatus()|OrderManager|IBKRGateway|Requête technique de bas niveau pour tester la réactivité du tunnel FIX/API.|
|7|Return ConnectionStatus|IBKRGateway|OrderManager|Réponse de l'infrastructure externe sur l'état de la session broker.|
|8|Return Status|OrderManager|SystemManager|Transmission du statut de connectivité consolidé au gestionnaire système.|
|9|LogWarning()|SystemManager|LogService|Journalisation d'une anomalie temporaire (sous le seuil de tolérance défini).|
|10|Emergency_Standby_Reset()|SystemManager|SystemManager|Appel de la séquence de purge et retour forcé à la Phase 06 (Full Bootstrap).|
|11|MarketOpenEvent()|MarketClock|SystemManager|Signal asynchrone prioritaire déclenchant la fin de la veille active.|
|12|LogCriticalEvent("Market Open Received")|SystemManager|LogService|Enregistrement immuable du signal d'ouverture pour audit et réconciliation.|

---

### 6. Ports et Interfaces

**IExternalConnectivity**
- **Implémenté par** : `OrderManager`
- **Injecté dans / Utilisé par** : `SystemManager`
- **Responsabilité opérationnelle** : Vérification de la liaison physique et logique avec le courtier (Gateway/FIX).
- **Règles d’accès ou d’usage** : Timeout strict de 5000ms. Tout échec est considéré comme une erreur critique en mode LIVE.

**BrokerGatewayPort**
- **Implémenté par** : `Gateway externe (IBKR)`
- **Injecté dans / Utilisé par** : `Order Manager`
- **Responsabilité opérationnelle** : Transmission technique des ordres, réception des callbacks broker et gestion CRITICAL vs STANDARD.
- **Règles d’accès ou d’usage** : Aucun accès direct par PM ou RM. Encapsulation totale dans l’Order Manager.

**IMarketEventProvider**
- **Implémenté par** : `Market Clock`
- **Injecté dans / Utilisé par** : `System Manager`
- **Responsabilité opérationnelle** : Émission de signaux asynchrones basés sur les horaires officiels d'échange et notification des événements de structure de session (MarketOpen, MarketClose, PreOpen).
- **Règles d’accès ou d’usage** : Diffusion en mode "Publish/Subscribe" ou callback asynchrone pour ne pas bloquer l'orchestrateur. Précision milliseconde requise. Doit être auditable via le Log Service dès réception.

**ILogger**
- **Implémenté par** : `Logger Global`
- **Injecté dans / Utilisé par** : `Tous les managers`
- **Responsabilité opérationnelle** : Journalisation des logs techniques, opérationnels et audit.
- **Règles d’accès ou d’usage** : Mode synchrone pour bootstrapping et erreurs fatales. Mode non-bloquant en runtime. Les PoolWorkers ne loguent jamais directement.

**IErrorHandler**
- **Implémenté par** : `ErrorService`
- **Injecté dans / Utilisé par** : `PM, RM, OM, System Manager`
- **Responsabilité opérationnelle** : Classification et propagation des erreurs fatales.
- **Règles d’accès ou d’usage** : Écriture seule. Appels synchrones pour erreurs critiques. Instance unique thread-safe



### TODO

* Assurer l’idempotence du MarketOpenEvent : ne déclencher l’entrée en exécution que si l’état courant est WAITING, ignorer tout événement dupliqué, retardé ou reçu hors séquence.

* En phase `WAITING`, si le Heartbeat OM échoue :
  * **LIVE** → relancer le **bootstrapping complet** (retry progressif à définir).
  * **PAPER** → ne rien bloquer par défaut ; autoriser des retries conditionnels **si le temps restant avant l’ouverture le permet**.

