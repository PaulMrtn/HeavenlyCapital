## `08-PHASE2-Transition-Mode-Veille`

<p align="center">
  <img src="../img/08-PHASE1-Transition-Mode-Veille.jpg" width="900">
</p>

--- 

### 1. Objectif

La finalité de ce module est de faire passer le système de l'état d'initialisation réussie à l'état de **veille sécurisée et active** (`WAITING`). Il assure la maintenance de l'intégrité technique jusqu'au déclenchement de l'ouverture du marché.

---

### 2. Contexte

Cette séquence marque la clôture de la **Phase 1 (Bootstrapping)**. Après validation de la Phase 07, le système entre en attente passive mais vigilante. Sa mission est de garantir que la "Fast-Lane" de données et le tunnel d'exécution restent opérationnels malgré les micro-coupures réseau ou les latences d'indexation courantes durant le pré-marché.

---

### 3. Logique Générale

Le **`System Manager (SM)`** bascule l'état global du système vers **`READY_FOR_TRADING`**, confirmant la fin de la phase de préparation initiale. Le système initie alors une attente asynchrone (`Wait for MarketOpenEvent()`), durant laquelle une double boucle de surveillance (Heartbeat) est maintenue selon une logique de **Patience Temporelle** :

* **Surveillance Analytique (LHB) :** Le SM interroge périodiquement le `Historic Live Hub` pour valider l'intégrité de l'indexation des données de pré-marché. Cette vérification garantit que le mécanisme de **Double Buffering** est fluide, que les données ne sont pas figées ("Stale Data") et que les vecteurs sont prêts pour l'inférence ML immédiate.
* **Surveillance de l'Exécution (OM) :** L'`Order Manager` teste activement la réactivité du tunnel avec la `IBKR Gateway` pour assurer la capacité d'émission d'ordres dès l'ouverture.
* **Gestion de la Résilience :** Le système est conçu pour tolérer les instabilités éphémères (micro-coupures réseau ou latences d'indexation). En cas d'échec d'un Heartbeat, le SM bascule en statut `WARNING`. Ce n'est qu'en cas de persistance de l'anomalie au-delà du seuil **`HEARTBEAT_TOLERANCE_MS`** que la procédure de réinitialisation complète (**`Emergency_Standby_Reset`**) est invoquée.

Le mode veille se termine dès la réception du signal **`MarketOpenEvent()`** émis par le `Market Clock`. Le SM enregistre alors l'événement pour audit et bascule immédiatement vers la **Phase 2 (In-Trade)**, à condition que l'intégrité technique soit confirmée.

---

### 4. Règles Critiques

* **Point de Non-Retour :** La mise à jour du statut vers **`READY_FOR_TRADING`** confirme que tous les contrôles de sécurité (LIVE vs PAPER) et d'intégrité technique ont été validés avec succès.
* **Surveillance Obligatoire et Temporelle :** La double boucle de Heartbeat (LHB et OM) doit être maintenue en continu. Le système n'exécute plus d'arrêt brutal au premier échec, mais observe une **période de tolérance** avant de déclencher une action corrective.
* **Priorité à l'Intégrité (LHB) :** En cas d'anomalies simultanées, la santé du `Historic Live Hub` est prioritaire sur la connectivité. Des données figées ("Stale Data") ou un buffer corrompu bloquent impérativement toute transition vers l'exécution.
* **Sécurité Technique vs Opportunité :** Si le `MarketOpenEvent()` survient pendant qu'un Heartbeat est en échec (en période de tolérance ou durant un Reset), l'entrée en exécution est bloquée. La sécurité de l'infrastructure prime sur le timing du marché.
* **Dilemme de l'Ouverture :** Si le marché ouvre alors que le système est en état d'alerte (Warning), le mode "patience" est abandonné au profit d'un déclenchement instantané du `Emergency_Standby_Reset()`.
* **Protection Passive (Broker-Side) :** La sécurité financière absolue repose sur l'usage systématique de **Bracket Orders**. En cas de redémarrage complet du système à l'ouverture, les positions existantes restent protégées par les Stop-Loss stockés de manière autonome sur les serveurs du courtier.
* **Déclenchement Auditable et Temporel :** Le seul événement mettant fin à la veille est le signal asynchrone du **`Market Clock`**. Sa réception doit être immédiatement enregistrée via un log critique pour garantir la traçabilité de la session.
* **Règle de Rattrapage :** Si le processus de Reset se termine après l'heure officielle d'ouverture, le `System Manager` vérifie l'historique des signaux et lance l'exécution en mode sécurisé avec la mention "Late Market Entry" dans l'audit trail.

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

* **Paramétrage :** Définir `HEARTBEAT_TOLERANCE_MS` (recommandé : 15s à 30s) pour filtrer les micro-coupures de l'API IBKR.
* **Séquence :** Finaliser la définition technique de `Emergency_Standby_Reset()` (Purge buffers LHB + Re-Bootstrap Phase 1).
* **Validation :** Implémenter l'idempotence du `MarketOpenEvent` pour ignorer les signaux reçus hors séquence ou durant un Reset.


