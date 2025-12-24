# Architecture – Catalogue Canonique des Ports & Interfaces

## Introduction

Ce document constitue la **source de vérité unique** pour l’ensemble des ports et interfaces du système de trading.

Objectifs :
- Éviter tout doublon fonctionnel entre séquences UML
- Clarifier les frontières de responsabilité
- Garantir une architecture cohérente de grade hedge fund
- Servir de référence avant toute création de nouvelle interface

Règle absolue :
> **Aucune nouvelle interface ne doit être créée sans vérification préalable dans ce document.**

Les interfaces sont classées par **domaine fonctionnel**, indépendamment des séquences (PHASE1, PHASE2, PHASE3, etc.).

---

## 1. Persistence & Data Integrity

### PersistencePort
Point d’accès unique pour toute persistance critique du système.

- Implémenté par : Data Integrity Layer (DIL) / AtomicDBWriteProcess
- Utilisé par : Portfolio Manager, Order Manager, Live Data Hub (si nécessaire)
- Responsabilités :
  - Persistance des snapshots (positions, portefeuilles)
  - Ordres et exécutions (Fills)
  - SessionBooks et journaux de session
  - États courants du système métier
- Règles :
  - Accès direct au DIL strictement interdit
  - Transactions atomiques obligatoires (start / commit / rollback)
  - Isolation totale des objets métier
- Phases :
  - Bootstrapping
  - Runtime métier
  - Post-trade

---

### ISessionStatusWriter
* **Implémenté par** : `Data Integration Layer (DIL)`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Persistance centralisée des statuts de validation de chaque composant.
* **Règles d’accès ou d’usage** : Passage exclusif par le fragment `AtomicDBWrite`. Interdiction d'usage par les managers locaux.

---

### IPositionProvider
Exposition en lecture seule de l’état des positions.

- Implémenté par : Portfolio Manager
- Utilisé par : Risk Monitor
- Responsabilités :
  - Fournir des snapshots immuables des positions
- Règles :
  - Lecture seule
  - Aucun verrou bloquant
  - Interdiction de modifier les objets exposés

---

### IPortfolioStateReader
Chargement initial du portefeuille.

- Implémenté par : Data Access Layer (DAL)
- Utilisé par : Portfolio Manager
- Responsabilités :
  - Lecture des positions, cash et lots initiaux
- Règles :
  - Lecture seule
  - Aucun accès transactionnel
  - Usage exclusif PHASE1

---

### IRiskStateReader
Chargement initial des données de risque.

- Implémenté par : Data Access Layer (DAL)
- Utilisé par : Risk Monitor
- Responsabilités :
  - Chargement des limites, expositions, seuils
- Règles :
  - Données immuables
  - PHASE1 uniquement
  - Aucune dépendance au Portfolio Manager

---

### IDataIntegrityCheckPort
Validation métier post-chargement.

- Implémenté par : IntegrityCheckService
- Utilisé par : Portfolio Manager, Risk Monitor
- Responsabilités :
  - Validation cohérence métier des données initiales
- Règles :
  - Appel synchrone
  - Aucun accès I/O
  - Retour structuré : OK / WARNING / FAIL
  - Échec propagé immédiatement au System Manager

---

## 2. Configuration & Static Data

### StaticConfigPort
Accès aux configurations globales immuables, hors univers de trading.
* **Implémenté par** : Data Access Layer (DAL)
* **Utilisé par** : System Manager
* **Responsabilités** :
  * Lecture unique des configurations statiques générales (paramètres système, seuils globaux, flags d’activation)
  * **Ne fournit pas l’univers de trading** (liste d’instruments et métadonnées associées → `TradingUniversePort`)
* **Règles** :
  * Bootstrapping uniquement
  * Jamais injecté dans les managers métier
  * Lecture seule, snapshot immuable

---

### TradingUniversePort
* **Implémenté par** : Data Access Layer (DAL) ou tout service fournissant l’univers de trading
* **Injecté dans / Utilisé par** : System Manager
* **Responsabilité opérationnelle** :
  * Fournir la liste complète et à jour des instruments de marché disponibles pour le trading
  * Exposer les métadonnées associées à chaque instrument (type d’instrument, marché, devise, lot size, etc.)
  * Servir de source unique pour la validation et la préparation des flux de données et des abonnements
* **Règles d’accès ou d’usage** :
  * Lecture seule pendant tout le cycle de trading
  * Snapshot immuable pendant les phases critiques (PHASE1, PHASE4)
  * Interdiction d’écriture directe par les consommateurs
  * Toute modification doit passer par un service central de mise à jour de l’univers, versionné et auditable
    
