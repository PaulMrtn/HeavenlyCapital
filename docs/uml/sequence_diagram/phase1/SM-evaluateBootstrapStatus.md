##  `SM-evaluateBootstrapStatus`

<p align="center">
  <img src="../img/SM-evaluateBootstrapStatus.jpg" width="900">
</p>


### 1. Objectif

Cette fonction est le point de contrôle unique pour appliquer la **politique de tolérance aux erreurs asymétrique** du système. Elle décide s'il faut arrêter le *bootstrapping* ou continuer après une défaillance de session.

---

### 2. Contexte

C'est une méthode interne du **`System Manager`** appelée après chaque étape critique de la Phase 1 (ex. : après le chargement parallèle). Son rôle est d'isoler la logique de décision d'arrêt des managers locaux.

---

### 3. Logique Générale

Le **`System Manager`** itère sur la liste des résultats d'exécution (`JobStatusList`). Pour chaque échec, il interroge le **`Configuration Store`** pour obtenir le type de session (`LIVE` ou `PAPER`). Si une session **`LIVE`** a échoué, il exécute **l'arrêt d'urgence**. Si seule une session **`PAPER`** a échoué, il logue l'erreur, marque la session comme invalide et continue l'évaluation des autres sessions.

---

### 4. Règles Critiques

* **Tolérance Zéro (LIVE) :** Toute défaillance `LIVE` déclenche l'arrêt immédiat et fatal via **`systemStop(CRITICAL_ERROR)`**.
* **Tolérance Conditionnelle (PAPER) :** Les échecs `PAPER` sont isolés et logués (`markInvalid()`), permettant au *bootstrapping* de se poursuivre pour les sessions valides.
* **Séparation des Responsabilités :** Le `SM` est le seul composant à connaître cette règle d'arrêt.

---

### 5. Conclusion

Cette fonction garantit que le système est sécurisé en priorisant l'**intégrité des sessions en direct**. Elle gère les défaillances non critiques sans interrompre le processus et assure un arrêt sécurisé et rapide en cas d'échec d'une session `LIVE`.


---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:--- |:--- |:--- |:--- |
| 1  | getJobResults()                  | System Manager | JobStatusList   | Récupère la liste des résultats de bootstrapping.                                                             |
| 2  | getSessionType(SessionID)        | System Manager | System Manager  | AUTO-APPEL : Accès immédiat au dictionnaire immuable (StaticConfigPort) chargé en RAM.                        |
| 3  | handleFatalError(CRITICAL_ERROR) | System Manager | IErrorHandler   | Appel synchrone vers le service centralisé. Déclenche l'arrêt immédiat du système si la session est LIVE.     |
| 4  | LogError(SESSION_FAILURE)        | System Manager | Log Service     | Notification d'erreur pour une session PAPER.                                                                 |
| 5  | markInvalid()                  | System Manager | TradingSession  | Invalidation de l'instance en mémoire (le DIL est ignoré selon tes instructions).                             |
| 6  | Return SUCCESS                   | System Manager | Appelant        | Retourne le contrôle uniquement si aucune erreur fatale (LIVE) n'a interrompu la boucle.                       |



### 6. f

### **IJobStatusReporterPort**
* **Implémenté par** : `Thread Manager`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Fournir le reporting structuré des résultats d'exécution des jobs de bootstrapping (succès ou échec de chaque session).
* **Règles d’accès ou d’usage** : Transmission synchrone. Utilisé par le SM pour obtenir la liste `JobStatusList` au début de l'évaluation.

### **StaticConfigPort**
* **Implémenté par** : `Data Access Layer (DAL)`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Fournir l'accès aux configurations immuables (Dictionnaire/Map) chargées en RAM. Dans cette séquence, il permet de résoudre le type de session (`LIVE` vs `PAPER`) sans accès I/O.
* **Règles d’accès ou d’usage** : Bootstrapping uniquement. Lecture seule d'un snapshot immuable injecté au démarrage.

### **IErrorHandler**
* **Implémenté par** : `ErrorService`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Gestion et propagation des erreurs fatales. Reçoit le signal `handleFatalError` si une session `LIVE` est en échec.
* **Règles d’accès ou d’usage** : Appel synchrone obligatoire pour les erreurs critiques. Instance unique thread-safe. Déclenche l'arrêt immédiat du flux.

### **ILogger**
* **Implémenté par** : `Logger Global`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Journalisation technique et audit. Utilisé pour enregistrer les échecs de sessions non-critiques (`PAPER`).
* **Règles d’accès ou d’usage** : Mode synchrone pour le bootstrapping. Doit enregistrer l'erreur avant que le SM ne continue l'évaluation.

### **ISessionStatusWriter**
* **Implémenté par** : `Data Integration Layer (DIL)`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Persistance du marquage d'invalidité d'une session. Correspond au message `markInvalid()` de la séquence.
* **Règles d’accès ou d’usage** : Passage exclusif par le fragment `AtomicDBWrite` (bien que simplifié dans la discussion, ce port garantit la cohérence de l'état en cas de reboot).

### **IBootstrapCoordinator**
* **Implémenté par** : `System Manager`
* **Injecté dans / Utilisé par** : `Main Entry / Bootstrap Thread`
* **Responsabilité opérationnelle** : Arbitrage final des statuts. Cette séquence (`evaluateBootstrapStatus`) est la méthode concrète de cette interface pour décider du passage à l'état `READY_FOR_TRADING`.
* **Règles d’accès ou d’usage** : Logique de "Fail-fast". Retourne `Return SUCCESS` à l'appelant si et seulement si aucune erreur `LIVE` n'a été rencontrée.


