
## `01-PHASE1-Connectivite-Critique`

<p align="center">
  <img src="../img/01-PHASE1-Connectivite-Critique.jpg" width="900">
</p>


### 1. Objectif

Ce module a pour finalité d'agir comme **point d'entrée sécurisé et décisionnel** du système. Il garantit que le processus ne s'engage dans une phase opérationnelle (Trading Phase 1 ou Rebalancement Phase 4) qu'après avoir validé la **disponibilité des dépendances critiques** et la **pertinence du calendrier**. En cas d'échec, il transmet un signal d'erreur spécifique à l'orchestrateur externe (script Bash) pour permettre une remédiation automatisée.

---

### 2. Contexte

Le module est activé systématiquement lors de chaque réveil du système (**`SYSTEM_WAKEUP`**), qu'il s'agisse d'un démarrage programmé pour une session de trading, d'une exécution de stratégie de rebalancement, ou d'un **redémarrage forcé après un crash** ou une erreur critique. Il sert de garde-fou avant le lancement des phases coûteuses en ressources.

---

### 3. Logique Générale

Le processus est orchestré par le **`System Manager`** selon une séquence strictement conditionnelle :

1. **Vérification Multi-Connectivité :** Le `System Manager` teste séquentiellement la **Base de Données**, l’**IBKR Gateway** puis l’**API EODHD**. Chaque test utilise le fragment de résilience avec des timeouts adaptés.
2. **Gestion des Échecs (Relais Orchestrateur) :** En cas d'échec persistant sur une connexion, le système génère un **code d'erreur spécifique**. Ce code est renvoyé à l'orchestrateur (script Bash parent) qui prend en charge la résolution technique (ex: redémarrage de service ou de tunnel) avant de tenter un nouveau reboot.
3. **Calcul de la Destination Opérationnelle :** Si les connexions sont valides, le système interroge l’`ICalendarServicePort`. Selon le calendrier et le type de réveil, le système décide :
  * De lancer le workflow de **Phase 1** (Trading).
  * De lancer le workflow de **Phase 4** (Rebalancement stratégique).
  * De libérer les ressources (`cleanupConnections`) et retourner en veille (**`Off-Cycle`**) si le marché est fermé.

---

### 4. Règles Critiques

* **Signalétique d'Erreur :** Tout arrêt via `systemStop` doit émettre un code de sortie (Exit Code) normé et documenté, permettant au script de pilotage Bash d'identifier la dépendance en cause.
* **Résilience Uniforme :** Toutes les vérifications utilisent le fragment **`SM-RESILIENT-CHECK-CONNECTION`** pour garantir un audit systématique des tentatives.
* **Arrêt Atomique :** L'arrêt du processus est immédiat et doit garantir la fermeture propre des descripteurs de fichiers pour éviter les verrous (locks) lors du reboot automatique par l'orchestrateur.
* **Responsabilité Unique (SRP) :** La logique calendaire est strictement encapsulée dans son service dédié. Le `System Manager` agit comme point d'entrée unique de la logique de contrôle sans porter la complexité du calcul des jours fériés.
* **Polyvalence du Réveil :** La logique doit être capable de discriminer si le réveil est un cycle normal ou une récupération après erreur pour adapter les vérifications.

---

### 5. Conclusion

Ce module sécurise l'amorçage du système en liant sa survie à la santé de ses dépendances. Il transforme les pannes techniques en **signaux exploitables par l'orchestrateur externe**, permettant une auto-réparation du système (Self-Healing) via reboot forcé. Cette approche garantit que le moteur de trading ne démarre que dans un environnement stabilisé et conforme au calendrier boursier.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|IMarketEventPublisher.publish(MarketEvent{SYSTEM_WAKEUP})|Market Clock|System Manager|Signal de réveil asynchrone déclenchant le passage de l'état IDLE à la phase de vérification active.|
|ref|SM-RESILIENT-CHECK-CONNECTION(checkStatus(Database_Service))|System Manager|Data Ingestion Layer|Appel au fragment de résilience pour vérifier la connectivité vitale à la base de données principale.|
|2|systemStop(CRITICAL_ERROR)|System Manager|System Manager|Arrêt d'urgence du processus en cas d'impossibilité de joindre la base de données.|
|ref|SM-RESILIENT-CHECK-CONNECTION(checkStatus(IBKR_Service))|System Manager|Data Ingestion Layer|Vérification de la liaison avec la passerelle du courtier (Interactive Brokers).|
|3|systemStop(CRITICAL_ERROR)|System Manager|System Manager|Arrêt immédiat si la connexion au broker est défaillante au démarrage.|
|ref|SM-RESILIENT-CHECK-CONNECTION(checkStatus(EODHD_Service))|System Manager|Data Ingestion Layer|Vérification de l'accès à l'API externe de données historiques et de référence.|
|4|systemStop(CRITICAL_ERROR)|System Manager|System Manager|Arrêt de sécurité si le fournisseur de données de référence est inaccessible.|
|5|calculateMarketDayStatus()|System Manager|System Manager|Logique interne déterminant si la date actuelle est une session ouverte (calendrier boursier).|
|6|persistMarketDayStatus|System Manager|Data Ingestion Layer|Enregistrement du statut de la journée via l'interface «MarketDayStatusWriter».|
|7|cleanupConnections()|System Manager|System Manager|Fermeture propre des sockets et libération des ressources si le marché est fermé.|
|8|transitionTo(Off-Cycle)|System Manager|System Manager|Retour à l'état de veille prolongée pour les jours non ouvrés (week-end/férié).|
|9|launch_PHASE1_workflow()|System Manager|System Manager|Déclenchement des procédures de pré-ouverture (chargement portefeuille/risque) si PRE_MARKET.|
|10|launch_PHASE4_workflow()|System Manager|System Manager|Initialisation des moteurs stratégiques si le réveil correspond au cycle STRATEGIC_SETUP.|

