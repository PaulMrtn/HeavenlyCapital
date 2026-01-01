## `04-PHASE1-Instanciation-Managers-Locaux`

<p align="center">
  <img src="../img/04-PHASE1-Instanciation-Managers-Locaux.jpg" width="900">
</p>


### 1. Objectif

La finalité de ce module est d'allouer la couche d'exécution métier du système en instanciant **toutes les sessions de trading actives**. Cela comprend la création, l'injection de dépendances et la liaison des triplets de managers locaux (**Portfolio Manager**, **Risk Monitor**, **Order Manager**) pour chaque stratégie. L'objectif est de garantir qu'avant tout chargement de données, incluant les oracles ML, la structure logique de décision et de sécurité est opérationnelle, isolée et supervisée. Cette étape assure également que chaque session dispose de ses propres modèles d'inférence immuables pour valider les signaux d'exécution en temps réel.

---

### 2. Contexte

Cette étape s'inscrit immédiatement après l'initialisation des services d'infrastructure persistants (Singletons globaux, Pools de Threads, `HealthService`, `ErrorService`). Elle constitue le pont entre l'infrastructure globale et l'exécution spécifique à une stratégie. Elle lie la logique de décision (**PM**) aux ressources d'exécution (**IG**, **LDH**) et au mécanisme de protection d'urgence (**RM**) tout en intégrant les modèles ML chargés depuis le système de fichiers. L'intégrité de ces modèles est vérifiée avant leur injection définitive dans les managers métier.

---

### 3. Logique Générale

Le **System Manager** orchestre une boucle itérative pour chaque identifiant de session récupéré depuis le `StaticConfigPort`. Le processus suit cet ordre strict pour garantir l'intégrité des liens :

1. **Récupération des Paramètres :** Extraction des seuils de risque et paramètres via `getConfigs(SessionID)`.
2. **Création Identitaire :** Instanciation de `TradingSession` (ID, MarketDayStatus) pour porter l'état local.
3. **Allocation des Managers (Injection par Constructeur) :**
  * **PM :** Créé avec son identifiant et les ports `ISessionPersistence` (DIL) et `IErrorHandler`.
  * **OM :** Créé avec la référence `IBKR Gateway` et les ports `IOrderRepository` (DIL) et `IErrorHandler`.
  * **RM :** Créé en dernier car il nécessite les références du PM (via `IPositionProvider`) et de l'OM (via `IOrderSubmissionPort`).
4. **Liaison des Canaux (Linking) :**
  * Le **System Manager** injecte l'OM dans le PM via `setOrderManager(OM)` pour établir le canal de **Performance**.
  * Le **System Manager** injecte le PM dans le RM via `setPortfolioReference(PM)` pour permettre la surveillance.
5. * **Allocation des Oracles ML (Injection par Constructeur) :**
  * Le **System Manager** résout les chemins des artefacts ML via la configuration statique (ModelID + Version).
  * Il instancie les modèles de décision locaux et les injecte dans les managers respectifs.
  * Chaque instance est locale à la session, garantissant une isolation stricte et l'absence de contention.
6. **Instanciation du Port de Santé :** Création d'un `IHealthCheckPort` dédié au triplet pour l'audit programmatique local.
7. **Vérification de Readiness :** Appel à `HCheckSessionReady(ID)` pour valider que tous les fils sont branchés et les threads alloués.

---

### 4. Règles Critiques

