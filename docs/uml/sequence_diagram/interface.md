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
Accès aux configurations globales immuables.

- Implémenté par : Data Access Layer (DAL)
- Utilisé par : System Manager
- Responsabilités :
  - Lecture unique des configurations statiques
- Règles :
  - Bootstrapping uniquement
  - Jamais injecté dans les managers métier

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

## 3. Market Data & Broker Connectivity

**IMarketDataBootstrapPort**
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

### MarketDataPort
Diffusion des données de marché.

- Implémenté par : Live Data Hub (LDH Global)
- Utilisé par : Portfolio Manager, Risk Monitor, éventuellement Order Manager
- Responsabilités :
  - Prix, volumes, snapshots de marché
- Règles :
  - Lecture seule
  - Objets immuables
  - Timeout et retry gérés au niveau du port
  - Aucun accès DIL

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

## Règle de Gouvernance

- Toute nouvelle interface doit :
  1. Être comparée à ce catalogue
  2. Être ajoutée ici avant usage
  3. Être référencée ensuite dans les séquences UML
- Une interface = une responsabilité claire
- Aucun doublon fonctionnel toléré
