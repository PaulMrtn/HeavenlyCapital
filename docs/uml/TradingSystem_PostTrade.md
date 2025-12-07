## Diagramme d'Activité : Phase III - Post-Trade

<p align="center">
  <img src="img/DA_03_TradingSystem_PostTrade.svg" width="900">
</p>


---

### 7. Clôture du Marché et Synchronisation Critique

La phase **Post-Trade** est déclenchée par le signal de fermeture du **Market Clock**. Cependant, le processus d'audit ne peut débuter immédiatement, car il nécessite une garantie d'**état final**.

#### Synchronisation du Systèm

La première étape cruciale est la **synchronisation du système**. Le **System Manager** ordonne au **Job Manager** de **forcer la complétion et d'attendre la validation de persistance** de toutes les écritures critiques initiées durant la phase *In-Trade* (comme les mises à jour des **Fills** et des **Positions**).

Cette commande inclut l'attente que les **buffers d'écriture soient intégralement vidés** (le **buffer des Ticks/Snapshots** du Live Data Hub) et que les données  soient **atomiquement persistées** en base de données. Cette étape garantit que la phase d'audit commence sur un **état du portefeuille final, complet et atomiquement persisté**, évitant toute anomalie due à la latence des queues d'écriture. 

#### Audit et Intégrité Financière

Une fois la synchronisation assurée, le **Portfolio Manager (PM)** exécute la **Réconciliation Finale**. Cette étape compare l'état du portefeuille interne avec les données reçues du courtier (par exemple, IBKR Gateway).

* **En cas d'écart**, le **PM** émet immédiatement une **Alerte Critique** et enregistre l'incident (`DATA_INTEGRITY_CHECK`). Cette alerte garantit une notification et une trace auditable de la défaillance d'intégrité.

---

## 8. Persistance Orchestrée et Gestion des Dépendances I/O 

Le reste de la phase est dominé par la gestion des tâches I/O dépendantes, qui doivent s'exécuter dans un **ordre strict** pour respecter la chaîne d'audit et de décision. Le **Job Manager** est le garant de cet enchaînement, utilisant des mécanismes de synchronisation (comme les *barriers* ou les *latches*) pour s'assurer qu'une étape ne commence que lorsque ses prérequis sont validés. 


### Enchaînement des Tâches Dépendantes

1.  **Génération du Rapport d'Audit Primaire (Critique) :**
    * La **Tâche de Génération du Rapport** (PnL final, métriques agrégées) est lancée **immédiatement après la Réconciliation Finale** (étape 7).
    * Cette tâche est allouée au **Pool I/O Audit** et sa validation de persistance est le **prérequis direct** pour toutes les étapes suivantes (stratégie et rapports secondaires).

2.  **Lancement des Tâches Secondaire :**
    * La génération d'un **Rapport de Performance** (Module Monitoring).
    * La **mise à jour de données externes** via une API (ex: mise à jour des données fondamental/alternative).
    * Ces tâches sont généralement allouées au **Pool I/O Bulk**.

3.  **Calcul de la Stratégie Dépendant (Décision Finale) :**
    * Le **Strategy Engine** exécute le calcul du **Portfolio Target** (plan d'ordres) en dernier.
    * Deux conditions sont requises :
        * La confirmation de la **fin des tâches précédentes**.
        * La vérification que le jour suivant est un **Jour de Rebalancement** (via le **Session Manager**).


#### Notes :

Les processus d'écriture sont soumis au **Thread Manager** pour allocation, conformément à leurs besoins en ressources et leur criticité :

* **Pool I/O Post-Trade :** Alloué aux écritures atomiques (**Target**, **Configuration**), qui exigent une garantie d'exécution immédiate.
* **Pool I/O Audit :** Alloué aux tâches de reporting principal qui nécessitent un accès stable aux données fraîchement synchronisées (ex: PnL Final).
* **Pool I/O Bulk :** Alloué aux écritures massives et non critiques, y compris les **tâches secondaires futures** qui ne doivent pas bloquer le cycle principal.

---

### 9. Préparation Atomique du Cycle Suivant

Cette étape garantit que le système est prêt à redémarrer sans faille en persistant les décisions critiques.

### Persistance du Plan d'Action Critique

Une fois que le **Strategy Engine** a calculé le **Portfolio Target** (le plan d'ordres pour l'ouverture prochaine), ce plan est soumis pour **Persistance Atomique**. Il est immédiatement alloué au **Pool I/O Post-Trade**. Cette isolation protège la sauvegarde de la décision la plus importante du système contre toute latence ou défaillance des autres écritures.

### Sauvegarde de la Configuration Globale

En parallèle, le **Session Manager** procède à la sauvegarde de l'**État Final de la Configuration** de **toutes les sessions** actives. Cette écriture est également considérée comme **critique** et utilise le **Pool I/O Pool I/O Post-Trade** car le système doit redémarrer avec les paramètres les plus à jour (dernières configurations utilisateur, état des *kill-switches*, etc.).

Le **System Manager** ne bascule le système en phase **Off-Cycle (Veille)** que lorsque la **validation de persistance** de ces deux écritures critiques (**Target** et **Configuration**) est reçue, garantissant une **intégrité totale** au moment de l'arrêt.


---
