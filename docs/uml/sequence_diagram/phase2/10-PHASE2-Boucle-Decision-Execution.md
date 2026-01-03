## `10-PHASE2-Boucle-Decision-Execution`

<p align="center">
  <img src="../img/10-PHASE2-Boucle-Decision-Execution.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'orchestrer la **réaction décisionnelle** du système suite à la stabilisation des données de marché. Il assure le passage de la donnée brute à l'action (ordres d'urgence ou stratégiques) en garantissant que le **Risk Monitor** et le **Portfolio Manager** travaillent sur un référentiel temporel et technique identique via un objet de contexte partagé.

---

### 2. Contexte

Ce module constitue le cœur de la **logique métier** en Phase II. Il est strictement "Consumer-side" et exploite les données stabilisées par la *Fast-Lane*. Il utilise le **Historic Live Hub (LHB)** comme source principale pour l'inférence des modèles de Machine Learning et le **DataCache** pour les vérifications de prix instantanés.

---

### 3. Logique Générale

Le flux est piloté par un événement de synchronisation enrichi :

* **Déclenchement** : L'**EventBus** diffuse le signal `notifyDataReady(Context)` dès que le cycle d'ingestion est clôturé dans le Cache et le LHB.
* **Orchestration par Contexte** : Le signal transporte un objet `MarketStateContext` immuable contenant l'index du slot LHB et les références aux quotes du cache.
* **Exécution Parallèle (Fragment `par`)** :
  * Le **Risk Monitor (10a)** effectue une lecture du contexte pour valider les limites d'exposition et exécuter son modèle ML de surveillance.
  * Le **Portfolio Manager (10b)** utilise l'index du contexte pour extraire les *features* du LHB et évaluer ses signaux stratégiques via ML.
* **Découplage de l'Exécution** : Les ordres sont poussés de manière asynchrone dans une `OrderInputQueue` prioritaire.
* **Traitement Séquentiel** : L'**Order Manager** consomme la queue en continu pour router les ordres vers le broker.

---

### 4. Règles Critiques

* **Sémantique "Context-Locked"** : Les managers RM et PM ont l'interdiction de solliciter des données hors de la portée définie par le `MarketStateContext` reçu pour garantir la cohérence des signaux.
* **Priorité de la Queue** : La `OrderInputQueue` doit traiter les ordres `CRITICAL` (issus du RM) avec une priorité absolue sur les ordres `STANDARD` (issus du PM).
* **Non-Blocage du Bus** : La diffusion du signal est asynchrone ; le traitement des modèles ML ne doit jamais ralentir la réception du prochain tick par l'EventBus.
* **Isolation ML** : Le LHB garantit l'immuabilité des séries temporelles pendant que les modèles effectuent leur inférence.

---

### 5. Conclusion

Cette architecture garantit une **cohérence temporelle absolue** entre la surveillance et la stratégie grâce au `MarketStateContext`. En synchronisant l'accès au cache atomique et aux séries temporelles du buffer LHB, le système permet une **inférence ML déterministe** sans aucune latence de recherche. Le découplage par file d'attente prioritaire assure que les décisions critiques du Risk Monitor sont exécutées instantanément, offrant une scalabilité robuste et une sécurité maximale en haute fréquence.

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

### IOrderManagerControl
* **Implémenté par** : `OrderManager`
* **Injecté dans / Utilisé par** : Interne au cycle d'exécution
* **Responsabilité opérationnelle** : Consommer séquentiellement les ordres présents dans la file d'attente via `dequeueOrder()`.
* **Règles d’accès ou d’usage** : Traitement ordonné selon la priorité définie lors de l'enfilage. Assure la transition vers l'exécution marché (Broker Gateway).

