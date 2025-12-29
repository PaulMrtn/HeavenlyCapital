## `10a-PHASE2-Surveillance-Urgence`

<p align="center">
<img src="../img/10a-PHASE2-Surveillance-Urgence.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de garantir la **détection immédiate** d'une violation critique des limites de risque et de déclencher l'exécution d'un ordre de liquidation (Stop-Loss ou Kill-Switch) avec une **priorité maximale absolue**, préservant ainsi le capital.

---

### 2. Contexte

Ce processus s'inscrit dans la **Phase II (In-Trade)** et est piloté par le **`RiskMonitor`**, un composant fonctionnant sur un thread de haute priorité dédié. Il est déclenché de manière asynchrone par l'événement **`notifySnapshotReady`** émis par le `LiveDataHub`, assurant que la surveillance s'effectue sur des données de prix complètes et cohérentes, à une fréquence régulière et critique (par exemple, toutes les minutes).

---

### 3. Logique Générale

Le `RiskMonitor` fonctionne en boucle continue. À chaque signal `SnapshotReady`, il initie un double processus de récupération synchrone (Fetch) : il lit le prix dans le **`DataCache`** et l'état de la position auprès du **`PortfolioManager`**. Muni de ces deux données, il procède à l'évaluation des seuils (`checkThresholds`). Si un seuil est franchi, il crée un ordre d'urgence, journalise l'incident de manière bloquante, puis soumet cet ordre à l'`OrderManager` avec une priorité **`CRITICAL`**. L'ordre est ensuite sécurisé dans la `PriorityQueue` de l'OM avant d'être routé pour l'exécution physique.

---

### 4. Règles Critiques

* **Déclenchement et Découplage :** Le `RiskMonitor` est entièrement découplé de la logique de trading standard. Il ne dépend que des sources de données passives (caches) et du `PortfolioManager` pour son état, et agit uniquement sur le signal cohérent du `Snapshot`.
* **Audit Synchrone :** L'enregistrement de l'incident (`logCriticalEvent`) est **obligatoirement synchrone et bloquant** (étape 9). Le `RiskMonitor` doit attendre la confirmation de l'écriture de la preuve d'audit avant de procéder à la soumission de l'ordre. C'est le prix de la conformité et de l'irréfutabilité.
* **Priorité Maximale :** L'ordre est soumis avec la priorité **`CRITICAL`**. L'`OrderManager` doit garantir que cet ordre est inséré en tête de la `PriorityQueue` et traité avant tout ordre `STANDARD` ou `NORMAL`.
* **Contrôle du Thread :** Le `RiskMonitor` utilise des appels synchrones pour l'audit et la soumission d'ordre (jusqu'à l'étape d'enfilement confirmée) afin de garantir que l'ordre est pris en charge avant que le thread ne soit libéré pour le cycle de surveillance suivant.

---

### 5. Conclusion

Le module **`10a-PHASE2-Surveillance-Urgence`** est le mécanisme de défense à haute priorité du système. Il garantit que toute violation de risque est détectée, auditée et contrée par une action immédiate (liquidation) dont la priorité d'exécution est formellement supérieure à toute autre opération de trading en cours.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|notifySnapshotReady(SnapshotHeader)|Live Data Hub|Risk Monitor|Notification asynchrone indiquant qu'un nouveau bloc de données de marché cohérent est disponible pour analyse.|
|2|getRequiredQuotes(SnapshotHeader)|Risk Monitor|Data Cache|Requête synchrone pour extraire les prix spécifiques nécessaires au calcul de l'exposition au risque.|
|3|Return: RequiredQuotes|Data Cache|Risk Monitor|Retour des données de cotation demandées.|
|4|readCurrentPositionState()|Risk Monitor|Portfolio Manager|Appel pour obtenir l'état actuel des positions ouvertes (quantité, prix d'entrée, etc.).|
|5|<<return>> PositionState|Portfolio Manager|Risk Monitor|Retour de l'état consolidé du portefeuille.|
|6|checkThresholds(PositionState, SnapshotHeader)|Risk Monitor|Risk Monitor|Auto-évaluation comparant l'état du portefeuille aux limites de risque définies (ex: Stop-Loss).|
|7|createEmergencyOrder(PositionState)|Risk Monitor|Risk Monitor|Génération interne d'un ordre de liquidation automatique si un seuil de risque est franchi.|
|8|logCriticalEvent(OrderEvent)|Risk Monitor|Log Service|Enregistrement synchrone et bloquant de l'incident pour garantir l'auditabilité avant l'exécution.|
|9|submitEmergencyOrder(RequestOrder, Priority: CRITICAL)|Risk Monitor|Order Manager|Soumission de l'ordre d'urgence avec le niveau de priorité le plus élevé du système.|
|10|enqueue(OrderRequest)|Order Manager|PriorityQueue|Insertion physique de l'ordre en tête de la file d'attente prioritaire.|
|11|Return: EnqueueConfirmed|PriorityQueue|Order Manager|Confirmation que l'ordre est sécurisé dans la file d'attente.|
|12|Return: OrderSubmitted|Order Manager|Risk Monitor|Confirmation finale de la prise en charge de l'ordre d'urgence.|
|ref|(OM-RouteOrderToBroker)|Order Manager|Externe|Référence à la séquence de routage de l'ordre vers le courtier pour exécution physique.|
