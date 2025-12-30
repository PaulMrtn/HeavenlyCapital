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
  * **Orchestration Technique :** Le `ThreadManager` reçoit ce signal et s'assure que les threads dédiés au **Risk Monitor (RM)** et au **Portfolio Manager (PM)** sont actifs et prêts. Il ne contient aucune logique métier.
  * Non-Blocage : Le ThreadManager n'attend pas de confirmation de la part des modules RM/PM. Le signal est de type "Fire and Forget".
  * **Exécution Parallèle :**
    * * Le **RM** effectue une lecture opportuniste du cache pour valider les limites d'exposition (Urgence).
    * Le **PM** effectue une lecture pour évaluer ses signaux d'entrée (Stratégie).
  * **Cohérence à la Lecture :** La cohérence des données est assurée par le consommateur au moment de l'accès au cache, garantissant l'utilisation de la valeur la plus proche de l'instant T.
  * **Sortie :** Les ordres générés sont poussés dans une `OrderInputQueue` prioritaire, découplant la décision de l'exécution finale par l' `Order Manager`.

---

### 4. Règles Critiques

* **Sémantique "Latest-only" :** Le RM et le PM lisent la version la plus récente disponible dans le cache au moment de leur réveil.
* **Priorité de la Surveillance :** Bien que lancés en parallèle, la logique de surveillance d'urgence (`10a`) est conçue pour avoir une priorité de scheduling supérieure au niveau de l'OS/Runtime par rapport à la stratégie standard (`10b`).
* **Indépendance de l'Audit :** La décision n'attend jamais la création d'un `SnapshotHeader` ou une écriture disque. Si un retard survient dans la Slow-Lane (audit), la boucle décisionnelle continue sans impact.
* **Découplage de l'Exécution :** L'envoi vers l' `OrderInputQueue` est non-bloquant.

---

### 5. Conclusion

Ce module garantit un flux de prix **déterministe, ultra-rapide et cohérent** pour le système. Il assure que des blocs complets de données de marché (`SnapshotHeader`) sont disponibles en mémoire avec la plus faible latence possible pour la surveillance du risque (Risk Monitor) et l'exécution des stratégies (Portfolio Manager), en isolant la charge de calcul de la charge d'écriture en mémoire.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | **onMarketDataAggregated()** | Data Cache | Thread Manager | Signal léger notifiant qu'une nouvelle salve de cotations est disponible en mémoire. |
| 2 | **activateHandlers()** | Thread Manager | Thread Manager | Allocation/Réveil des threads dédiés pour RM et PM. |
| ref | 10a-PHASE2-Surveillance-Urgence | Risk Monitor | (Self) | **Lecture directe Cache.** Vérification des seuils de risque et génération d'ordres de protection. |
| ref | 10b-PHASE2-Strategie-Standard | Portfolio Manager | (Self) | **Lecture directe Cache.** Calcul des signaux et génération d'ordres de trading. |
| 3 | enqueueOrder(Order, Priority) | Risk Monitor | OrderInputQueue | Envoi d'ordres (Priorité Haute). |
| 4 | enqueueOrder(Order, Priority) | Portfolio Manager | OrderInputQueue | Envoi d'ordres (Priorité Standard). |
| 5 | dequeueOrder() | Order Manager | OrderInputQueue | Récupération asynchrone pour exécution marché. |

---

