## `10b-PHASE2-Strategie-Standard`

<p align="center">
  <img src="../img/10b-PHASE2-Strategie-Standard.jpg" width="900">
</p>

---

### 1. Objectif

L'objectif de cette séquence est d'exécuter de manière les ordres de trading standards **prédéterminés** (issus du rééquilibrage), en sélectionnant le moment optimal (timing) pour la soumission à l'exécution.

---

### 2. Contexte

Ce processus s'inscrit au cœur de la **boucle de décision In-Trade** et est piloté par le **`PortfolioManager`**. Contrairement à l'urgence, il s'agit d'une **exécution planifiée**. Le cycle est déclenché par l'événement régulier **`notifySnapshotReady`** du `LiveDataHub`, qui fournit au PM l'opportunité d'évaluer l'état du marché à un instant précis.

---

### 3. Logique Générale

Le `PortfolioManager` fonctionne en boucle persistante, s'activant à chaque notification de Snapshot. Il procède à un **Fetch synchrone** du prix le plus récent depuis le **`DataCache`**. Il utilise ensuite un algorithme de *timing* (ex: TWAP, VWAP) pour évaluer si ce prix est favorable par rapport à l'objectif de l'ordre précalculé, ou si le temps imparti pour l'exécution d'un lot est écoulé. Si la condition est jugée optimale, le PM récupère l'ordre correspondant, journalise sa décision d'exécution, et soumet l'ordre à l'`OrderManager`.

---

### 4. Règles Critiques

* **Déclenchement Périodique :** Le `PortfolioManager` utilise la notification du Snapshot comme un *snapshot* d'horloge régulier pour ses algorithmes de *timing*, évitant de gaspiller des ressources sur une analyse à la fréquence brute des *ticks*.
* **Priorité Standard :** L'ordre est soumis avec la priorité **`STANDARD`**. Il doit obligatoirement être inséré dans la `PriorityQueue` derrière tout ordre de priorité **`CRITICAL`**.
* **Audit Synchrone :** L'enregistrement de la décision d'exécution (`logExecutionDecision`) est **synchrone**. Le PM doit enregistrer la justification de son choix de *timing* (le prix et le moment) avant de soumettre l'ordre pour garantir l'auditabilité de la performance d'exécution.
* **Rôle d'Exécuteur :** Le `PortfolioManager` n'est pas le créateur de l'intention de trading, mais le **gestionnaire tactique de l'exécution**.

---

### 5. Conclusion

Le module garantit que les ordres de stratégie sont exécutés au moment jugé le plus favorable par les algorithmes d'optimisation, sans jamais interférer avec la priorité absolue accordée aux ordres de surveillance et d'urgence gérés par le `RiskMonitor`. Il assure l'efficacité des transactions planifiées dans le respect strict des contraintes de priorité du système.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|notifySnapshotReady(SnapshotHeader)|LiveDataHub|PortfolioManager|Signal asynchrone notifiant qu'un nouveau bloc de données de marché cohérent est disponible pour analyse tactique.|
|2|getCurrentQuote(AssetID)|PortfolioManager|DataCache|Requête synchrone pour obtenir le prix de marché actuel de l'actif concerné par la stratégie.|
|3|Return: CurrentMarketQuote|DataCache|PortfolioManager|Retour de la cotation la plus récente stockée en mémoire vive.|
|4|checkTimingOpportunity(MarketQuote)|PortfolioManager|PortfolioManager|Auto-évaluation utilisant des algorithmes (ex: TWAP/VWAP) pour déterminer si le prix actuel est optimal pour l'exécution.|
|5|fetchNextPendingOrder(TimingParameters)|PortfolioManager|PortfolioManager|Récupération interne de l'ordre planifié suivant (issu du rééquilibrage) lorsque le timing est jugé favorable.|
|6|logExecutionDecision(OrderEvent)|PortfolioManager|Log Session|Enregistrement synchrone des paramètres ayant mené à la décision d'exécution pour audit de performance.|
|7|submitNewOrder(RequestOrder, Priority: STANDARD)|PortfolioManager|OrderManager|Soumission de l'ordre à l'exécuteur avec un niveau de priorité normal (inférieur aux ordres critiques).|
|8|enqueue(OrderRequest)|OrderManager|PriorityQueue|Placement de l'ordre dans la file d'attente prioritaire pour traitement par l'infrastructure d'exécution.|
|9|Return: EnqueueConfirmed|PriorityQueue|OrderManager|Confirmation de la bonne réception et de la mise en attente de l'ordre dans la queue.|
|10|OrderSubmissionAccepted|OrderManager|PortfolioManager|Confirmation finale au gestionnaire de portefeuille que l'ordre a été pris en charge avec succès.|
|ref|(OM-RouteOrderToBroker)|OrderManager|Externe|Référence à la procédure de transmission effective de l'ordre vers le courtier externe.|