* **Renforcement de l’Injection :** Pour tous les ports critiques (`IOrderSubmissionPort`, `IPositionProvider`, `IErrorHandler`), l'injection par **constructeur** est obligatoire. Les setters sont réservés aux liaisons de second rang pour éviter les dépendances cycliques.
* **Isolation RM/PM (Non-Blocking) :** Pour garantir la réactivité absolue de la surveillance d'urgence, le **Risk Monitor** ne possède jamais de référence directe vers la logique interne du PM. Il accède à l'état des positions via le port **`IPositionProvider`** qui fournit des **Snapshots immuables**. Cela empêche tout blocage du RM par un verrou (lock) ou une contention mémoire issus du PM.
* **Segmentation des Pools d'Exécution :**
* **RM :** S'exécute sur le `RM_CRITICAL_POOL` (priorité absolue).
* **PM :** S'exécute sur le `STRATEGY_POOL` (calculs métier).
* **OM :** S'exécute sur le `IO_POOL` (gestion réseau et persistance).
* **Immutabilité des Oracles :** Une fois injectés, les modèles `IExecutionDecisionModel` et `IStopPredictionModel` sont strictement en lecture seule. Ils ne possèdent aucun état mutable et n'effectuent aucun apprentissage en ligne.
* **Pureté Fonctionnelle :** Les modèles ML agissent comme des fonctions pures (Market Data In  Boolean Out). Ils n'ont aucun accès aux ports de persistance ou de connectivité broker.
* **Isolation ML/Manager :** Le **Portfolio Manager** et le **Risk Monitor** possèdent leurs propres instances de modèles. Un manager ne peut jamais invoquer le modèle d'un autre composant.
* **Abstraction du Port de Persistance :** Les managers n'ont aucun couplage avec le **Data Integrity Layer (DIL)**. Ils utilisent des interfaces métier. Les appels vers ces ports sont obligatoirement routés vers le `BULK_POOL` ou le `AUDIT_POOL` via des méthodes transactionnelles (`startTransaction`, `commit`).
* **Centralisation Fail-Fast :** Le port **`IErrorHandler`** injecté dans chaque manager est le seul canal autorisé pour les remontées critiques. En cas d'erreur fatale, il déclenche l'arrêt immédiat de la session sans tentative de "retry" interne.
* **Couplage Minimal :** Le RM n'écrit jamais dans le PM. L'OM n'accède jamais au PM. Tout échange se fait via des ports standardisés.

---

### 5. Conclusion

Ce module garantit que l'architecture métier est instanciée et que tous les **canaux de communication critiques** (Ordres, Surveillance, Données) entre les composants locaux sont établis. La structure du système est ainsi **isolée et sécurisée**, prête à charger les données initiales et à passer en mode veille de trading.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | getSessionsToLoad() | System Manager | Config | Récupération de la liste des sessions actives. |
| 2 | new TradingSession(ID, Status) | System Manager | TradingSession | Création de l'entité identitaire de la session. |
| 3 | getConfigs(SessionID) | System Manager | Config | Extraction des seuils et paramètres spécifiques. |
| 4 | new PM(ID, Config, LDH, IPersist, IExecModel) | System Manager | Portfolio Manager | Injection du modèle de décision d'exécution (Achat/Vente). |
| 5 | new RM(ID, Config, LDH, IStopModel) | System Manager | Risk Monitor | Injection du modèle de prédiction Stop-Loss anticipé. |
| 6 | new OM(S, IG, IPersistencePort) | System Manager | Order Manager | **Correction** : Injection du port de persistance pour les logs d'ordres et Fills. |
| 7-9 | Setters (OM, PM) | System Manager | PM / RM | Établissement des canaux de communication inter-composants. |
| 10 | HCheckSessionReady(ID) | System Manager | System Manager | Validation d'intégrité de l'instanciation. |
| alt | [HCheck == FAILED] | System Manager | System Manager | Branche de sortie critique vers systemStop(ERROR). |
| 11 | call_05-PHASE1... | System Manager | System Manager | Poursuite du bootstrapping. |

---

### 6. Ports et Interfaces

**PersistencePort**
* **Implémenté par :** Data Integrity Layer (DIL) / AtomicDBWriteProcess
* **Injecté dans :** Portfolio Manager (PM), Order Manager (OM), Live Data Hub (LDH) si nécessaire
* **Responsabilité :** Point unique d’accès pour toute persistance critique du système :
  * Snapshots de positions et portefeuilles
  * Journaux de sessions et SessionBooks
  * Ordres et exécutions (Fills)
  * États courants du système métier
* **Règles d’accès :**
  * Accès direct au DIL interdit en dehors de ce port
  * Persistance **atomique** obligatoire : startTransaction / commit / rollback
  * Isolation stricte : aucun module externe ne peut modifier ou lire directement les objets métier sans passer par ce port
  * Supporte les écritures synchronisées et sécurisées pour les opérations critiques
* **Phase d’utilisation :**
  * Bootstrapping et runtime métier, selon contexte
  * Tous accès critiques doivent transiter par ce port
