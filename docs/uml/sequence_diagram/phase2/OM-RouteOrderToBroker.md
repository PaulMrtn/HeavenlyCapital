## `OM-RouteOrderToBroker`

<p align="center">
  <img src="../img/OM-RouteOrderToBroker.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce processus est de garantir la **transmission physique et priorisée** des ordres de trading à la plateforme du courtier (`IBKR Gateway`), en appliquant une **politique de priorité globale** (Live avant Paper) et en utilisant les ressources I/O appropriées.

---

### 2. Contexte

Cette séquence est un processus asynchrone interne au module **`OrderManager`** et est déclenchée après l'insertion sécurisée d'un ordre dans la `PriorityQueue` locale. Elle représente l'exécution du routage et de la communication externe, gérée par le **Dequeue Processor** de l'OM. L'introduction du **`Global Order Router` (GOR)** dans cette séquence est nécessaire pour arbitrer les conflits de priorité entre les différentes sessions (Live vs. Paper) avant d'allouer des ressources I/O.

---

### 3. Logique Générale

Un thread de fond (le Dequeue Processor) dans l'`OrderManager` surveille la `PriorityQueue` locale et en extrait l'ordre de plus haute priorité **locale**. L'ordre, ainsi que son **Type de Session** (Live ou Paper), est ensuite soumis au **`Global Order Router` (GOR)**. Le GOR utilise cette priorité réévaluée pour solliciter le **`JobManager`** et le **`ThreadManager`**, garantissant que l'ordre est transmis par l'`IBKR Gateway` en utilisant le **Pool I/O** le plus adapté à sa priorité finale. L'état de l'ordre passe alors à `SUBMITTED` dès la confirmation de la passerelle.

---

### 4. Règles Critiques

* **Priorité d'Arbitrage :** La règle de super-priorité du GOR doit être respectée de manière absolue : tous les ordres d'une session Live doivent être routés avant tous les ordres de même priorité logique d'une session Paper.
* **Isolation I/O :** Le `JobManager` doit allouer la tâche à un **Pool I/O dédié** (Pool I/O Critical ou autre) en fonction de la priorité finale décidée par le GOR. Cela isole les communications rapides des opérations de fond.
* **Statut de l'Ordre :** L'état de l'ordre passe de `PENDING_QUEUE` à un état de transmission (`SUBMITTED`) uniquement après que l'`IBKR Gateway` ait confirmé que l'ordre a quitté le système.
* **Asynchronisme :** L'intégralité du routage est un processus asynchrone qui ne doit jamais bloquer les threads de décision (PM ou RM). L'exécution du routage est pilotée par le thread de fond du Dequeue Processor.

---

### 5. Conclusion

Le module garantit l'exécution des ordres dans le respect strict des priorités logiques et architecturales. Il s'assure que les ordres sont non seulement priorisés au niveau de la session locale, mais aussi correctement arbitrés au niveau global pour favoriser les cycles de test sans compromettre l'urgence des ordres réels.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | dequeue() | OM Dequeue Processor | PriorityQueue | Extrait l'ordre ayant la priorité locale la plus élevée de la file d'attente interne. |
| 2 | HighestPriorityOrder | PriorityQueue | OM Dequeue Processor | Retourne l'objet Order sélectionné au processeur pour traitement. |
| 3 | formatOrder(Order, SessionType) | OM Dequeue Processor | OM Dequeue Processor | Prépare les données de l'ordre et injecte le contexte de session (Live/Paper). |
| 4 | submitOrderForArbitration(FormattedOrder) | OM Dequeue Processor | GlobalOrderRouter | Transmet l'ordre au routeur global pour arbitrage des priorités inter-sessions. |
| 5 | calculateFinalIOPriority(Order, SessionType) | GlobalOrderRouter | GlobalOrderRouter | Applique la règle de super-priorité : les sessions Live priment sur le Paper. |
| 6 | submitExecutionJob(Order, FinalPoolHint) | GlobalOrderRouter | JobManager | Soumet une tâche d'exécution asynchrone avec une directive de pool spécifique. |
| 7 | delegateExecution(Order, Pool) | JobManager | ThreadManager | Alloue le job au Pool I/O (Critical ou Standard) selon la priorité arbitrée. |
| 8 | transmitOrder(Order) | ThreadManager | IBKR Gateway | Exécute la transmission physique de l'ordre vers l'API du courtier. |
| 9 | orderSentConfirmation(OrderID) | IBKR Gateway | OM Dequeue Processor | Confirme que l'ordre a quitté le système, déclenchant le passage au statut SUBMITTED. |
