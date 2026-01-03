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
|1|notifyDataReady(Context)|EventBus|Risk Monitor|Notification asynchrone transmettant le contexte immuable (références Cache + index LHB) pour déclencher l'inférence ML de surveillance.|
|2|notifyDataReady(Context)|EventBus|Portfolio Manager|Notification asynchrone simultanée transmettant le même contexte pour déclencher l'inférence ML de stratégie.|
|ref|10a-PHASE2-Surveillance-Urgence|Risk Monitor|N/A|Fragment de référence : Exécution de la logique de risque (calcul d'exposition et détection d'anomalies ML).|
|ref|10b-PHASE2-Strategie-Standard|Portfolio Manager|N/A|Fragment de référence : Exécution de la logique tactique (signaux d'entrée/sortie et timing ML).|
|3|enqueueOrder(Order,Priority)|Risk Monitor|OrderInputQueue|Enfilage asynchrone d'un ordre d'urgence avec priorité 'CRITICAL' suite à une violation de limite.|
|4|enqueueOrder(Order,Priority)|Portfolio Manager|OrderInputQueue|Enfilage asynchrone d'un ordre stratégique avec priorité 'STANDARD' suite à un signal valide.|
|5|dequeueOrder()|Order Manager|OrderInputQueue|Appel synchrone (Pull) pour extraire et traiter l'ordre le plus prioritaire de la file d'attente pour exécution broker.|
---


### 6. Ports et Interfaces

### IMarketDataCacheReader
* **Implémenté par** : `DataCache`
* **Injecté dans / Utilisé par** : `RiskMonitor`, `PortfolioManager`
* **Responsabilité opérationnelle** : Fournir un accès en lecture seule, non bloquant et ultra-rapide aux derniers `MarketQuotes` (cotations agrégées) en RAM.
* **Règles d’accès ou d’usage** : Lecture *lock-free* utilisant l'*Atomic Versioning*. Usage exclusif d’objets immuables pour garantir qu'aucune modification n'est possible par les consommateurs. Ne doit jamais bloquer la *Fast-Lane*.

### IEventBusPort 
* **Implémenté par** : `EventBus` (Infrastructure technique)
* **Injecté dans / Utilisé par** : `DataCache` (Émetteur), `RiskMonitor` & `PortfolioManager` (Abonnés)
* **Responsabilité opérationnelle** : Diffuser de manière asynchrone le signal `MarketDataUpdated()` pour réveiller les modules décisionnels.
* **Règles d’accès ou d’usage** : Diffusion non-bloquante. Supporte l'exécution parallèle des abonnés. Doit respecter les priorités de scheduling (Urgence vs Stratégie).

### IOrderSubmissionPort
* **Implémenté par** : `OrderManager`
* **Injecté dans / Utilisé par** : `RiskMonitor`
* **Responsabilité opérationnelle** : Permettre la soumission immédiate d'ordres de protection ou de liquidation suite à une violation de limite.
* **Règles d’accès ou d’usage** : Exclusivité au `RiskMonitor` pour cette interface spécifique. Utilisation impérative de la priorité `CRITICAL`.

### IOrderInputQueuePort
* **Implémenté par** : `OrderInputQueue`
* **Injecté dans / Utilisé par** : `RiskMonitor`, `PortfolioManager` (Producteurs) / `OrderManager` (Consommateur)
* **Responsabilité opérationnelle** : Agir comme zone de transit (buffer) asynchrone pour découper la phase de décision de la phase d'exécution.
* **Règles d’accès ou d’usage** : Méthode `enqueueOrder(Order, Priority)` non-bloquante. Doit supporter la gestion des priorités (High pour le RM, Standard pour le PM).

### IPositionProvider
* **Implémenté par** : `PortfolioManager`
* **Injecté dans / Utilisé par** : `RiskMonitor`
* **Responsabilité opérationnelle** : Exposer l'état actuel des positions pour permettre au `RiskMonitor` de calculer l'exposition en temps réel par rapport aux nouveaux prix.
* **Règles d’accès ou d’usage** : Lecture seule. Aucun verrou bloquant. Utilisé durant le fragment `10a-Surveillance-Urgence`.

### IOrderManagerControl (Nouveau - pour message 4)
* **Implémenté par** : `OrderManager`
* **Injecté dans / Utilisé par** : Interne au cycle d'exécution
* **Responsabilité opérationnelle** : Consommer séquentiellement les ordres présents dans la file d'attente via `dequeueOrder()`.
* **Règles d’accès ou d’usage** : Traitement ordonné selon la priorité définie lors de l'enfilage. Assure la transition vers l'exécution marché (Broker Gateway).
