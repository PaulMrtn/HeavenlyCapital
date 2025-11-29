## I. Data Management

Ce cœur est responsable de l'ingestion, du nettoyage, de la persistance et de la mise à disposition des données.

### **Database Connector**

Ce composant est l'interface du système avec la base de données relationnelle. Sa fonction principale est de gérer le cycle de vie des connexions : établir, maintenir, et clore les sessions. Il gère la **résilience** de la connexion, la **lecture sécurisée** des identifiants, et fournit des métriques de **surveillance** au système.

* **Interfaces Fournies / Requises :**
    * **IConnectionFactory** : **Interface fournie** par le `Database Connector` pour instancier et retourner un objet de connexion ou une session de base de données.
    * *SQL Alchemy* : **Package/Framework requis** (ORM) pour la gestion technique du *pool* de connexions.
    * **Config / Secret Vault** : **Composant/Source requis** pour l'extraction sécurisée des identifiants de connexion (*secrets*).
    * **Monitoring Module** : **Composant requis** pour rapporter l'état des connexions et la latence I/O.

#### Notes

* **Résilience :** Implémente une **logique de *retry*** pour rétablir automatiquement la connexion à la base de données en cas de défaillance temporaire du réseau.
* **Sécurité :** Construit l'URI de connexion en lisant les identifiants à partir d'une source sécurisée (**Secret Vault**) et non d'un simple fichier de configuration.
* **Performance/Monitoring :** Transmet des métriques de performance et de santé de la base de données au **Monitoring Module** (e.g., temps de réponse, taux de succès des connexions) pour une surveillance proactive.


### **Data Preprocessor**
  
Ce composant assure la sanitisation et la normalisation des payloads de données brutes. Il est invoqué par le Data Ingestion Layer en amont de toute opération de persistance. Il opère comme une unité de transformation interne garantissant la cohérence du schema des données.


### **Data Ingestion Layer (DIL)**

Le DIL est l'orchestrateur de la persistance des *data sets. Sa responsabilité principale est de fournir un set de méthodes d'écriture pour injecter l'intégralité des flux de données dans le système de stockage persistant. Il assure la séquence des opérations : appel au Data Preprocessor pour la standardisation des données, puis mapping et écriture.

* **Interfaces Fournies / Requises :**
    * **IDatabaseWriter** : **Interface de persistance fournie** par le DIL, constituant le **contrat de service** pour les composants tiers souhaitant stocker des données (e.g., **Live Data Hub**).
    * **Database Connector** : **Composant requis** pour la gestion du *pool* de connexions et des sessions de transaction vers le *data store*.
    * **Data Preprocessor** : **Composant requis** pour standardiser le *payload* de données.
    * *SQL Alchemy* : **Package/Framework requis** (ORM) utilisé pour l'abstraction et l'efficacité des opérations CRUD.


### **Data Access Layer (DAL)**

**Description :** Le DAL est la couche d'**abstraction de la lecture** qui fournit des méthodes simplifiées et optimisées pour requêter l'intégralité des *data sets* stockés. Il agit comme un **intermédiaire de service** permettant aux composants clients (stratégies, *risk monitors*) de consommer des données sans connaissance directe du *schema* ou de la complexité du **Database Connector**.

* **Interfaces Fournies / Requises :**
    * **IDataReader** : **Interface de lecture fournie** par le DAL. Elle expose des méthodes de haut niveau (ex: `get_historical_prices(asset_id, start_date)`) qui constituent le **contrat de service** pour la consommation de données.
    * **Database Connector** : **Composant requis** pour obtenir la session de connexion active à la base de données.
    * *SQL Alchemy* : **Package/Framework requis** (ORM) utilisé pour la construction et l'exécution des requêtes optimisées.

#### Notes

* **Mise en Cache des Requêtes :** Intégration d'un mécanisme de **caching** au niveau du DAL pour les requêtes de données historiques coûteuses ou fréquemment sollicitées. Cela permet de réduire la **latence** et la **charge I/O** sur la base de données pour les composants consommateurs.
  

### **Live Data Hub**

Ce composant est l'**écouteur central** des flux de prix marché. Il écoute les *triggers* de prix en temps réel via l'**IBKR Gateway** pour créer des **snapshots de marché** réguliers. Ces données sont mises en cache via l'**Interface Cache** et mises en file d'attente pour la persistance via l'**Interface Buffer**.

* **Interfaces Fournies / Requises :**
    * **IBKR Data Interface** : **Interface requise** via **IBKR Gateway** pour recevoir les mises à jour de prix (*market data stream*).
    * **Cache Interface** : **Interface fournie** pour l'écriture des données en cache.
    * **Buffer Interface** : **Interface fournie** pour la mise en file d'attente des données destinées à la persistance asynchrone.
    * *ib\_async* : **Package/Framework requis** pour la gestion de l'écoute asynchrone des événements de l'API de courtage.

