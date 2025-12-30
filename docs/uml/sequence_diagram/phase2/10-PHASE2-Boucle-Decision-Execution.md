## `10-PHASE2-Boucle-Decision-Execution`

<p align="center">
  <img src="../img/10-PHASE2-Boucle-Decision-Execution.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de déclencher la **réaction décisionnelle** suite à la mise à jour des données de marché. Il assure le passage de la donnée brute stockée en mémoire (`DataCache`) à l'action (ordres d'urgence ou de stratégie). L'objectif est de garantir que le **Risk Monitor** et le **Portfolio Manager** réagissent de manière asynchrone et parallèle dès qu'une nouvelle agrégation est disponible.

---

### 2. Contexte

Ce module constitue le point d'entrée de la **logique métier** en Phase II. Contrairement à la Phase 09 (I/O pure), la séquence 10 ne gère pas la donnée mais son **exploitation**. Elle est strictement "Consumer-side". Elle traite le `DataCache` comme une source *Latest-only* et ne dépend d'aucun mécanisme de persistance ou d'audit lent.

---

### 3. Logique Générale

Le flux est piloté par un événement de notification léger :

  * **Déclenchement :** Le `DataCache` émet un signal `onMarketDataAggregated` dès qu'un lot de cotations a été rafraîchi par la Fast-Lane.
  * **Orchestration Technique :** Un `EventBus` technique diffuse l’événement de mise à jour des cotations. RM et PM sont abonnés et déclenchent leur traitement de manière asynchrone.
  * **Exécution Parallèle :**
    * * Le **RM** effectue une lecture opportuniste du cache pour valider les limites d'exposition (Urgence).
    * Le **PM** effectue une lecture pour évaluer ses signaux d'entrée (Stratégie).
  * **Cohérence à la Lecture :** La cohérence des données est assurée par le consommateur au moment de l'accès au cache, garantissant l'utilisation de la valeur la plus proche de l'instant du réveil du consommateur.
  * **Sortie :** Les ordres générés sont poussés dans une `OrderInputQueue` prioritaire, découplant la décision de l'exécution finale par l' `Order Manager`.

---

### 4. Règles Critiques

* **Sémantique "Latest-only" :** Le RM et le PM lisent la version la plus récente disponible dans le cache au moment de leur réveil.
* **Non-Blocage** : l’`EventBus` diffuse l’événement de façon asynchrone. RM et PM lisent le cache au moment où ils sont réveillés par l’événement.
* **Priorité de la Surveillance :** Bien que lancés en parallèle, la logique de surveillance d'urgence (`10a`) est conçue pour avoir une priorité de scheduling supérieure au niveau de l'OS/Runtime par rapport à la stratégie standard (`10b`).
* **Indépendance de l'Audit :** La décision n'attend jamais la création d'un `SnapshotHeader` ou une écriture disque. Si un retard survient dans la Slow-Lane (audit), la boucle décisionnelle continue sans impact.
* **Découplage de l'Exécution :** L'envoi vers l' `OrderInputQueue` est non-bloquant.

---

### 5. Conclusion

Ce module garantit une **réactivité événementielle immédiate** du système face aux mouvements du marché. En utilisant une notification légère de disponibilité, il assure que les modules décisionnels travaillent toujours sur la donnée la plus fraîche en mémoire. Cette architecture élimine les goulots d'étranglement, garantit une isolation totale entre la surveillance et la stratégie, et permet une scalabilité fluide sans compromis sur la latence.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|MarketDataUpdated()|DataCache|EventBus|Notification asynchrone signalant qu'un nouvel agrégat de cotations (MarketQuote) est disponible en RAM.|
|ref|10a-PHASE2-Surveillance-Urgence|RiskMonitor|N/A|Fragment de référence déclenché par l'EventBus : lecture PULL du cache et calcul des risques.|
|ref|10b-PHASE2-Strategie-Standard|PortfolioManager|N/A|Fragment de référence déclenché par l'EventBus : lecture PULL du cache et évaluation des signaux.|
|2|enqueueOrder(Order,Priority)|RiskMonitor|OrderInputQueue|Dépôt d'un ordre de protection avec priorité haute dans la file d'attente asynchrone.|
|3|enqueueOrder(Order,Priority)|PortfolioManager|OrderInputQueue|Dépôt d'un ordre stratégique avec priorité standard dans la file d'attente asynchrone.|
|4|dequeueOrder()|OrderManager|OrderInputQueue|Extraction et traitement séquentiel des ordres par le gestionnaire pour exécution marché.|

---


### 6. Ports et Interfaces

### IMarketDataEventPort

* **Implémenté par** : `EventBus`
* **Injecté dans / Utilisé par** : `DataCache` (émetteur), `RiskMonitor`, `PortfolioManager` (souscripteurs)
* **Responsabilité opérationnelle** : Diffusion asynchrone et non-bloquante du signal de disponibilité d'un nouvel agrégat de prix (`MarketQuote`).
* **Règles d’accès ou d’usage** :
* Diffusion de type "Fire-and-Forget".
* Interdiction de transporter des payloads lourds ; l'événement contient uniquement le trigger de réveil.
* Garantie de livraison aux abonnés enregistrés sans blocage du thread producteur.


### IOrderInputPort

* **Implémenté par** : `OrderInputQueue`
* **Injecté dans / Utilisé par** : `RiskMonitor`, `PortfolioManager`
* **Responsabilité opérationnelle** : Point d'entrée unique pour la soumission d'ordres issus de la logique décisionnelle.
* **Règles d’accès ou d’usage** :
* Accès strictement non-bloquant via `enqueueOrder(Order, Priority)`.
* Priorité `CRITICAL` réservée exclusivement au `RiskMonitor`.
* Priorité `STANDARD` allouée au `PortfolioManager`.
* Découplage total entre l'instant de décision et l'instant d'exécution technique.


### IOrderManagementPort

* **Implémenté par** : `OrderManager`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Pilotage du cycle de vie de l'exécution des ordres et interface avec les files d'attente système.
* **Règles d’accès ou d’usage** :
* Lecture séquentielle de la file via `dequeueOrder()`.
* Responsable de la transmission technique finale vers les bourses via `BrokerGatewayPort`.


### IDecisionTriggerPort

* **Implémenté par** : `RiskMonitor`, `PortfolioManager`
* **Injecté dans / Utilisé par** : `ThreadManager` / `EventBus`
* **Responsabilité opérationnelle** : Interface de réveil et d'activation des moteurs métier suite à une mise à jour de marché.
* **Règles d’accès ou d’usage** :
* Invoqué exclusivement de manière asynchrone.
* Déclenche l'accès immédiat au `IMarketDataCacheReader` pour récupération des données en mode PULL.
* Cycle de vie lié à la session de trading : actif uniquement en état `READY_FOR_TRADING`.


### IMarketDataCacheReader

* **Implémenté par** : `DataCache`
* **Injecté dans / Utilisé par** : `RiskMonitor`, `PortfolioManager`
* **Responsabilité opérationnelle** : Accès lecture seule, non bloquant, aux derniers `MarketQuote` disponibles.
* **Règles d’accès ou d’usage** :
* Lecture lock-free obligatoire.
* Aucun accès aux structures de données internes du cache.
* Usage exclusif de `MarketQuotes` immuables.
* Le port garantit l'accès aux seules versions validées (Atomic Versioning).
* Ne bloque jamais la Fast-Lane.


