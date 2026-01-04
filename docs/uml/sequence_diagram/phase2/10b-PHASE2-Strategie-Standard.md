## `10b-PHASE2-Strategie-Standard`

<p align="center">
  <img src="../img/10b-PHASE2-Strategie-Standard.jpg" width="900">
</p>

---

### 1. Objectif

L'objectif de cette séquence est d'exécuter de manière optimisée les ordres de trading standards **planifiés**. Ces ordres sont générés lors de la **Phase 4 (Strategy Update)** de la session précédente et chargés en mémoire vive lors du bootstrapping en **Phase 1**. Le module sélectionne le moment optimal (*timing*) pour la soumission à l'exécution en se basant sur l'analyse des séries temporelles intraday.

---

### 2. Contexte

Ce processus constitue le cœur de la **boucle de décision In-Trade** pilotée par le **`PortfolioManager`**. Il s'agit d'une exécution tactique déclenchée par l'événement **`notifyDataReady`** provenant de l'**`EventBus`**. Ce signal indique que le **Historic Live Hub (LHB)** a stabilisé un nouveau snapshot de marché, permettant une analyse cohérente sans interférer avec le flux d'acquisition ultra-rapide.

---

### 3. Logique Générale

Le `PortfolioManager` fonctionne en mode "Pull" réactif pour garantir l'isolation des ressources :

1. **Réception du Signal** : Le PM est réveillé par l'**EventBus** avec le contexte du dernier snapshot.
2. **Mise à jour et Extraction** : Le PM sollicite le **LHB** via `getRawBufferSlice()` pour obtenir un vecteur immuable de prix historiques (). Il met à jour ses indicateurs internes avec ces données.
3. **Analyse de Timing** : Un algorithme de décision (ex: VWAP, ML) évalue si le prix actuel est favorable par rapport à l'objectif de l'ordre planifié.
4. **Récupération de l'Ordre** : Si la condition est optimale, le PM extrait l'ordre correspondant (chargé initialement en Phase 1).
5. **Audit et Envoi** : Le PM journalise sa décision de manière synchrone avant de soumettre l'ordre à l'**`OrderManager`** avec une priorité **`STANDARD`**.

---

### 4. Règles Critiques

* **Origine des Ordres** : Les intentions de trading sont générées en **Phase 4 (J-1)** et uniquement **chargées** depuis la base de données en **Phase 1 (J)**. Le PM en Phase 2 ne crée pas d'intention, il gère uniquement la tactique d'exécution.
* **Isolation par Double Buffering** : Le PM lit exclusivement dans le buffer "gelé" du **LHB**, assurant une lecture **Lock-Free**. Cela garantit que l'analyse tactique ne ralentit jamais l'ingestion des nouveaux ticks (Fast-Lane).
* **Priorité Relative** : Tout ordre issu de cette séquence porte le flag **`STANDARD`**. L'**`OrderManager`** et la **`PriorityQueue`** garantissent que ces ordres sont traités après les ordres de priorité `CRITICAL` (Urgence/Risque).
* **Audit Synchrone** : L'appel `logExecutionDecision` doit être complété avant la soumission physique de l'ordre pour assurer une traçabilité parfaite entre le signal de prix et l'action engagée.

---

### 5. Conclusion

Ce module assure que les ordres de stratégie sont exécutés au moment jugé le plus favorable par les algorithmes d'optimisation. En s'appuyant sur le **LHB** et l'**EventBus**, elle garantit une efficacité transactionnelle maximale tout en respectant la hiérarchie de priorité absolue imposée par les contraintes de risque du système.

---