---


### 6. Ports et Interfaces

### IMarketEventProvider
- **Implémenté par** : `Market Clock`
- **Injecté dans / Utilisé par** : `System Manager`
- **Responsabilité opérationnelle** : Émission de signaux asynchrones basés sur les horaires officiels d'échange et notification des événements de structure de session (MarketOpen, MarketClose, PreOpen).
- **Règles d’accès ou d’usage** : Diffusion en mode "Publish/Subscribe" ou callback asynchrone pour ne pas bloquer l'orchestrateur. Précision milliseconde requise. Doit être auditable via le Log Service dès réception.

### ISessionStatusWriter
* **Implémenté par** : `Data Integration Layer (DIL)`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Persistance centralisée des statuts de validation de chaque composant.
* **Règles d’accès ou d’usage** : Passage exclusif par le fragment `AtomicDBWrite`. Interdiction d'usage par les managers locaux.

### IExternalConnectivity
* **Implémenté par** : `OrderManager`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Vérification de la liaison physique et logique avec le courtier (Gateway/FIX).
* **Règles d’accès ou d’usage** : Timeout strict de 5000ms. Tout échec est considéré comme une erreur critique en mode LIVE.

**IDatabaseConnectivityPort**
  * **Implémenté par** : `Database Service` (Infrastructure Layer)
  * **Injecté dans / Utilisé par** : `System Manager` / `SM-RESILIENT-CHECK-CONNECTION`
  * **Responsabilité opérationnelle** : Fournir une preuve de vie (Heartbeat) et valider la disponibilité du pool de connexions à la base de données principale.
  * **Règles d’accès ou d’usage** : Appel synchrone obligatoire au démarrage. Timeout à configuré.
  * **Contraintes** : Ne doit effectuer aucune lecture métier à ce stade, uniquement un test de liaison (`ping`).

**IEODHDConnectivityPort**
  * **Implémenté par** : `EODHD Service` (External API Gateway)
  * **Injecté dans / Utilisé par** : `System Manager` / `SM-RESILIENT-CHECK-CONNECTION`
  * **Responsabilité opérationnelle** : Vérifier la validité de l'authentification et l'accessibilité de l'API externe EODHD (données de marché historiques/référence).
  * **Règles d’accès ou d’usage** : Appel synchrone. Timeout à configuré.
  * **Contraintes** : Usage strictement limité au bootstrapping.

**ICalendarServicePort**
  * **Implémenté par** : `Internal Calendar Service`
  * **Injecté dans / Utilisé par** : `System Manager`
  * **Responsabilité opérationnelle** : Déterminer si la date actuelle correspond à une session de trading ouverte selon les calendriers des bourses cibles.
  * **Règles d’accès ou d’usage** : Fournit une réponse booléenne immédiate (calcul in-memory).
  * **Contraintes** : Doit être initialisé avant l'appel à `calculateMarketDayStatus()`.

**IProcessControlPort**
  * **Implémenté par** : `Runtime Environment` / `System Manager`
  * **Injecté dans / Utilisé par** : `System Manager`
  * **Responsabilité opérationnelle** : Gérer les transitions d'état de vie du processus, notamment l'arrêt immédiat en cas d'erreur fatale ou la mise en veille.
  * **Règles d’accès ou d’usage** : Invoqué via `systemStop(CRITICAL_ERROR)` ou `transitionTo(Off-Cycle)`.
  * **Contraintes** : L'appel à `systemStop` doit être atomique et garantir la fermeture des descripteurs de fichiers ouverts.


### NOTE

1. **Phase 01 Scope** : Phase 01 valide uniquement l’environnement (I/O + calendrier) ; aucun état métier ni persistance critique à ce stade.
2. **Error Flow** : Les composants détectent l’erreur ; **le System Manager décide** et appelle explicitement l’ErrorService (Monitor ≠ décideur).
3. **Market Events** : Les événements temporels (MarketOpen, SYSTEM_WAKEUP) sont déclencheurs uniques ; ajouter un garde-fou d’idempotence côté SM.
4. **Heartbeat Policy** : En mode WAITING : échec Heartbeat LIVE → relancer le bootstrapping ; PAPER → retries conditionnels selon le temps restant avant l’open.
5. **Process Stop Contract** :`systemStop()` doit garantir la libération des ressources (sockets, threads) même en arrêt fatal.
