
#  Activity diagram  : Cycle de Vie Quotidien 

<p align="center">
  <img src="/img/DA_00_TradingSystem_ActivityFlow.svg" width="900">
</p>


### I. Phase Pre-Trade (Préparation à l'Ouverture)

Cette phase est dédiée à l'initialisation du système et au chargement des données avant le début de la session de trading.

### 1. Démarrage et Contrôle du Cycle de Marché

Le cycle démarre par un événement temporel, non pas par un *cold boot*.

* **Déclencheur :** Le **System Core** sort du mode veille suite à un signal programmé du **Market Clock** (ex: 8h00 AM).
* **Orchestration :** Le **System Core** prend le relais :
    * Il utilise le **Sessions Manager** pour instancier les sessions de trading.
    * Il consulte le **TradingCalendar** pour chaque session afin de vérifier si la date correspond à un jour ouvré.
    * Il détermine le type de journée (Jour de Rebalancement vs. Jour de Trading Normal).

### 2. Vérifications Préalables (Intégrité et Connexion)

Le **System Core** garantit que toutes les dépendances sont saines **avant** de charger les stratégies.

* **Vérification de Santé :** Le **System Core** contrôle l'état des connexions critiques :
    * Lien avec la base de données (`Database Connector`).
    * Lien avec le courtier (`IBKR Gateway` / TWS API).
    * Statut et identification de chaque compte Interactive Brokers.

### 3. Chargement et Préparation des Données

Cette étape lance des processus en parallèle pour garantir que la prise de décision est immédiate à l'ouverture. Les actions sont lancées par le **System Core** et exécutées par les autres Cores :

* **Responsabilité Trading/Risk Core :** Le **Trading/Risk Core** charge en mémoire les paramètres essentiels à l'exécution :
    * **Jour de Rebalancement :** Charge les ordres de rebalancement (créés la veille et stockés en base) pour une soumission potentielle à l'ouverture.
    * **Jour de Trading Normal :** Charge les données de **stop-loss** et de take-profit relatives aux positions en cours (`Risk Monitor` et `PSM`).
* **Responsabilité Data Core :** Le **Data Core** démarre l'écoute et l'acquisition des données de marché :
    * L'**IBKR Gateway** initialise la connexion pour être prêt à recevoir les **tick data** (prix) et les **fills** (exécutions) dès l'ouverture.

### 4. Synchronisation et Transition vers In-Trade

* **Synchronisation :** Le **System Core** attend la complétion de deux conditions avant de procéder :
    1.  Le chargement des données (Ordres / Stop-Loss) par le **Trading/Risk Core** est terminé.
    2.  La connexion à l'**IBKR Gateway** par le **Data Core** est établie et fonctionnelle.
* **Déclenchement :** Le **System Core** bascule en phase **In-Trade** uniquement après avoir reçu un nouveau signal du **Market Clock** indiquant que l'heure d'ouverture est atteinte ($\text{current\_time} \ge \text{market\_open\_time}$).

---

### II. Phase In-Trade (Exécution et Surveillance)

Cette phase est caractérisée par des flux de données à haute fréquence, l'évaluation continue des risques, et l'exécution d'ordres.

### 5. Activation des Flux Temps Réel

Dès la transition vers la phase In-Trade, le **Data Core** active ses flux asynchrones :

* Le **Live Data Hub** commence à recevoir les **tick data** (flux de prix haute fréquence) via l'**IBKR Gateway**.
* Des **snapshots** agrégés sont générés régulièrement.
* **Distribution des Snapshots (Parallélisme) :**
    * **Vers la Persistance (I/O Lent) :** Les snapshots sont mis en file d'attente (buffer) pour une insertion différée en base de données par le **Persistence/Storage Core**.
    * **Vers le Temps Réel (I/O Rapide) :** Les snapshots sont écrits dans un **cache** à faible latence.

### 6. Boucle de Décision et d'Exécution

Le **Trading/Risk Core** utilise le cache temps réel pour une boucle continue de décision :

* Le **Risk Monitor** lit le cache pour surveiller les prix des positions actives et vérifier les conditions de **stop-loss** chargées.
* Le **Portfolio State Manager (PSM)** évalue les conditions d'achat/vente (selon la stratégie).
* L'**Order Manager** soumet les ordres (préparés ou nouvellement générés) au courtier via l'**IBKR Gateway**.
* Le **Trading/Risk Core** traite les exécutions (`Fills`) reçues de manière asynchrone pour mettre à jour les positions et les lots de PnL.

---

### III. Phase Post-Trade (Réconciliation et Audit)

Cette phase est déclenchée par la fermeture du marché et se concentre sur l'intégrité et la préparation pour le jour suivant.

### 7. Clôture des Opérations et Séquence d'Audit

* **Déclencheur :** Le **System Core** reçoit le signal de fermeture du **Market Clock** ($\text{current\_time} \ge \text{market\_close\_time}$).
* **Arrêt des Flux (Data Core) :** L'ingestion des **tick data** est immédiatement arrêtée.
* **Arrêt Trading (Trading/Risk Core) :** La boucle de surveillance du `Risk Monitor` est arrêtée, et l'**Order Manager** annule les ordres non exécutés.
* **Réconciliation Finale (Trading/Risk Core) :** Le **PSM** effectue une **réconciliation** pour comparer l'état final du portefeuille (positions, cash) avec les données officielles d'Interactive Brokers, garantissant l'intégrité.

### 8. Persistance et Audit (Rapport de Fin de Journée)

* **Mise à Jour Historique (Data Core) :** Le **Persistence/Storage Core** finalise l'écriture de toutes les données en attente (ticks, fills, logs) et met à jour les données historiques via des API dédiées. **(Cette étape doit précéder la vérification du jour suivant).**
* **Rapport d'Audit (Data Core) :** Le **Monitoring Manager** génère le rapport complet de la journée (PnL, métriques de performance, erreurs d'audit) et l'enregistre en base de données.

### 9. Préparation du Cycle Suivant

* **Vérification du Jour Suivant (System Core) :** Le **System Core** consulte le `TradingCalendar` pour déterminer le type de la prochaine journée.
* **Exécution de la Stratégie (Trading/Risk Core) :**
    * **Condition :** Si le jour suivant est un **jour de rebalancement**, le **Strategy Engine** (dans le **Trading/Risk Core**) est exécuté.
    * **Objectif :** Ce moteur calcule les nouvelles demandes d'ordres cibles et les enregistre en base de données (via le **Data Core**) pour être chargées le lendemain matin.
* **Transition :** Une fois toutes les tâches Post-Trade complétées et validées, le **System Core** bascule en phase **Off-Cycle** (Veille/Tâches de nuit).