* **Data Classes :**
    * **TickData** : Représente l'état instantané d'un actif (bid/ask, dernière transaction, volumes). C'est la donnée brute du marché.
    * **SnapshotHeader** : Représente l'en-tête d'un instantané global du marché à une fréquence donnée (ex: '1m', '5m').
    * **MarketQuote** : Représente la cotation consolidée d'un actif au sein d'un SnapshotHeader pour une période donnée.

#### Notes

* **Cohérence des Ticks :** Inclusion d'un mécanisme de vérification pour détecter les **sauts (gaps)** ou les incohérences dans la séquence des *ticks* reçus, afin de garantir la qualité des **SnapshotHeader** générés.
* **Suivi de Latence :** Enregistrement du **`receive_timestamp`** (temps de réception par le *Hub*) en plus du `timestamp` du marché. Cela permet de calculer la latence entre le courtier et le système et d'auditer la performance.


---

### II. Real-Time Core (Noyau Temps Réel)

Ce cœur gère les opérations critiques nécessitant une faible latence, notamment l'exécution d'ordres et la surveillance immédiate.

* **Order Manager** : Traque le statut de tous les ordres ouverts et exécutés, en interaction directe avec l'API de courtage.
* **Portfolio State Manager** : Maintient l'état actuel et précis du portefeuille (positions, liquidités, P&L).
* **Risk Monitor** : Effectue des contrôles de risque pré- et post-trade en temps réel.

---

### III. Pipeline Core (Noyau de Pipeline)

Le cœur de la stratégie, exécutant la logique complexe de sélection d'actifs, d'optimisation et d'évaluation du risque.

* **Pipeline Manager** : Orchestre l'exécution séquentielle des étapes de la stratégie.
* **Asset Selection** : Applique des critères d'éligibilité pour sélectionner l'univers d'actifs.
* **Filter Manager** : Applique des filtres basés sur des indicateurs techniques ou fondamentaux.
* **Portfolio Optimizer** : Calcule les poids optimaux des actifs sélectionnés pour le portefeuille.
* **Risk Manager** : Évalue et contraint le risque global généré par l'optimisation.
* **Data Integrity Engine** : Assure que les données utilisées par le pipeline sont valides et non corrompues.

---

### IV. Backtest Core (Noyau de Backtesting)

Ce cœur est dédié à l'évaluation des performances des stratégies sur des données historiques et à la calibration des modèles.

* **Backtest Engine** : Moteur principal d'exécution pour la simulation des stratégies historiques.
* **Parametric Optimizer** : Réalise l'optimisation des paramètres pour trouver la meilleure performance ajustée au risque.
* **Shock Simulator** : Permet de réaliser des stress-tests en simulant des chocs de marché (e.g., Krach de 2008).

---

### V. Utilitaires & Infrastructure

Composants transversaux et d'infrastructure pour le bon fonctionnement et la surveillance du système.

* **Session Manager** : Gère l'état et le cycle de vie des sessions utilisateur ou d'exécution.
* **Thread Manager** : Contrôle l'allocation et la gestion des threads d'exécution.
* **Concurrency Manager** : Gère les mécanismes de parallélisme et de concurrence.
* **Log Manager** : Centralise et formate les journaux (logs) du système.
* **Reporting Manager** : Génère des rapports de performance et d'activité du système.
* **Monitoring Module** : Collecte des métriques sur la santé et les performances du système en temps réel.
* **Notification Manager** : Envoie des alertes aux utilisateurs ou aux systèmes externes.

---

### Interfaces et Connecteurs Clés

Ces éléments définissent les contrats de communication ou les dépendances technologiques entre les composants.

* **Ib\_async** : **Interface/Bibliothèque** fournie pour gérer la communication asynchrone avec l'API Interactive Brokers.
* **IBKR Order Sender** : **Interface fournie** par l'API de courtage pour l'envoi des ordres, utilisée par l'Order Manager.
* **IBKR Data Interface** : **Interface fournie** par l'API pour récupérer les données de marché, utilisée par le Live Data Hub.
* **IDatabaseWriter** : **Interface fournie** pour écrire des données de manière abstraite dans le stockage persistant.
* **SQL Alchemy** : **Bibliothèque/ORM** (Object-Relational Mapping) utilisée pour l'accès aux bases de données relationnelles.
* **Config, Path, Params** : **Interfaces/Paramètres** génériques pour la configuration, les chemins de fichiers et les données d'entrée.
