## `10a-PHASE2-Surveillance-Urgence`

<p align="center">
<img src="../img/10a-PHASE2-Surveillance-Urgence.jpg" width="900">
</p>

### 1. Objectif

Ce module a pour finalité de garantir la **détection immédiate et l'exécution prioritaire** d'ordres d'urgence (type Stop-Loss ou Kill-Switch) suite à une violation des seuils de risque, assurant ainsi la sécurité et la résilience financière de la session de trading.

---

### 2. Contexte

Ce processus s'inscrit au cœur de la **Phase II (In-Trade)**, opérant en continu dès l'ouverture du marché. Il est déclenché par la réception asynchrone d'un nouvel instantané de prix cohérent (`SnapshotHeader`) provenant du `LiveDataHub`. Il utilise un **thread de haute priorité persistant** pour minimiser la latence entre la réception des prix et la prise de décision critique.

---


### 3. Logique Générale

La surveillance s'exécute dans une boucle continue (tant que le marché est ouvert). Suite à la réception d'une nouvelle cotation :

1.  Le `RiskMonitor` lit l'état actuel de la position auprès du `PortfolioManager` pour garantir la cohérence des données.
2.  Il compare cet état avec les seuils de risque configurés (`checkThresholds`).
3.  En cas de dépassement critique, l'ordre d'urgence est créé et la procédure d'arrêt est initiée.
4.  L'ordre est soumis à l'`OrderManager` via la `PriorityQueue` pour garantir une prise en charge immédiate.
5.  Le processus se termine une fois l'ordre sécurisé dans le système d'exécution.

---


### 4. Règles Critiques

* **Audit Synchrone :** L'enregistrement de l'incident (`logCriticalEvent(OrderEvent)`) est **obligatoirement synchrone** et doit être achevé avant toute soumission d'ordre. Le thread de surveillance se bloque pour garantir que la trace d'audit est écrite physiquement.
* **Priorité Absolue :** L'objet `RequestOrder` soumis à l'`OrderManager` doit impérativement porter le tag **`Priority: CRITICAL`** pour garantir son routage et son traitement avant tous les ordres de stratégie standard.
* **Non-Perte de Données :** L'appel du `RiskMonitor` à l'`OrderManager` est **synchrone** jusqu'à la confirmation de l'enfilement (`enqueue(OrderRequest)`) dans la `PriorityQueue`. Le thread de haute priorité du Risk Monitor ne se libère que lorsque l'ordre est sécurisé dans la file d'attente de l'OM.
* **Cohérence de Données :** La lecture de la position auprès du `PortfolioManager` est synchrone pour garantir que le calcul de risque est basé sur l'état le plus récent du portefeuille.

---


### 5. Conclusion

Le module `10a-PHASE2-Surveillance-Urgence` est le **mécanisme de protection* du système de trading. Il garantit que les défaillances de risque sont gérées avec une latence minimale, une priorité maximale, et une **auditabilité stricte** de la décision et de l'action, sans jamais dépendre du flux des ordres de trading normaux.
