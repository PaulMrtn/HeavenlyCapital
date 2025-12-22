## `05-PHASE1-Chargement-Parallele`

<p align="center">
  <img src="../img/05-PHASE1-Chargement-Parallele.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de charger l'état initial complet de toutes les sessions de trading **en parallèle**. Il vise à minimiser le temps de latence au démarrage en exploitant la parallélisation des opérations de lecture en base de données (I/O) de manière concurrente.

---

### 2. Contexte

Cette étape intervient immédiatement après l'**instanciation des managers locaux** (Phase 04) et s'appuie sur les **Pools de Threads** (initialisés en Phase 03). Elle constitue la première phase opérationnelle utilisant le parallélisme pour préparer le **Portfolio Manager (PM)** et le **Risk Monitor (RM)** avec les données nécessaires à leur activation.

---

### 3. Logique Générale

Le **System Manager** orchestre la phase en déléguant la charge de travail au **Thread Manager**. Pour chaque session active, le processus suit une séparation stricte entre les phases I/O et CPU pour garantir l'observabilité.

 **Création et Soumission**
  * Deux commandes de travail (`Job`) sont créées par session : une via **ILoadPortfolioStateCommand** et une via **ILoadRiskStateCommand**.
  * Le **SessionType** (LIVE ou PAPER) est impérativement attaché au job dès sa création pour définir les règles de résilience.
  * Les commandes sont soumises au **Thread Manager** pour exécution.

**Phase de Chargement (I/O Uniquement)**
  * Des **PoolWorkers** distincts exécutent les tâches simultanément.
  * Le **PM** utilise **IPortfolioStateReader** pour charger les positions et le cash (Lecture seule, sans accès transactionnel).
  * Le **RM** utilise **IRiskStateReader** pour charger les snapshots de risques (Données immuables).
  * Ces opérations sollicitent le **Database Connector** de manière concurrente.

**Phase de Validation (CPU Uniquement)**
  * Cette phase ne démarre que si **tous les chargements d'une session sont en succès**.
  * Chaque manager sollicite le port **IDataIntegrityCheckPort** pour effectuer son contrôle d'intégrité métier (**HCheckDataIntegrity**).
  * Cette étape valide la cohérence logique (ex: somme des lots vs position totale) sans aucun accès I/O supplémentaire.

**Consolidation**
  * Le **Thread Manager** consolide les résultats via **IJobStatusReporterPort** et renvoie une **JobStatusList** au System Manager pour la clôture de la phase.

---

### 4. Règles Critiques

* **I/O Maximisation :** Le parallélisme est utilisé pour masquer la latence des opérations I/O bloquantes de la base de données.
* **Vérification Métier :** Le **`HCheckDataIntegrity`** est un garde-fou. Il assure la **cohérence logique** des données (ex. : la somme des lots correspond à la position totale) avant la mise en service du manager.
* **Non-Blocage :** Le thread du **System Manager** est libéré dès la soumission des tâches au Thread Manager. Il ne doit jamais être bloqué par l'attente des réponses de la base de données.
* **Propagation Immédiate (Fail-Fast) :** Toute erreur classée **FATAL** doit être transmise immédiatement via **IErrorHandler**. Ce signal court-circuite l'attente des autres jobs de la session pour déclencher une action corrective immédiate.
* **Gestion d'Erreur Différenciée :** Le Thread Manager applique les règles d'arrêt selon le **SessionType** :
  * **LIVE :** Tout échec entraîne un arrêt global via `systemStop(CRITICAL_ERROR)`.
  * **PAPER :** L'échec entraîne l'invalidation de la session spécifique, mais le processus global continue.
* **Timeouts :** L'interface **IJobTimeoutPolicyPort** impose un délai maximum d'exécution. En cas de dépassement, le job est marqué en échec (FAILURE) sans tentative de retry automatique.
* **Disponibilité :** Le port **IHealthCheckPort** doit être interrogé avant le lancement pour s'assurer de la santé locale des managers, sans I/O bloquant.

---

### 5. Conclusion

