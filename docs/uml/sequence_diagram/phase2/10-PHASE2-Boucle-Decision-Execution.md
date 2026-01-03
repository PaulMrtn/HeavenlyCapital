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

#### **`IEventBusPort`**
* **Domaine fonctionnel** : Infrastructure & Notification
* **Implémenté par** : EventBus Global
* **Injecté dans / Utilisé par** : Thread Manager (Émetteur), Risk Monitor & Portfolio Manager (Abonnés)
* **Responsabilité opérationnelle** : Notification de type "Signal-then-Pull" déclenchant la boucle de décision.
* **Modification majeure** : La méthode de notification transporte désormais l'objet `IMarketStateContext`.
* **Signature** : `notifyDataReady(IMarketStateContext context)`.
* **Règles d’accès ou d’usage** : Diffusion (Broadcast) asynchrone pour éviter tout blocage de la Fast-Lane par un manager lent.


#### **`IOrderManagerControl`**
* **Domaine fonctionnel** : System Control & Lifecycle
* **Implémenté par** : Order Manager
* **Injecté dans / Utilisé par** : Order Manager (Auto-consommation)
* **Responsabilité opérationnelle** : Orchestrer le vidage de la file d'attente d'entrée et le routage vers le GOR (Global Order Router).
* **Modification majeure** : Intégration de la logique de dépilage prioritaire (Priority Dequeuing).
* **Méthodes clés** :
* `processNextOrder()` : Extrait l'ordre le plus prioritaire et déclenche le routage.
* **Règles d’accès ou d’usage** : Consommation séquentielle stricte pour garantir l'intégrité des ID d'ordres envoyés au broker.


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


### **`IMarketStateContext`** 
* **Implémenté par** : Infrastructure / EventBus
* **Utilisé par** : Risk Monitor, Portfolio Manager
* **Responsabilité** : Contrat de données immuable transportant le `SnapshotIndex` du LHB et la Map des `MarketQuote` du Cache.
* **Règle** : Objet éphémère, non persistant, garantissant l'atomicité temporelle des décisions.

### **`IFeatureProvider`**
* **Implémenté par** : Historic Live Hub (LHB)
* **Utilisé par** : Risk Monitor, Portfolio Manager
* **Responsabilité** : Extraction de fenêtres temporelles (vecteurs) à partir de l'index fourni par le contexte pour nourrir les modèles ML.
* **Règle** : Lecture seule, optimisée pour le calcul de tenseurs. Remplace l'ancien `ILiveDataReader`.

### **`IOrderInputQueue`** 
* **Implémenté par** : OrderInputQueue (Buffer technique)
* **Utilisé par** : Risk Monitor, Portfolio Manager (Producteurs)
* **Responsabilité** : Point de dépôt non-bloquant des intentions d'ordres.
* **Règle** : Doit supporter le marquage de priorité (`CRITICAL` vs `STANDARD`).


