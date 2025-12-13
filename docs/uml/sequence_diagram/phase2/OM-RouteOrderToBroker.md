## `OM-RouteOrderToBroker`

<p align="center">
  <img src="../img/OM-RouteOrderToBroker.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce processus est de garantir la **transmission physique et priorisée** des ordres de trading à la plateforme du courtier (`IBKR Gateway`), en s'assurant que l'ordre le plus urgent est traité avant les autres, et ce, sans bloquer les autres opérations critiques.

---


### 2. Contexte

Cette séquence est un processus asynchrone interne au module **`OrderManager`** et est référencée immédiatement après l'insertion sécurisée d'un ordre dans la `PriorityQueue` (étapes 14 de la séquence `10a` et 12 de la séquence `10b`). Elle représente la prise de relais du **"Dequeue Processor"** de l'OM pour l'exécution réelle. Le processus s'inscrit dans l'architecture I/O, utilisant les pools de threads dédiés pour isoler l'activité de communication externe.

---


### 3. Logique Générale

Un thread de fond au sein de l'`OrderManager` (le Dequeue Processor) surveille en permanence la **`PriorityQueue`**. Dès qu'un ordre y est présent, il l'extrait (`dequeue`), garantissant ainsi que l'ordre avec la priorité la plus élevée est traité en premier. L'OM formatte ensuite l'ordre pour la passerelle et le soumet au **`JobManager`** en spécifiant le niveau d'I/O requis (Critique ou Standard). Le `JobManager` alloue la ressource via le `ThreadManager`, et l'ordre est transmis par l'`IBKR Gateway` au courtier. Une fois la transmission confirmée par la passerelle, l'ordre prend un statut intermédiaire (`SUBMITTED` ou `SENT`) dans le système, et le processeur revient immédiatement à l'attente du prochain ordre dans la queue.

---


### 4. Règles Critiques

* **Priorité d'Exécution :** La `PriorityQueue` assure la discipline. Les ordres `CRITICAL` (Stop-Loss, urgence) sont toujours retirés et routés avant les ordres `STANDARD` (stratégie) ou tout autre ordre.
* **Isolation I/O :** La tâche de transmission est soumise au `JobManager` pour utiliser un **Pool I/O dédié**. Les ordres critiques doivent être exécutés via le **`Pool I/O Critical`** pour éviter d'être ralentis par des écritures I/O lourdes (comme le *Bulk I/O* des données de marché).
* **Statut de l'Ordre :** Lors de l'extraction de la queue, l'état interne de l'ordre passe de `PENDING_QUEUE` à un état de transaction, puis à **`SENT`** ou **`SUBMITTED`** dès la confirmation de la passerelle. L'état final (`FILLED` ou `CANCELED`) est géré par la séquence `11-PHASE2-Traitement-Fill` ou une séquence d'annulation séparée.
* **Processus Asynchrone :** L'intégralité du routage (après l'extraction) est un processus de fond (asynchrone). Il ne doit jamais bloquer la logique du `RiskMonitor` ou du `PortfolioManager`, qui ne font que soumettre l'ordre et non le suivre.

---


### 5. Conclusion

Le module **`OM-RouteOrderToBroker`** est le moteur d'exécution physique du système, opérant en coulisse pour transformer les décisions de trading en actions concrètes sur le marché. Il garantit que le strict respect de la priorité établie par la `PriorityQueue` est maintenu jusqu'à la dernière étape de la communication externe, assurant ainsi l'exécution ultra-rapide des ordres d'urgence.
