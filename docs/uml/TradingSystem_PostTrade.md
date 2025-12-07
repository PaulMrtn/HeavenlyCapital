## Diagramme d'Activité : Phase III - Post-Trade

<p align="center">
  <img src="img/DA_03_TradingSystem_PostTrade.svg" width="900">
</p>


---

### 7. Clôture du Marché et Synchronisation Critique

La phase Post-Trade est déclenchée par le signal de fermeture du **Market Clock**. Cependant, le processus d'audit ne peut débuter immédiatement.

La première étape cruciale est la **synchronisation du système**. Le **System Manager** ordonne au **Job Manager** de **forcer la complétion et d'attendre la validation de persistance** de toutes les écritures critiques initiées durant la phase *In-Trade* (comme les mises à jour des **Fills** et des **Positions**). Cette étape garantit que la phase d'audit commence sur un **état du portefeuille final, complet et atomiquement persisté** en base de données, évitant toute anomalie due à la latence des queues d'écriture.

#### Audit et Intégrité Financière

Une fois la synchronisation assurée, le **Portfolio Manager (PM)** exécute la **Réconciliation Finale**. Cette étape compare l'état du portefeuille interne avec les données reçues du courtier (IBKR Gateway).

* **En cas d'écart**, le **PM** émet immédiatement une **Alerte Critique** et enregistre l'incident (`DATA_INTEGRITY_CHECK`). Cette alerte garantit une notification humaine urgente et une trace auditable de la défaillance d'intégrité.

---

### 8. Persistance Orchestrée et Gestion des Dépendances I/O

Le reste de la phase est dominé par la gestion de trois tâches I/O distinctes, qui doivent s'exécuter dans un ordre strict pour respecter la chaîne d'audit : $\text{Données Brutes} \rightarrow \text{Rapport Financier} \rightarrow \text{Décision Stratégique}$.

#### Séparation des Ressources (Thread Manager)

Les processus d'écriture sont soumis au **Thread Manager** pour allocation, conformément à leurs besoins en ressources et leur criticité :

* **Pool I/O Bulk :** Alloué aux écritures massives, lentes, mais nécessaires à l'historique.
* **Pool I/O Critical :** Alloué aux écritures atomiques (configuration, plan d'ordres), qui exigent une garantie d'exécution immédiate.

#### Enchaînement des Tâches Dépendantes

1.  **Persistance des Données de Marché (Bulk I/O) :** Le **Live Data Hub (LDH)** soumet l'ordre de **FLUSH du Buffer de Ticks/Snapshots**. Cette tâche est allouée au **Pool I/O Bulk**. Sa complétion est le premier jalon du Post-Trade.
2.  **Génération du Rapport d'Audit Dépendant :** La **Tâche de Génération du Rapport** (PnL, métriques agrégées) ne peut être lancée qu'après avoir reçu la **confirmation de validation de persistance** du Bulk I/O. Cette dépendance est gérée par le **Job Manager**, qui utilise un mécanisme de synchronisation pour s'assurer que les données brutes sont disponibles. La tâche de reporting est ensuite allouée au **Pool I/O Audit**.
3.  **Calcul de la Stratégie Dépendant :** Le **Strategy Engine** ne peut exécuter le calcul du **Portfolio Target** que si deux conditions sont remplies : la confirmation de la **fin de la tâche de Reporting/Audit**, ET la vérification que le jour suivant est un **Jour de Rebalancement**.

---

### 9. Préparation Atomique du Cycle Suivant

Cette étape garantit que le système est prêt à redémarrer sans faille.

#### Persistance du Plan d'Action Critique

Une fois que le **Strategy Engine** a calculé le **Portfolio Target** (le plan d'ordres pour l'ouverture prochaine), ce plan est soumis pour **Persistance Atomique**. Il est immédiatement alloué au **Pool I/O Critical**. Cette isolation protège la sauvegarde de la décision la plus importante du système contre toute latence ou défaillance des autres écritures.

#### Sauvegarde de la Configuration

En parallèle, le **Session Manager** procède à la sauvegarde de l'**État Final de la Configuration** de la session. Cette écriture est également considérée comme **critique** et utilise le **Pool I/O Critical** car le système doit redémarrer avec les paramètres les plus à jour.

Le **System Manager** ne bascule le système en phase **Off-Cycle (Veille)** que lorsque la **validation de persistance** de ces deux écritures critiques (Target et Configuration) est reçue, garantissant une intégrité totale au moment de l'arrêt.