---

### ISessionConfigProvider
Configuration statique par session.

- Implémenté par : Config Service Global
- Utilisé par : System Manager, Order Manager
- Responsabilités :
  - Fourniture des paramètres de session et seuils de risque
- Règles :
  - Lecture seule
  - Aucune modification dynamique autorisée

---

## ICalendarServicePort
  * **Implémenté par** : `Internal Calendar Service`
  * **Injecté dans / Utilisé par** : `System Manager`
  * **Responsabilité opérationnelle** : Déterminer si la date actuelle correspond à une session de trading ouverte selon les calendriers des bourses cibles.
  * **Règles d’accès ou d’usage** : Fournit une réponse booléenne immédiate (calcul in-memory).
  * **Contraintes** : Doit être initialisé avant l'appel à `calculateMarketDayStatus()`.

---

## 3. Market Data & Broker Connectivity

### IMarketDataBootstrapPort

- **Implémenté par** : Broker Gateway (IBKR Gateway)
- **Injecté dans / Utilisé par** : System Manager
- **Responsabilité opérationnelle** :
  - Établissement de la connexion technique au fournisseur de données
  - Initialisation et enregistrement des abonnements marché
- **Règles d’accès ou d’usage** :
  - Appels synchrones uniquement
  - Usage strictement limité au bootstrapping
  - Aucun accès direct aux flux de prix
  - Échec ⇒ CRITICAL_FAILURE immédiat

---

### MarketDataPort
Diffusion des données de marché validées aux consommateurs métier.

* **Implémenté par** : Live Data Hub (LDH Global)
* **Utilisé par** : Portfolio Manager, Risk Monitor, éventuellement Order Manager
* **Responsabilités** :
  * Diffusion des prix, volumes et snapshots de marché **après validation minimale** par le flux d’ingestion (`MarketDataSinkPort`)
  * Fournir un flux stable et immuable pour la consommation métier
* **Règles** :
  * Lecture seule côté consommateurs
  * Objets immuables
  * Timeout et retry gérés au niveau du port
  * Aucun accès direct au DIL
  * **Activation interdite avant validation complète du flux**

---

### MarketDataSinkPort
* **Implémenté par** : Live Data Hub (LDH) ou tout service capable de recevoir et traiter les flux de marché entrants.
* **Injecté dans / Utilisé par** : IBKR Gateway, System Manager (pour orchestration initiale).
* **Responsabilité opérationnelle** :
  * Recevoir les flux de prix bruts provenant de la passerelle du courtier.
  * Acheminer ces données vers le cache interne et les composants consommateurs (Portfolio Manager, Risk Monitor) après validation minimale.
  * Garantir la **séquentialité** et la **complétude** des ticks pour permettre la persistance atomique.
  * Préparer les données pour la distribution aux services de persistance ou de calcul stratégique.
* **Règles d’accès ou d’usage** :
  * Aucun accès direct par PM, RM ou autres consommateurs métiers.
  * Lecture seule côté consommateurs : ils ne doivent jamais écrire dans ce flux.
  * Les écritures doivent passer uniquement par des services producteurs de flux (ex : IBKR Gateway).
  * Gestion des erreurs : tout échec critique dans le traitement doit remonter au System Manager pour déclencher des alertes ou un arrêt sécuritaire.

---
### BrokerGatewayPort
Abstraction du courtier.

- Implémenté par : Gateway externe (IBKR)
- Utilisé par : Order Manager
- Responsabilités :
  - Transmission technique des ordres
  - Réception des callbacks broker
  - Gestion CRITICAL vs STANDARD
- Règles :
  - Aucun accès direct par PM ou RM
  - Encapsulation totale dans l’Order Manager

---

### IExternalConnectivity

* **Implémenté par** : `OrderManager`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Vérification de la liaison physique et logique avec le courtier (Gateway/FIX).
* **Règles d’accès ou d’usage** : Timeout strict de 5000ms. Tout échec est considéré comme une erreur critique en mode LIVE.

---

### IOrderSubmissionPort
Soumission d’ordres critiques.

- Implémenté par : Order Manager
- Utilisé par : Risk Monitor
- Responsabilités :
  - Soumission d’ordres d’urgence / liquidation
- Règles :
  - Exclusivité Risk Monitor
  - Priorité CRITICAL obligatoire

---

### IMarketEventProvider

