## `05-PHASE1-Chargement-Parallele`

<p align="center">
  <img src="../img/05-PHASE1-Chargement-Parallele.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de charger l'état initial complet de chaque session de trading de manière **séquentielle et isolée**. Il vise à garantir l'intégrité absolue des données au démarrage en centralisant les opérations de lecture en base de données (I/O) et les contrôles métier au niveau de chaque manager local. Cette approche simplifiée assure une transition robuste vers la phase opérationnelle en validant la cohérence des snapshots de portefeuille et de risque avant toute activation.

---

### 2. Contexte

Cette étape intervient immédiatement après l'**instanciation des managers locaux** (Phase 04). Elle constitue la première phase opérationnelle de récupération de données réelles, où chaque **Trading Session** prépare son **Portfolio Manager (PM)** et son **Risk Monitor (RM)** avec les informations d'état nécessaires à leur activation.

---

### 3. Logique Générale

Le **Session Manager** orchestre la phase en itérant sur chaque **Trading Session** active. Le processus suit une séparation stricte entre la récupération des données (I/O) et la validation métier (CPU).

**Phase de Chargement (I/O Uniquement)**
  * Chaque **Trading Session** pilote l'injection de données depuis la base de données vers ses composants internes.
  * Le **PM** et le **RM** effectuent des requêtes de lecture synchrones via le **Data Access Layer** pour récupérer les snapshots de positions et de limites.
  * En cas d'erreur technique majeure (base de données injoignable), un rapport **FATAL** est immédiatement transmis à l'**Error Service**.

**Phase de Validation (CPU Uniquement)**
  * Une fois les données (DTO) réceptionnées, chaque manager effectue son contrôle d'intégrité métier (**HCheckDataIntegrity**).
  * Cette étape valide la cohérence logique (ex: somme des lots vs position totale) sans aucun accès I/O supplémentaire.
  * Si un manager renvoie un statut **FAILED**, la session est immédiatement marquée pour annulation.

**Consolidation et Arbitrage**
  * Le **Session Manager** consolide les statuts de chaque `Trading Session` via `evaluateBootstrapStatus`.
  * Le système applique alors les règles de résilience selon le mode de la session (LIVE ou PAPER).


---

### 4. Règles Critiques

* **Isolation Sessionnelle :** Chaque `Trading Session` gère ses propres échecs ; une erreur dans une session ne doit pas corrompre les données d'une autre.
* **Vérification Métier :** Le `HCheckDataIntegrity` est obligatoire. Tout écart logique détecté post-chargement entraîne l'invalidation du manager.
* **Fail-Fast Différencié :**
  * **LIVE :** Tout échec de chargement ou d'intégrité déclenche un `systemStop(CRITICAL_ERROR)` global.
  * **PAPER :** La session est annulée (`SESSION_DISABLED`), mais le `Session Manager` poursuit le bootstrap des autres sessions.
* **Traçabilité d'Audit :** Chaque session doit finir dans l'un des deux états terminaux : `SESSION_READY` ou `SESSION_DISABLED`, consigné dans le `Log Service`.

---

### 5. Conclusion

Cette garantit un démarrage robuste en validant l'intégrité de chaque session avant son activation. Elle assure la protection du capital via un arrêt global en mode LIVE tout en permettant la continuité du système en mode PAPER.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|DB.getPortfolioSnapshot(SessionID)|Portfolio Manager|Data Access Layer|Requête de lecture synchrone pour récupérer l'état initial des positions et du cash.|
|2|DB.getRiskLimits(SessionID)|Risk Monitor|Data Access Layer|Requête de lecture synchrone pour récupérer les snapshots de risque et limites immuables.|
|3|Return PortfolioSnapshotDTO|Data Access Layer|Portfolio Manager|Transfert de l'objet de données structuré contenant l'état du portefeuille chargé.|
|4|Return RiskSnapshotDTO|Data Access Layer|Risk Monitor|Transfert de l'objet de données structuré contenant les paramètres de risque chargés.|
|5|report(FATAL)|Portfolio Manager|Error Service|Signalement immédiat d'une erreur d'accès ou de lecture critique de la base de données.|
|6|report(FATAL)|Risk Monitor|Error Service|Signalement immédiat d'une erreur d'infrastructure critique empêchant le chargement du risque.|
|7|HCheackDataIntegrity(DTO)|Portfolio Manager|Portfolio Manager|Auto-vérification CPU de la cohérence logique des données de portefeuille reçues.|
|8|HCheackDataIntegrity(DTO)|Risk Monitor|Risk Monitor|Auto-vérification CPU de la validité métier des seuils et limites de risque.|
|9|Return Status(Failure)|Portfolio Manager|Trading Session|Notification au manager de session d'un échec de validation d'intégrité du portefeuille.|
|10|Return Status(Failure)|Risk Monitor|Trading Session|Notification au manager de session d'un échec de validation d'intégrité du risque.|
|11|evaluateBootstrapStatus(StatusList)|Session Manager|Session Manager|Analyse décisionnelle basée sur les retours des managers pour valider la session.|
|12|log(SESSION_READY/DISABLED)|Session Manager|Log Service|Enregistrement final de l'état opérationnel de la session pour l'audit système.|

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
