
## Diagramme d'Activité : Phase IV - Pre-Market Setup

<p align="center">
  <img src="img/DA_034_TradingSystem_StrategicSetup.jpg" width="900">
</p>

---

Cette phase est dédiée à la **préparation complète du plan de trading du jour T**. Exécutée quelques heures avant l'ouverture et déclenchée par le **Market Clock**, elle commence par l'ingestion des données de marché les plus fiables et actualisées. Elle exécute ensuite le **Strategy Engine pré-paramétré** pour générer le **Portfolio Cible**, qui sera persisté de manière atomique en base de données, rendant le système prêt pour la phase de *Bootstrapping*.

### 10. Initialisation, Validation et Ingestion des Données

Cette étape assure que le système dispose de toutes les conditions et données nécessaires pour commencer la préparation stratégique.

* **Déclencheur :** Un événement temporel programmé par le **Market Clock** (par exemple à 7h00 AM CET).
* **Vérification Critique des Connexions :** Le **System Manager** vérifie l'accessibilité de la Base de Données et des API externes (EODHD). L'échec entraîne un arrêt immédiat et l'émission d'une alerte critique.
* **Vérification du Jour Ouvré :** Le **System Manager** vérifie si le jour T est un jour de trading. Si ce n'est pas le cas, le processus s'arrête et le système bascule immédiatement en veille (`OFF-CYCLE`).
* **Mise à Jour Systématique des Données :** Le **Data Ingestion Layer** exécute la tâche d'ingestion des données de marché via les API externes, en persistant ces informations dans la base de données. 

---

### 11. Calcul Stratégique Conditionnel (Engine Execution)

Le cœur de cette phase est l'exécution du plan de trading pour le jour à venir, conditionnellement à la nécessité d'un rebalancement.

* **Contrôle de Rebalancement :** Le **System Manager** vérifie le statut du jour T (`[IF MarketDayStatus.is_rebalancing_day]`).
* **Exécution de la Stratégie :** Si la condition est remplie, le **Strategy Engine pré-paramétré** est exécuté.
* **Génération du Plan Cible :** L'Engine génère le **Portfolio Cible** (un objet `TargetPortfolioDTO`) qui contient l'ensemble des ordres à exécuter pour atteindre la composition cible.

---

### 12. Persistance Atomique et Fin de la Phase

L'étape finale garantit que les requêtes d'ordres sont stockées de manière atomique pour être chargé sans risque au moment du *Bootstrapping* (Phase I).

* **Soumission de la Tâche Critique :** Le **System Manager** soumet le `TargetPortfolioDTO` au **Job Manager** pour une persistance atomique.
* **Allocation et Enregistrement :** Le **Job Manager** alloue la tâche au **Pool I/O Critical** et enregistre le plan en base de données, garantissant qu'en cas d'échec du système, le plan est soit totalement persistant, soit totalement absent.
* **Validation et Transition :** Le **System Manager** attend la **Validation de Persistance du Portfolio Cible**. Une fois la confirmation d'intégrité reçue, il met le système dans l'état final **`READY_TO_BOOTSTRAP`**.

---

### 13. Déblocage du Cycle

* **Déblocage :** La Phase IV met le système dans un état passif d'attente. La Phase I (Pre-Trade) sera déclenchée par le **Market Clock** (ex: Rêveil/8h00 AM) et utilisera l'état `READY_TO_BOOTSTRAP` pour charger le `SessionConfig` (Phase III) et le `Portfolio Cible` (Phase IV) pour commencer la journée de trading.