- **Implémenté par** : `Market Clock`
- **Injecté dans / Utilisé par** : `System Manager`
- **Responsabilité opérationnelle** : Émission de signaux asynchrones basés sur les horaires officiels d'échange et notification des événements de structure de session (MarketOpen, MarketClose, PreOpen).
- **Règles d’accès ou d’usage** : Diffusion en mode "Publish/Subscribe" ou callback asynchrone pour ne pas bloquer l'orchestrateur. Précision milliseconde requise. Doit être auditable via le Log Service dès réception.

---

### IEODHDConnectivityPort

  * **Implémenté par** : `EODHD Service` (External API Gateway)
  * **Injecté dans / Utilisé par** : `System Manager` / `SM-RESILIENT-CHECK-CONNECTION`
  * **Responsabilité opérationnelle** : Vérifier la validité de l'authentification et l'accessibilité de l'API externe EODHD (données de marché historiques/référence).
  * **Règles d’accès ou d’usage** : Appel synchrone. Timeout à configuré.
  * **Contraintes** : Usage strictement limité au bootstrapping.

---

### IMarketDataCacheWriter**
  * **Implémenté par** : Data Cache
  * **Injecté dans / Utilisé par** : Live Data Hub (via fragment 09a)
  * **Responsabilité opérationnelle** : Mise à jour ultra-rapide des `MarketQuotes` agrégés en mémoire vive pour une disponibilité immédiate.
  * **Règles d’accès ou d’usage** : Accès non-bloquant. Priorité `CRITICAL`. Utilisation d'une queue asynchrone pour garantir la faible latence.

---

### ILiveDataOrchestrator**
  * **Implémenté par** : Live Data Hub
  * **Injecté dans / Utilisé par** : System Manager
  * **Responsabilité opérationnelle** : Point d'entrée pour le pilotage du cycle de vie des données de marché (Message 1 : `startMarketDataService`).
  * **Règles d’accès ou d’usage** : Gère la transition vers le mode "In-Trade". Doit confirmer que les deux flux (Fast/Slow) sont opérationnels.

---

## 4. Threading, Jobs & Execution

### IThreadManagerPort
Gestion de la couche d’exécution.

- Implémenté par : Thread Manager
- Utilisé par : System Manager
- Responsabilités :
  - Allocation des pools
  - Démarrage des loops persistantes
  - Reporting de l’état d’initialisation
- Règles :
  - Invocation synchrone uniquement
  - BOOTSTRAP_ONLY
  - Aucun accès direct aux PoolWorkers

---

### IThreadPoolConfigPort
Configuration des pools de threads.

- Implémenté par : Configuration Store
- Utilisé par : Thread Manager
- Responsabilités :
  - Tailles et priorités des pools
- Règles :
  - Lecture seule
  - Disponible avant création des PoolWorkers

---

### IJobTimeoutPolicyPort
Politique de timeout des jobs.

- Implémenté par : Thread Manager
- Utilisé par : PoolWorker
- Responsabilités :
  - Application des délais maximum
- Règles :
  - Timeout dur
  - Aucun retry automatique

---

### IJobStatusReporterPort
Remontée des statuts d’exécution.

- Implémenté par : Thread Manager
- Utilisé par : System Manager
- Responsabilités :
  - Reporting structuré par session
- Règles :
  - Transmission synchrone
  - Aucun agrégat métier

---

## 5. Logging, Audit & Errors

### ILogger
Journalisation globale du système.

- Implémenté par : Logger Global
- Utilisé par : Tous les managers
- Responsabilités :
  - Logs techniques, opérationnels et audit
- Règles :
  - Mode synchrone pour bootstrapping et erreurs fatales
  - Mode non-bloquant en runtime
  - PoolWorkers ne loguent jamais directement

---

### IErrorHandler
Gestion centralisée des erreurs critiques.

- Implémenté par : ErrorService
- Utilisé par : PM, RM, OM, System Manager
- Responsabilités :
  - Classification et propagation des erreurs fatales
- Règles :
  - Écriture seule
  - Appels synchrones pour erreurs critiques
  - Instance unique thread-safe

---

## 6. Health & Monitoring

### IHealthCheckPort
État de santé local des composants.

- Implémenté par : HealthService
- Utilisé par : PM, RM, OM, System Manager
- Responsabilités :
  - Vérification des threads, files et dépendances
- Règles :
  - Aucun I/O bloquant
  - Appel hors chemin critique

---

### IMarketDataHealthPort

- **Implémenté par** : Live Data Hub (LDH)
- **Injecté dans / Utilisé par** : System Manager
- **Responsabilité opérationnelle** :
  - Validation de la preuve de vie du flux de données marché
  - Vérification de la couverture des instruments requis
  - Contrôle de la fraîcheur des ticks reçus
