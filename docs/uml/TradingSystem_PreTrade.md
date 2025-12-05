## Diagram Activity : Phase I - Pré-Trade

<p align="center">
  <img src="img/DA_01_TradingSystem_PreTrade.svg" width="900">
</p>


La Phase Pré-Trade est une étape de *bootstrapping*. Son objectif est de garantir que tous les composants sont **instanciés, configurés, et opérationnellement prêts à communiquer** avant la réception du signal d'ouverture du marché. La séquence est conçue pour assurer la gestion des erreurs et l'injection des dépendances.

### 1. Démarrage et contrôles de résilience (Orchestration par `System Manager`)

Cette séquence est séquentielle et intègre une logique de **Retry (tentatives)** pour gérer les pannes transitoires de services.

* **Réveil du Système** : Le processus est déclenché par un signal `SYSTEM_WAKEUP` émis par le `Market Clock`.
* **Contrôle de connectivité (DB)** :
    * Le `System Manager` ordonne au `Database Connector` de vérifier l'état de la connexion.
    * **Log :** Enregistrement du statut initial de la DB  
    * **Gestion d'Erreur :** Si la vérification échoue, le système effectue une boucle de `Retry` (un certain nombre de tentatives avec un délai d'attente croissant). Si le nombre maximum de tentatives est atteint, le système log l'erreur critique et s'arrête (`ERROR`).
* **Contrôle de Connectivité Critique (Courtier)** :
    * Une fois la connexion DB stable, le `System Manager` ordonne à l'`IBKR Gateway` de vérifier la connexion à l'API du courtier et de TWS/GB (.exe) dans le même temps.
    * **Gestion d'Erreur :** Application de la même logique de `Retry` en cas d'échec transitoire. Si l'échec est persistant, le système s'arrête.
* **Calcul et Persistance du Statut** : Le `System Manager` utilise le package `pandas_market_calendars` pour determiner l'objet `MarketDayStatus` et le `IDatabaseWriter` du `Data Access Layer` pour la persistence.
* **Contrôle de Jour Ouvré** :
    * **Condition :** Si `MarketDayStatus.is_trading_day == FALSE`, le `System Manager` bascule immédiatement en phase `Off-Cycle` (Veille).
    * **Sinon :** Le processus passe à l'étape 2 d'instanciation.

#### Note : 

* Dans le cas d'une `ERROR` lors des tests de connectivité avec la DB ou IBKR alors, il faut envoyer une notification d'urgence (`Notification Manager`).

### 2. Instanciation des composants et injection des dépendances / configs

Les composants globaux sont instanciés en premier. La lecture des configurations depuis la base de données est centralisée par le `System Manager`.

* **Instanciation Globale (Singletons)** :
    * Instanciation du **`IBKR Gateway`** et du **`Live Data Hub (LDH)`** (composants globaux et uniques).
    * **H-Check Unitaire :** Une vérification initiale est effectuée sur chaque objet pour confirmer son intégrité en mémoire.
* **Lecture des Métadonnées** :
    * Le `System Manager` ordonne au `Data Access Layer` de **requêter** toutes les configurations statiques nécessaires :
        * Configurations des **Sessions** (LIVE/PAPER).
        * Métadonnées des **Managers** (`PM`, `RM`, `OM` par défaut).
* **Instanciation des Sessions et Managers Locaux (Boucle)** :
    * Le `System Manager` utilise les configurations lues pour ordonner au `Session Manager` de créer les objets `TradingSession`.
    * **Boucle d'Instanciation :** Le `System Manager` itère sur chaque `TradingSession` créée :
        * Pour chaque session, il instancie un triplet de composants locaux : **`Portfolio Manager (PM)`**, **`Risk Monitor (RM)`**, et **`Order Manager (OM)`**.
        * **Injection de Dépendance :** Les configurations spécifiques à la session (lues à l'étape précédente) sont injectées dans le constructeur de chaque manager.
        * **H-Check Unitaire (Local) :** Une vérification est effectuée sur le PM, RM et OM pour confirmer leur bonne construction avec les configs injectées.
  
    
### 3. Chargement des Données et Parallélisation

L'objectif est d'assurer que les managers locaux ont leurs données opérationnelles chargées et que le canal de données temps réel est prêt.

* **Lancement Parallèle** : Le `System Manager` lance deux branches en parallèle :
    * **Branche A (Chargement de Données) :** Les instances de `PM` et `RM` lancent la requête (via le `DAL`) pour lire les données dynamiques du jour :
        * `Orders` en attente (rebalancement).
        * `RiskLimits` et `Stop-Loss` pour les positions actives.
        * Ces données sont **mises en mémoire** dans les structures internes du PM et du RM.
    * **Branche B :** L'`IBKR Gateway` lance une requête de données TEST (ex: PING sur un symbole simple) et attend la première réponse pour valider que le canal de données IBKR → LDH est ouvert et fonctionnel.
* **Synchronisation** : Le `System Manager` attend la complétion des deux branches.


### 4. Validation Opérationnelle Croisée (HEART CHECK)

C'est l'étape de validation finale. Elle vérifie que les **liens de communication asynchrones** sont établis.

* **Vérification :** Le `System Manager` effectue des requêtes actives pour valider les dépendances :
    * **LDH & IBKR Gateway :** L'IBKR Gateway a-t-il un flux de prix actif ? Le LDH a-t-il correctement souscrit et reçoit-il un signal *Keep-Alive* ?
    * **Risk Monitor (RM) :** Le RM a-t-il chargé toutes les positions et est-il prêt à recevoir les mises à jour de prix du LDH ?
    * **Portfolio Manager (PM) :** Le PM est-il correctement injecté dans l'OM et prêt à recevoir/traiter les confirmations d'exécution (Fills) ?
* **Log :** Si tous les tests réussissent, le `System Manager` enregistre le statut "System Ready" et entre dans l'état d'attente.

### 5. Transition vers la Phase In-Trade

* Le `System Manager` attend le signal `MARKET_OPEN` émis par le `Market Clock`.
* Dès réception, il bascule l'état du système en phase **In-Trade**.
