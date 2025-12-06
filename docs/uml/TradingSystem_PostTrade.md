## Diagramme d'Activité : Phase II - Post-Trade

<p align="center">
  <img src="img/DA_03_TradingSystem_PostTrade.svg" width="900">
</p>


---

### 6. Traitement des Flux Temps Réel : Acquisition et Distribution

Dès la réception du signal d'ouverture du marché par le **System Manager**, le **Live Data Hub (LDH)** initie le processus d'acquisition et de distribution des données de marché. L'IBKR Gateway commence l'acquisition des **Tick Data** (flux de prix haute fréquence) de manière asynchrone, marquant le début de l'activité du cœur temps réel.

Le **Live Data Hub** exécute immédiatement une **Surveillance Critique du Flux**. Il intercepte chaque Tick pour vérifier le *timestamp* et le temps écoulé depuis le dernier tick. Cette action sert à détecter une latence critique ou une erreur de connexion réseau. Si le seuil de latence est dépassé ou si la connexion est perdue, le **LDH** émet un événement **`CRITICAL_ERROR`** au **System Manager**, qui déclenche la séquence d'arrêt sécurisé (**Kill Switch**).

Si le flux est jugé stable et la latence est acceptable, le **Live Data Hub** agrège ces ticks pour générer régulièrement des **Snapshots** des cotations de marché. 

Un **Nœud de Fork** distribue le Snapshot généré en deux flux parallèles, une technique de conception essentielle pour optimiser la latence du système :

* **Flux Temps Réel (Fast-Lane) :** Le Snapshot est immédiatement écrit dans un **cache en mémoire vive**. Ce cache à faible latence permet un accès instantané aux prix les plus récents par le **Risk Monitor** et le **Portfolio Manager** pour la prise de décision.
* **Flux de Persistance (Slow-Lane) :** Le Snapshot est mis en file d'attente (buffer) pour une **écriture différée** en base de données.

#### 6.1 Persistance des Données de Marché (Bulk I/O)

La persistance des Snapshots est traitée comme une tâche d'arrière-plan massive (**Bulk I/O**). Le **Live Data Hub** soumet l'ordre de **FLUSH (vidage)** du buffer au **DIL (Data Ingestion Layer)**. Le DIL formule la requête et la soumet au **Job Manager**, spécifiant explicitement le besoin d'utiliser le **Pool I/O Bulk**. Le **Job Manager** délègue ensuite au **Thread Manager** l'exécution de la tâche en allouant un thread du **Pool I/O Bulk** dédié. Cette isolation garantit que ces écritures lourdes et lentes ne bloquent jamais le thread I/O critique utilisé pour l'envoi d'ordres ou la persistance transactionnelle. Le DIL exécute alors l'écriture physique en base.

---

### 7. Boucle de Décision et d'Exécution

La boucle de décision et d'exécution s'exécute à très haute fréquence, pilotée par les données du cache temps réel et orchestrée par le **Risk Monitor** et le **Portfolio Manager (PM)**.

#### 7.1 Surveillance et Ordres d'Urgence

Le **Risk Monitor** lit en continu le cache temps réel pour obtenir le prix le plus récent et surveille l'état de chaque position active. Si une condition de sortie pré-définie, comme un **Stop-Loss** ou un **Take-Profit**, est atteinte, le **Risk Monitor** génère immédiatement un **Ordre d'Urgence**. Cet ordre est envoyé à l'**Order Manager** avec une indication de **Priorité Maximale**, court-circuitant l'évaluation de stratégie standard.

#### 7.2 Traitement des Ordres Standards et Exécution

Le **Portfolio Manager (PM)** évalue les conditions d'achat/vente selon la stratégie en cours pour générer des Ordres Standards si nécessaire. L'émission d'ordres par le PM est strictement conditionnée :

1.  **Jour de Rééquilibrage :** Si le **System Manager** a marqué la journée comme une journée de rééquilibrage planifiée, le PM calcule les écarts de pondération du portefeuille et génère des ordres massifs pour corriger l'exposition.
2.  **Timing Intraday (Optionnel) :** Les ordres massifs générés lors d'un rééquilibrage sont soumis à un **Algorithme d'Optimisation Intraday** (ex : TWAP/VWAP) pour optimiser le prix moyen d'exécution sur la journée.
3.  **Par Défaut :** En dehors d'un jour de rééquilibrage, le PM reste silencieux. Il n'émet un ordre que si une autre fonctionnalité (comme le Cash Management ou une stratégie intraday secondaire) le lui demande explicitement.

L'**Order Manager** reçoit tous les ordres (Urgent ou Standard) et les soumet immédiatement au **Job Manager** pour arbitrage. Le **Job Manager** utilise sa logique de priorité pour garantir que les **Ordres d'Urgence** sont traités avant les Ordres Standards. Le Job Manager délègue ensuite la tâche d'envoi au **Thread Manager**, spécifiant le **Pool I/O Critical**. Le **Thread Manager** alloue un thread du Pool I/O Critical pour que l'IBKR Gateway exécute la transmission de l'ordre au courtier, assurant la latence minimale pour l'exécution critique.

#### 7.3 Gestion des Exécutions (Fills) et Persistance Critique

La réception d'une exécution effective (**Fill**) est un événement critique qui nécessite une action immédiate et atomique. L'IBKR Gateway reçoit le Fill et émet immédiatement un événement **'Fill Received'**.

Un **Nœud de Fork** dirige cet événement vers ses deux abonnés critiques en parallèle pour la mise à jour immédiate :

* **Order Manager :** Met à jour le statut de l'objet **Order** (quantité exécutée, statut final).
* **Portfolio Manager :** Met à jour les **Lots de PnL** et l'objet **Position** (calcul du PnL latent et réalisé).

Une fois que l'Order Manager et le Portfolio Manager ont préparé et validé leurs données de mise à jour, l'unité de travail est soumise au **DIL** (via l'interface `IDatabaseWriter`) pour persistance.

Le DIL formule la tâche et la soumet au **Job Manager**, spécifiant l'utilisation du **Pool I/O Critical**. Le **Job Manager** délègue au **Thread Manager** l'allocation d'un thread du Pool I/O Critical, assurant que cette écriture transactionnelle vitale (statut de l'ordre, état financier) est isolée des tâches de fond lentes. Le DIL exécute la transaction de base de données.

La boucle se répète à haute fréquence jusqu'à ce que le **System Manager** reçoive le signal de fermeture (`MARKET_CLOSE`) du **Market Clock**, initiant la transition vers la Phase Post-Trade. 