|ID|Fonction / Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|notifyDataReady(MarketStateContext)|EventBus|PortfolioManager|Signal asynchrone notifiant que le swap de buffer LHB est effectué et que les données sont prêtes pour analyse.|
|2|getRawBufferSlice()|PortfolioManager|Live Historic Buffer|Requête synchrone (O(1)) pour extraire une fenêtre de séries temporelles (vecteur) depuis la mémoire gelée.|
|3|TimeSeriesVector|Live Historic Buffer|PortfolioManager|Retour immuable des données historiques nécessaires aux calculs des modèles de timing (ex: VWAP, ML).|
|4|checkTimingOpportunity()|PortfolioManager|PortfolioManager|Auto-évaluation (modèle tactique) déterminant si le prix actuel et la tendance valident une entrée immédiate.|
|5|fetchNextPendingOrder(TimingParameters)|PortfolioManager|PortfolioManager|Récupération de l'ordre planifié issu du rééquilibrage de Phase 1 une fois le signal de timing validé.|
|6|logExecutionDecision(OrderEvent)|PortfolioManager|Log Session|Enregistrement synchrone et bloquant de la justification du timing (prix/contexte) pour l'audit de performance.|
|7|submitNewOrder(RequestOrder, Priority: STANDARD)|PortfolioManager|OrderManager|Soumission de l'ordre de stratégie à l'exécuteur avec un niveau de priorité normal (Standard).|
|8|enqueue(OrderRequest)|OrderManager|PriorityQueue|Placement de l'ordre dans la file d'attente prioritaire pour séquençage physique vers le broker.|
|9|Return: EnqueueConfirmed|PriorityQueue|OrderManager|Confirmation technique que l'ordre est bien enregistré dans la file d'attente système.|
|10|Return: OrderSubmitted|OrderManager|PortfolioManager|Accusé de réception final confirmant la prise en charge de l'ordre par la couche d'exécution.|
|ref|(OM-RouteOrderToBroker)|OrderManager|Externe|Fragment de référence indiquant la transmission effective du message FIX/API vers la gateway du courtier.|

---

### 6. Ports et Interfaces

**IEventBusPort**
* **Implémenté par** : `EventBus Global`
* **Injecté dans / Utilisé par** : `Portfolio Manager` (Abonné)
* **Responsabilité opérationnelle** : Notification asynchrone notifiant que le swap de buffer du LHB est effectué et qu'un nouveau snapshot cohérent est prêt pour analyse.
* **Règles d’accès ou d’usage** : Diffusion asynchrone ultra-légère contenant uniquement l'index (ID) du slot mémoire stabilisé.

**ILiveDataReader**
* **Implémenté par** : `Historic Live Hub (LHB)`
* **Injecté dans / Utilisé par** : `Portfolio Manager`
* **Responsabilité opérationnelle** : Fournir un accès en lecture seule aux séries temporelles (Time-Series) de la session en cours via une indexation linéaire absolue.
* **Règles d’accès ou d’usage** : Extraction synchrone en . Utilisation obligatoire du mécanisme de **Double Buffering** pour garantir une isolation totale vis-à-vis de l'ingestion Fast-Lane.

**IExecutionDecisionModel**
* **Implémenté par** : Modèles tactiques chargés (VWAP, TWAP, ML, Baseline)
* **Injecté dans / Utilisé par** : `Portfolio Manager`
* **Responsabilité opérationnelle** : Oracle de décision déterminant si le prix actuel et le contexte historique permettent l'exécution d'un ordre planifié.
* **Règles d’accès ou d’usage** : Modèle strictement déterministe et **stateless**. Aucun effet de bord ni accès I/O autorisé lors de l'appel.

**ILogger**
* **Implémenté par** : `Logger Global`
* **Injecté dans / Utilisé par** : `Portfolio Manager`
* **Responsabilité opérationnelle** : Journalisation des décisions tactiques (`logExecutionDecision`) incluant le prix et la justification du timing.
* **Règles d’accès ou d’usage** : **Mode synchrone et bloquant** impératif avant la soumission de l'ordre pour garantir l'auditabilité de la performance d'exécution.

**IOrderInputQueuePort**
* **Implémenté par** : `OrderInputQueue`
* **Injecté dans / Utilisé par** : `Portfolio Manager` (Producteur)
* **Responsabilité opérationnelle** : Point de dépôt asynchrone pour les ordres générés par la logique de stratégie.
* **Règles d’accès ou d’usage** : Attribution obligatoire de la priorité **`STANDARD`**. L'ordre sera traité par l'Order Manager après les flux critiques de risque.