Ce module garantit un démarrage rapide et résilient en gérant efficacement la latence I/O.
**Trace d'Audit :** À la clôture de la PHASE 1, une trace d'audit est obligatoirement émise pour chaque session. Les états possibles, essentiels pour le diagnostic post-mortem, sont strictement :
  * **`SESSION_READY`** : Chargement et intégrité validés.
  * **`SESSION_DISABLED`** : Session invalidée suite à un échec de chargement ou de validation (cas PAPER).
Le succès de cette étape permet la transition vers l'initialisation du flux de données temps réel.

---

### 6. Ports et Interfaces

**IPortfolioStateReader**
- **Implémenté par** : Data Access Layer (DAL)
- **Injecté dans / Utilisé par** : Portfolio Manager
- **Responsabilité opérationnelle** : Chargement en lecture seule de l’état initial du portefeuille (positions, cash, lots)
- **Règles d’accès ou d’usage** :
  - Lecture seule
  - Interdiction totale d’écriture
  - Appel autorisé uniquement durant PHASE1
  - Aucun accès transactionnel

**IRiskStateReader**
- **Implémenté par** : Data Access Layer (DAL)
- **Injecté dans / Utilisé par** : Risk Monitor
- **Responsabilité opérationnelle** : Chargement des snapshots de risque initiaux (limites, expositions, seuils)
- **Règles d’accès ou d’usage** :
  - Données immuables
  - Aucun recalcul dynamique
  - Usage exclusif PHASE1
  - Interdiction de dépendance au PM

**ILoadPortfolioStateCommand**
- **Implémenté par** : Portfolio Manager
- **Injecté dans / Utilisé par** : Thread Manager
- **Responsabilité opérationnelle** : Encapsulation du chargement initial du portefeuille sous forme de job exécutable
- **Règles d’accès ou d’usage** :
  - Un job par session
  - Exécution unique
  - Timeout obligatoire
  - Retour d’un JobStatus typé

**ILoadRiskStateCommand**
- **Implémenté par** : Risk Monitor
- **Injecté dans / Utilisé par** : Thread Manager
- **Responsabilité opérationnelle** : Encapsulation du chargement initial des données de risque
- **Règles d’accès ou d’usage** :
  - Un job par session
  - Exécution unique
  - Timeout obligatoire
  - Isolation totale entre sessions

**IDataIntegrityCheckPort**
- **Implémenté par** : IntegrityCheckService (Core)
- **Injecté dans / Utilisé par** : Portfolio Manager, Risk Monitor
- **Responsabilité opérationnelle** : Validation métier post-chargement des données initiales
- **Règles d’accès ou d’usage** :
  - Appel synchrone
  - Aucun accès I/O
  - Retour structuré (OK / WARNING / FAIL)
  - Échec ⇒ propagation immédiate au System Manager

**IJobTimeoutPolicyPort**
- **Implémenté par** : Thread Manager
- **Injecté dans / Utilisé par** : PoolWorker
- **Responsabilité opérationnelle** : Application des délais maximum d’exécution par job
- **Règles d’accès ou d’usage** :
  - Timeout dur
  - Dépassement ⇒ JobStatus.FAILURE
  - Aucun retry automatique

**IJobStatusReporterPort**
- **Implémenté par** : Thread Manager
- **Injecté dans / Utilisé par** : System Manager
- **Responsabilité opérationnelle** : Remontée structurée des statuts d’exécution par session
- **Règles d’accès ou d’usage** :
  - Chaque statut doit contenir SessionID
  - Aucun agrégat métier
  - Transmission synchrone en fin de batch

**IHealthCheckPort**
- **Implémenté par** : HealthService (Infrastructure Layer)
- **Injecté dans / Utilisé par** : Portfolio Manager, Risk Monitor
- **Responsabilité opérationnelle** : Vérification locale de disponibilité avant lancement des jobs
- **Règles d’accès ou d’usage** :
  - Appel obligatoire avant soumission au Thread Manager
  - Aucun I/O bloquant
  - Usage interdit en boucle temps réel

**IErrorHandler**
- **Implémenté par** : ErrorService (Core Infrastructure)
- **Injecté dans / Utilisé par** : Portfolio Manager, Risk Monitor
- **Responsabilité opérationnelle** : Centralisation des erreurs critiques durant le chargement parallèle
- **Règles d’accès ou d’usage** :
  - Écriture seule
  - Appel synchrone pour erreurs fatales
  - Interdiction de retry interne




