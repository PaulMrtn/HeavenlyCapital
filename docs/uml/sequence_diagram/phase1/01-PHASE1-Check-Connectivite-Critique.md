
## `01-PHASE1-Connectivite-Critique`

<p align="center">
  <img src="../img/01-PHASE1-Connectivite-Critique.jpg" width="900">
</p>


### 1. Objectif

Ce module a pour finalité d'agir comme **point d'entrée sécurisé** du système de trading. Il garantit que le processus de *bootstrapping* ne se poursuit qu'après avoir validé la **disponibilité de toutes les dépendances critiques** (via `IDatabaseConnectivityPort`, `IExternalConnectivity` et `IEODHDConnectivityPort`) et confirmé la **pertinence métier** par l'analyse du calendrier via `ICalendarServicePort`.

---

### 2. Contexte

Le module s'inscrit au début absolu de la **Phase Pré-Trade (Bootstrapping)**, immédiatement après la réception du signal **`SYSTEM_WAKEUP`** émis par l’`IMarketEventProvider` (Market Clock). Son existence vise à prévenir le gaspillage de ressources (temps d'instanciation des composants) si les services fondamentaux (I/O) ou la condition de marché sont absents.

---

### 3. Logique Générale

Le processus est orchestré par le **`System Manager`** et se déroule de manière séquentielle et conditionnelle :

1. **Vérification Sécurisée :** Le `System Manager` vérifie séquentiellement la **Base de Données**, l’**IBKR Gateway** puis l’**API EODHD**. Il utilise le fragment de résilience transversal avec des **timeouts différenciés** : très court pour la DB (2s) afin de détecter une panne immédiate, et plus long pour IBKR (10s) pour autoriser le handshake réseau.
2. **Calcul du Statut :** Une fois les connexions établies, le système interroge son instance interne de gestion calendaire (`ICalendarServicePort`) pour déterminer le **`MarketDayStatus`**. Ce statut est persisté via l’`ISessionStatusWriter` (DIL) pour l'audit.
3. **Décision de Poursuite :** Si le jour n'est pas ouvré, le système déclenche une fonction de **nettoyage** (`cleanupConnections`) pour libérer les sockets ouverts (DB/IBKR) avant d'entrer en veille (**`Off-Cycle`**). Si le jour est ouvré, le *bootstrapping* se poursuit vers l'étape d'instanciation.

---

### 4. Règles Critiques

* **Résilience Uniforme :** Toutes les vérifications de connexion utilisent le fragment **`SM-RESILIENT-CHECK-CONNECTION`** pour garantir une logique uniforme de gestion des pannes transitoires et de l'audit.
* **Arrêt Atomique :** Un **échec critique et persistant** entraîne l'envoi immédiat d'une alerte et la **destruction immédiate** du processus via l’`IProcessControlPort` (`systemStop`). Cet arrêt est atomique et garantit la fermeture des descripteurs de fichiers ouverts.
* **Responsabilité Unique (SRP) :** La logique calendaire est strictement encapsulée dans son service dédié. Le `System Manager` agit comme point d'entrée unique de la logique de contrôle sans porter la complexité du calcul des jours fériés.

---

### 5. Conclusion

Le module **`01-PHASE1-Connectivite-Critique`** garantit que l'initialisation du système est toujours **conditionnelle** à la santé de ses dépendances et à la pertinence du contexte de marché. Il assure l'**intégrité du démarrage** par une procédure d'arrêt strict en cas de défaillance fondamentale, ou une mise en veille optimisée par libération de ressources, avant de passer à la phase coûteuse d'instanciation.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
|1|publish(MarketEvent{SYSTEM_WAKEUP})|Market Clock|System Manager|Événement asynchrone déclenchant le réveil du système et le début du bootstrapping.|
|ref|SM-RESILIENT-CHECK-CONNECTION(Service_Name)|System Manager|Fragment Résilience|Vérification séquentielle (DB, IBKR, EODHD) avec timeouts différenciés (2s, 10s, 5s).|
|2,3,4|systemStop(CRITICAL_ERROR)|System Manager|System Manager|Auto-appel déclenchant la procédure d'arrêt d'urgence et la destruction du runtime.|
|5|calculateMarketDayStatus()|System Manager|System Manager|Logique interne déterminant si le jour actuel est un jour de trading via le module Calendar.|
|6|persistMarketDayStatus()|System Manager|Data Ingestion Layer|Délégation au DIL pour la persistance du statut du jour et récupération de données contextuelles.|
|7a|cleanupConnections()|System Manager|System Manager|Libération des sockets et ressources (DB/IBKR) pour éviter toute fuite de ressources en mode Off-Cycle.|
|7b|transitionTo(Off-Cycle)|System Manager|System Manager|Mise en veille du système si le marché est fermé (pas d'instanciation nécessaire).|
|8|call_02-PHASE1...()|System Manager|System Manager|Passage à la séquence suivante d'instanciation globale si toutes les conditions sont validées.|

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

