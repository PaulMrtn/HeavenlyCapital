## Diagram Activity : Phase I - Pré-Trade

# WARNING : THIS FIGURE ISN'T UP TO DATE 

<p align="center">
  <img src="img/DA_01_TradingSystem_PreTrade.svg" width="900">
</p>

La Phase Pré-Trade est l'étape de **démarrage et de validation** du système. Son objectif est de garantir que tous les composants sont instanciés, configurés, et opérationnellement prêts à communiquer avant l'ouverture du marché.

## 1. Démarrage et Contrôles de Résilience (Orchestration par System Manager)

Cette séquence est séquentielle et intègre une logique de **Retry** pour gérer les pannes transitoires.

### 1.1. Réveil du Système et Contrôles Critiques

* **Déclenchement :** Le processus est initié par un signal **`SYSTEM_WAKEUP`** émis par le `Market Clock`.
* **Contrôle de Connectivité (DB) :** Le `System Manager` ordonne au `Database Connector` de vérifier l'état de la connexion. En cas d'échec persistant après des boucles de **Retry**, le système s'arrête et envoie une **notification d'urgence**.
* **Contrôle de Connectivité Critique (Courtier) :** Une fois la connexion DB stable, le `System Manager` vérifie la connexion à l'API du courtier et à TWS/GB. En cas d'échec persistant, le système s'arrête et envoie une **notification d'urgence**.

### 1.2. Calcul et Décision de Jour Ouvré

* **Calcul et Persistance du Statut :** Le `System Manager` calcule l'objet **`MarketDayStatus`** et le persiste via le `Data Ingestion Layer`.
* **Contrôle de Jour Ouvré :** Si **`MarketDayStatus.is_trading_day == FALSE`**, le `System Manager` bascule immédiatement en phase **Off-Cycle** (Veille). Sinon, le processus passe à l'étape 2.

---

## 2. Instanciation des Composants et Injection des Dépendances / Configs

Cette étape est optimisée pour minimiser les latences d'I/O en centralisant la lecture des données.

### 2.1. Lecture de TOUTES les Configurations (I/O Optimisé) 🚀

* **Lecture Intensive :** Le `System Manager` ordonne au `Data Access Layer (DAL)` de **regrouper et requêter en un seul bloc d'opérations** toutes les configurations statiques nécessaires :
    * Configurations des **Pools de Threads** (tailles, priorités).
    * Configurations des **Singletons** (`IBKR Gateway`, `LDH`).
    * Configurations des **Managers Locaux** (Session configs, Risk Limits, etc.).
* **Stockage en Mémoire :** Toutes les données de configuration sont stockées en mémoire pour une injection rapide et séquentielle.

### 2.2. Instanciation Globale et Pools de Threads

* **Instanciation Singletons :** Le `System Manager` instancie l'`IBKR Gateway` et le `Live Data Hub (LDH)` en leur **injectant immédiatement** leurs configurations spécifiques lues à l'étape 2.1. Un H-Check unitaire confirme l'intégrité de chaque objet.
* **Initialisation des Pools de Threads :**
    * Le `System Manager` ordonne au **`Thread Manager (TM)`** de créer les Pools I/O (**CRITICAL**, **STANDARD**) en utilisant les tailles lues.
* **Validation du Pool de Priorité (H-Check Renforcé) :** Le `TM` effectue un **test de priorité actif**. Il lance un **mini-job de test** sur un `PoolWorker` du Pool CRITICAL pour s'assurer qu'il s'exécute avec le niveau de priorité maximal configuré par le système d'exploitation.

### 2.3. Instanciation des Sessions et Managers Locaux (Boucle)

* Le `System Manager` crée les objets `TradingSession`.
* **Boucle d'Instanciation :** Une boucle itère sur chaque `TradingSession` :
    * Création du triplet de managers locaux : **`Portfolio Manager (PM)`**, **`Risk Monitor (RM)`**, et **`Order Manager (OM)`**.
    * **Injection de Dépendance :** Le `MarketDayStatus` et les configurations spécifiques à la session sont injectés.
    * Un H-Check unitaire est effectué sur chaque manager local pour confirmer sa bonne construction.

---

## 3. Chargement des Données et Parallélisation

L'objectif est de charger les données opérationnelles en mémoire et de valider le flux de données en temps réel simultanément.

* **Lancement Parallèle :** Le `System Manager` lance deux branches d'initialisation en parallèle :
    * **Branche A (Chargement de Données) :** Le PM et le RM lisent les données dynamiques du jour (Orders en attente, RiskLimits) et les mettent en mémoire.
    * **Branche B (Validation du Flux) :** L'`IBKR Gateway` lance une requête TEST (PING) pour valider que le canal de données IBKR → LDH est ouvert et fonctionnel.
* **Synchronisation :** Le `System Manager` attend la complétion des deux branches.

---

## 4. Validation Opérationnelle Croisée (HEART CHECK)

Cette validation finale vérifie que les **liens de communication asynchrones** sont établis et que le système est prêt pour le trading.

* **Vérification des Dépendances :** Le `System Manager` effectue des requêtes actives pour valider :
    * Le flux de prix actif entre l'`IBKR Gateway` et le `LDH`.
    * Que le `Risk Monitor` est prêt à recevoir les mises à jour de prix du `LDH`.
    * Que le `Portfolio Manager` est correctement lié à l'`Order Manager` pour la gestion des exécutions.
* **Log :** Si tous les tests réussissent, le `System Manager` enregistre le statut **"System Ready"**.

---

## 5. Transition vers la Phase In-Trade

* Le `System Manager` attend le signal **`MARKET_OPEN`** émis par le `Market Clock`.
* Dès réception, il bascule l'état du système en phase **In-Trade**.