* **Objectif :** Assurer la cohérence, atomicité et auditabilité des données critiques à travers tout le système
**Port : IPositionProvider**
  * **Implémenté par :** Portfolio Manager.
  * **Injecté dans :** Risk Monitor (et tout module en lecture seule).
  * **Responsabilité :** Fournir des snapshots immuables (`PositionSnapshot`) des positions en temps réel.
  * **Règles d’usage :** **Lecture seule.** Aucun verrou (lock) bloquant autorisé. Interdiction de modifier les objets exposés.

**BrokerGatewayPort**
* **Implémenté par :** Gateway externe IBKR
* **Injecté dans :** Order Manager (OM)
* **Responsabilité :**
  * Abstraction complète de la communication avec le broker
  * Transmission technique des ordres et réception des callbacks
  * Gestion de la priorité des ordres (`CRITICAL` vs `STANDARD`)
* **Règles d’usage :**
  * Aucun accès direct autorisé par PM ou RM (tout passe par OM)
  * Le Risk Monitor soumet les ordres urgents via **IOrderSubmissionPort**, qui délègue ensuite vers le **BrokerGatewayPort** dans OM
* **Objectif :** Isoler le courtier des modules métier tout en permettant le passage sécurisé des ordres critiques et standards

**Port : MarketDataPort**
  * **Implémenté par :** LDH Global.
  * **Injecté dans :** Portfolio Manager, Risk Monitor.
  * **Responsabilité :** Diffusion des flux de marché (Prix, Volume) en lecture seule.
  * **Règles d’usage :** Accès immuable. Interdiction de modification. Politiques de `Timeout` et `Retry` appliquées au niveau du port pour protéger l'appelant.

**IOrderSubmissionPort**
- Implémenté par : Order Manager (OM)
- Injecté dans : Risk Monitor (RM)
- Responsabilité : Soumission prioritaire d’ordres d’urgence et de liquidation
- Règles :
  - Exclusivité RM
  - Messages doivent porter le flag CRITICAL pour bypasser la file standard

**Port : ILogger**
  * **Implémenté par :** Logger Global.
  * **Injecté dans :** PM, RM, OM, System Manager.
  * **Responsabilité :** Journalisation technique et audit de conformité.
  * **Règles d’usage :** Non-bloquant. Ne doit jamais impacter les threads critiques d'exécution. Respect rigoureux des niveaux de priorité d'audit.

**Port : ISessionConfigProvider**
  * **Implémenté par :** Config Service Global.
  * **Injecté dans :** System Manager, Order Manager.
  * **Responsabilité :** Fournir les paramètres statiques et les seuils de risque par session.
  * **Règles d’usage :** **Lecture seule.** Pas de modification dynamique autorisée pendant la session de trading.

**Port : IHealthCheckPort**
  * **Implémenté par :** HealthService (Infrastructure Layer).
  * **Injecté dans :** PM, RM, OM, System Manager.
  * **Responsabilité :** Exposer l’état de santé des threads, des files d'attente et des dépendances critiques.
  * **Règles d’usage :** Appel autorisé uniquement hors chemin critique (hors boucle de calcul). État calculé localement sans I/O bloquante. Cycle de vie aligné sur le manager hôte.

**Port : IErrorHandler**
  * **Implémenté par :** ErrorService (Core Infrastructure).
  * **Injecté dans :** PM, RM, OM.
  * **Responsabilité :** Centralisation des erreurs critiques, classification de sévérité et déclenchement des protocoles **Fail-Fast**.
  * **Règles d’usage :** **Écriture uniquement.** Appels synchrones pour les erreurs fatales uniquement. Interdiction de "Retry" interne au port. Instance unique, partagée et Thread-Safe.

**IExecutionDecisionModel**
* **Implémenté par :** Modèles ML chargés (XGBoost, Régression, etc.).
* **Injecté dans :** Portfolio Manager.
* **Responsabilité :** Oracle de décision. Détermine si le prix actuel permet l'exécution d'un ordre planifié via `shouldExecute(last_price)`.
* **Règles :** Déterministe, sans effet de bord, aucun accès I/O.

**IStopPredictionModel**
* **Implémenté par :** Modèles ML de risque chargés.
* **Injecté dans :** Risk Monitor.
* **Responsabilité :** Anticipation de sortie. Détermine si une liquidation préventive est requise avant l'atteinte mécanique du stop-loss via `shouldLiquidate(last_price)`.
* **Règles :** Indépendant de la logique du Portfolio Manager.