- **Règles d’accès ou d’usage** :
  - Appel synchrone avec timeout dur
  - Aucune opération I/O externe bloquante
  - Logique de validation strictement encapsulée
  - Échec ⇒ arrêt immédiat du système
    
---

### IBootstrapReadinessCheck
* **Implémenté par** : `PortfolioManager`, `RiskMonitor`, `OrderManager`, `LiveDataHub`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Validation de l'intégrité technique (instanciation des structures, état des threads, readiness local).
* **Règles d’accès ou d’usage** : Appel synchrone obligatoire en Phase 1. Interdiction de mutation d'état (Read-Only technique).

---

### ICrossValidator
* **Implémenté par** : `PortfolioManager`, `RiskMonitor`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Validation de la cohérence métier inter-domaines (compatibilité Risk Limits vs Portfolio State).
* **Règles d’accès ou d’usage** : Exclusivité au bootstrap. Dépendance requise aux données de marché pour validation des seuils.

---

### HCheckPriorityInterface
Validation OS de la priorité temps réel.

- Implémenté par : Thread Manager
- Utilisé par : PoolWorker CRITICAL_POOL
- Responsabilités :
  - Vérifier que l’OS respecte la priorité maximale
- Règles :
  - Bootstrapping uniquement
  - Échec ⇒ CRITICAL_FAILURE immédiat

---

### IDatabaseConnectivityPort
  * **Implémenté par** : `Database Service` (Infrastructure Layer)
  * **Injecté dans / Utilisé par** : `System Manager` / `SM-RESILIENT-CHECK-CONNECTION`
  * **Responsabilité opérationnelle** : Fournir une preuve de vie (Heartbeat) et valider la disponibilité du pool de connexions à la base de données principale.
  * **Règles d’accès ou d’usage** : Appel synchrone obligatoire au démarrage. Timeout à configuré.
  * **Contraintes** : Ne doit effectuer aucune lecture métier à ce stade, uniquement un test de liaison (`ping`).

---

## 7. Commands (Bootstrapping)

### ILoadPortfolioStateCommand
Job de chargement initial du portefeuille.

- Implémenté par : Portfolio Manager
- Utilisé par : Thread Manager
- Règles :
  - Un job par session
  - Exécution unique
  - Timeout obligatoire

---

### ILoadRiskStateCommand
Job de chargement initial du risque.

- Implémenté par : Risk Monitor
- Utilisé par : Thread Manager
- Règles :
  - Un job par session
  - Isolation stricte entre sessions


---

### IBootstrapCoordinator
* **Implémenté par** : `SystemManager`
* **Injecté dans / Utilisé par** : Bootstrap Thread / Main Entry
* **Responsabilité opérationnelle** : Arbitrage final des statuts collectés et transition vers l'état `READY_FOR_TRADING`.
* **Règles d’accès ou d’usage** : Logique de "Fail-fast". Exécution prioritaire sur le pool de threads `CRITICAL`.

---

## 8. Notification & Alerting (New)

### INotificationService
Service d'alerte externe (Hors-Log).
* **Implémenté par** : AlertingService (Email, SMS, PagerDuty)
* **Utilisé par** : Monitor, SystemManager
* **Responsabilité opérationnelle** : 
  * Envoi immédiat d'alertes critiques aux opérateurs humains.
  * Doit être non-bloquant (Asynchrone).
* **Règles d’accès ou d’usage** : 
  * Usage limité aux erreurs de sévérité CRITICAL ou FATAL.
  * Ne remplace pas le Logger (Audit technique).

---

## 9. System Control & Lifecycle

**IProcessControlPort**
  * **Implémenté par** : `Runtime Environment` / `System Manager`
  * **Injecté dans / Utilisé par** : `System Manager`
  * **Responsabilité opérationnelle** : Gérer les transitions d'état de vie du processus, notamment l'arrêt immédiat en cas d'erreur fatale ou la mise en veille.
  * **Règles d’accès ou d’usage** : Invoqué via `systemStop(CRITICAL_ERROR)` ou `transitionTo(Off-Cycle)`.
  * **Contraintes** : L'appel à `systemStop` doit être atomique et garantir la fermeture des descripteurs de fichiers ouverts.

---

## Règle de Gouvernance

- Toute nouvelle interface doit :
  1. Être comparée à ce catalogue
  2. Être ajoutée ici avant usage
  3. Être référencée ensuite dans les séquences UML
- Une interface = une responsabilité claire
- Aucun doublon fonctionnel toléré
