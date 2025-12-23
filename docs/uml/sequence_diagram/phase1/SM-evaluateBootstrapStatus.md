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
