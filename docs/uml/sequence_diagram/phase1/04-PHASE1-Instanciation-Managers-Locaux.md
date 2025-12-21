## `04-PHASE1-Instanciation-Managers-Locaux`

<p align="center">
  <img src="../img/04-PHASE1-Instanciation-Managers-Locaux.jpg" width="900">
</p>


### 1. Objectif

La finalité de ce module est d'allouer la couche d'exécution métier du système en instanciant **toutes les sessions de trading actives**. Cela comprend la création et la liaison des triplets de managers locaux (**Portfolio Manager**, **Risk Monitor**, **Order Manager**) pour chaque stratégie.

---

### 2. Contexte

Cette étape s'inscrit après l'initialisation des **services d'infrastructure persistants** (Singletons, Pools de Threads) et avant le chargement des données. Elle est cruciale car elle **lie la stratégie (PM)** aux **ressources globales (LDH, IG)** et au **mécanisme de sécurité (RM)**. Elle prépare la structure logique qui opèrera pendant la session de trading.

---

### 3. Logique Générale

Le **`System Manager`** orchestre une boucle itérative pour chaque identifiant de session récupéré dans la configuration. Pour chaque session :

1.  L'entité **`TradingSession`** est créée pour détenir l'identité et l'état local de la stratégie.
2.  Les trois managers locaux (`PM`, `RM`, `OM`) sont instanciés en **injectant leurs dépendances minimalistes** (configurations et Singletons globaux nécessaires).
3.  Les **canaux de communication locaux** sont établis :
    * Le **`PM` est lié à l'`OM`** pour la soumission d’ordres d’investissement (selon une stratégie définie).
    * Le **`RM` est lié à l'`OM`** pour l'émission d'ordres d'urgence (Stop-Loss).
    * Le **`RM` obtient la référence du `PM`** (`setPortfolioReference`) pour la lecture de l'état du portefeuille (position) et le déclenchement du **Kill Switch** asynchrone.
4.  Une vérification d'intégrité minimale (**`HCheckSessionReady`**) est effectuée pour s'assurer que tous les canaux critiques sont correctement établis avant de passer à l'étape suivante.

---

### 4. Règles Critiques

* **Couplage Faible :** Le **`Portfolio Manager`** est maintenu **minimaliste**. Il ne dépend pas de l'`IBKR Gateway` ou du `Risk Monitor` pour son exécution principale.
* **Séparation des Canaux :** Le chemin de la **performance** (`PM` $\rightarrow$ `OM`) est distinct du canal de la **sécurité** (`RM` $\rightarrow$ `OM`). La vérification de risque par le `RM` est hors-bande.
* **Isolation du Risque :** La création d'un **triplet de managers par session** garantit qu'un dysfonctionnement dans une stratégie ne peut pas compromettre les autres sessions actives.
* **Lien de Surveillance :** Le **`RM`** doit avoir une référence active et persistante au **`PM`** pour pouvoir lire la position mise à jour (nécessaire à la construction de l'ordre de liquidation) et pour exécuter l'arrêt d'urgence.

---

### 5. Conclusion

Ce module garantit que l'architecture métier est instanciée et que tous les **canaux de communication critiques** (Ordres, Surveillance, Données) entre les composants locaux sont établis. La structure du système est ainsi **isolée et sécurisée**, prête à charger les données initiales et à passer en mode veille de trading.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | getSessionsToLoad() | System Manager | Config | Récupération de la liste des sessions actives. |
| 2 | new TradingSession(ID, Status) | System Manager | TradingSession | Création de l'entité identitaire de la session. |
| 3 | getConfigs(SessionID) | System Manager | Config | Extraction des seuils et paramètres spécifiques. |
| 4 | new PM(S, C, LDH, IPersistencePort) | System Manager | Portfolio Manager | **Correction** : Injection de l'interface de persistance pour les SessionBooks. |
| 5 | new RM(S, C, LDH) | System Manager | Risk Monitor | Création du moniteur de risque (lecture seule LDH/PM). |
| 6 | new OM(S, IG, IPersistencePort) | System Manager | Order Manager | **Correction** : Injection du port de persistance pour les logs d'ordres et Fills. |
| 7-9 | Setters (OM, PM) | System Manager | PM / RM | Établissement des canaux de communication inter-composants. |
| 10 | HCheckSessionReady(ID) | System Manager | System Manager | Validation d'intégrité de l'instanciation. |
| alt | [HCheck == FAILED] | System Manager | System Manager | Branche de sortie critique vers systemStop(ERROR). |
| 11 | call_05-PHASE1... | System Manager | System Manager | Poursuite du bootstrapping. |

---

### 6. Ports et Interfaces

**Port : ISessionPersistence**

* Implémenté par : DIL / AtomicDBWriteProcess
* Injecté dans : Portfolio Manager, Order Manager
* Responsabilité opérationnelle : Persistance atomique des SessionBooks et logs d’ordres/fills
* Règles d’usage : Accès exclusif via thread pool AUDIT_POOL ou BULK_POOL. Support startTransaction / commit / rollback. Aucun accès direct aux objets métier.

**Port : IOrderRepository**

* Implémenté par : DIL / AtomicDBWriteProcess
* Injecté dans : Order Manager
* Responsabilité opérationnelle : Persistance des ordres et exécutions
* Règles d’usage : Transaction atomique obligatoire. Accès via BULK_POOL. Ne pas exposer les données aux modules externes.

**Port : IPositionProvider**

* Implémenté par : Portfolio Manager
* Injecté dans : Risk Monitor, autres modules lecture seule
* Responsabilité opérationnelle : Fournir des snapshots immuables des positions
* Règles d’usage : Lecture seule. Aucun verrou bloquant. Pas de modification des objets exposés.

**Port : IOrderSubmissionPort**

* Implémenté par : Order Manager
* Injecté dans : Risk Monitor
* Responsabilité opérationnelle : Soumission d’ordres d’urgence et liquidation
* Règles d’usage : Seul RM peut soumettre via ce port. Respecter la priorité CRITICAL.

**Port : IBrokerGateway**

* Implémenté par : Gateway externe IBKR
* Injecté dans : Order Manager
* Responsabilité opérationnelle : Transmission des ordres au courtier
* Règles d’usage : Priorisation CRITICAL vs STANDARD. Aucun accès direct par PM ou RM.

**Port : ILiveDataHub**

* Implémenté par : LDH global
* Injecté dans : Portfolio Manager, Risk Monitor
* Responsabilité opérationnelle : Fournir flux de marché en lecture seule
* Règles d’usage : Accès immuable. Ne jamais modifier les données. Timeout et retry appliqués sur chaque appel.

**Port : ILogger / IAuditLogger**

* Implémenté par : Logger global
* Injecté dans : PM, RM, OM, System Manager
* Responsabilité opérationnelle : Journalisation synchronisée et asynchrone
* Règles d’usage : Ne pas exposer aux threads critiques d’exécution métier. Respect des priorités d’audit.

**Port : ISessionConfigProvider**

* Implémenté par : Config Service global
* Injecté dans : System Manager, OM
* Responsabilité opérationnelle : Fournir les paramètres et seuils par session
* Règles d’usage : Lecture seule. Pas de modification dynamique. Utilisation uniquement au démarrage ou lors de refresh contrôlé.

---

### NOTE

**Port de Persistance** : Pour éviter le couplage direct avec le Data Ingestion Layer (DIL), les managers (PM, OM) utilisent désormais des interfaces métier (ex: ISessionPersistence, IOrderRepository). Le DIL agit comme l'adaptateur concret implémentant ces interfaces. Cette abstraction garantit que la logique métier de trading reste isolée des mécanismes de stockage (SQL, NoSQL ou Fichier), facilitant l'injection de Mocks lors des tests de performance. Les appels passés par ces ports devront obligatoirement être routés vers le BULK_POOL ou le AUDIT_POOL pour ne pas ralentir le thread d'exécution métier. Il faudra s'assurer que l'instance du DIL injectée comme Port possède bien les méthodes atomiques requises (startTransaction, commit) pour supporter les flux de la Phase IV.


**Isolation RM/PM** : Pour garantir la réactivité absolue de la surveillance d'urgence (Phase II), le Risk Monitor ne doit jamais posséder de référence directe vers le Portfolio Manager. L'accès à l'état des positions s'effectue exclusivement via un Port de Lecture Read-Only (`IPositionProvider`). Ce port doit exposer une vue immuable ou un Snapshot de l'état (ex: PositionSnapshot), garantissant que le fil d'exécution du RM ne sera jamais bloqué par un verrou (lock), une contention mémoire ou une propagation d'I/O provenant du PM.
