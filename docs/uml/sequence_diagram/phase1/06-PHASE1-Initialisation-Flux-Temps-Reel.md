## `06-PHASE1-Initialisation-Flux-Temps-Reel`

<p align="center">
  <img src="../img/06-PHASE1-Initialisation-Flux-Temps-Reel.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'établir la **connexion en temps réel** aux données de marché et de **valider** que le flux de prix est actif et correctement acheminé vers le cache du système.

---

### 2. Contexte

Cette étape intervient immédiatement après le chargement des données statiques (positions initiales, limites de risque). Elle est essentielle car elle prépare la source d'information principale pour l'exécution du trading. Sans prix temps réel, le `Risk Monitor` et le `Portfolio Manager` ne peuvent pas fonctionner. Elle établit la liaison entre l'`IBKR Gateway` et le `Live Data Hub (LDH)`.

---

### 3. Logique Générale

Le **`System Manager`** commence par récupérer la liste complète de tous les instruments nécessaires à la surveillance et à l'exécution de toutes les sessions actives. Il ordonne ensuite à l'`IBKR Gateway` d'établir la connexion physique et de demander l'abonnement à ces données. L'`IBKR Gateway` configure le **`LDH`** pour qu'il reçoive les **ticks de prix** asynchrones. Pour finaliser, le `System Manager` effectue un **contrôle de santé** sur le `LDH`, attendant la confirmation de la **réception d'au moins un *tick*** dans un délai imparti. Le succès de cette vérification permet de passer à la phase de validation finale.

---

### 4. Règles Critiques

* **Activation du Flux :** L'établissement de la connexion doit être synchrone, mais l'arrivée des données (`ticks`) est **asynchrone** et ne doit pas bloquer le fil d'orchestration.
* **Validation Critique :** Le contrôle **`HCheckFirstTickReceived`** est une contrainte non-fonctionnelle cruciale. Il s'agit d'une preuve de vie : si aucun prix n'est reçu avant l'expiration du *timeout*, l'opération est considérée comme une **défaillance critique**, et le *bootstrapping* doit être annulé.
* **Encapsulation :** Le `LDH` est le seul récepteur des prix bruts provenant de l'`IBKR Gateway`. Les autres managers ne doivent pas communiquer directement avec la passerelle pour les données de marché.
* **Arrêt Inconditionnel :** Si le `LDH` échoue à confirmer la réception du premier *tick* (erreur de connexion, timeout, etc.), cela signifie que l'infrastructure de données de marché est compromise. Le `System Manager` doit immédiatement appeler **`systemStop(CRITICAL_ERROR)`**.
  
---

### 5. Conclusion

Ce module garantit que le système dispose d'un **canal de données de marché actif et testé** avant la mise en service. Le succès est la preuve que les prix temps réel sont disponibles pour le *Risk Monitor* et le *Portfolio Manager*. L'échec entraîne un arrêt sécurisé immédiat du système.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | `getRequiredMarketDataContracts()` | System Manager | Config | Récupère la liste exhaustive des tickers nécessaires aux sessions actives. |
| 2 | `requestMarketDataFeed(Contracts)` | System Manager | IBKR Gateway | Ordonne l'initialisation du flux de données pour les contrats spécifiés. |
| 3 | `connectToFeedAPI()` | IBKR Gateway | IBKR Gateway | Auto-appel pour établir la connexion TCP/API avec le fournisseur Interactive Brokers. |
| 4 | `subscribe(Contracts)` | IBKR Gateway | Live Data Hub | Transmet les demandes d'abonnement pour acheminer les ticks vers le LDH. |
| 5 | `startStreaming(LDH)` | IBKR Gateway | IBKR Gateway | Déclenche l'envoi asynchrone des flux de prix vers le cache du LDH. |
| 6 | `HCheckGlobal(timeout)` | System Manager | Live Data Hub | Lance le contrôle de santé asynchrone (Couverture + Fraîcheur). |
| 7 | `validateFlow()` | Live Data Hub | Live Data Hub | Vérifie en interne : Seuil ≥ 80% ET Delta Temps Tick/Système valide. |
| 8 | `logCriticalEvent(Error, Meta)` | System Manager | Logger | Journalise l'échec final (IDs manquants, latence) avant l'arrêt. |
| 9 | `systemStop(CRITICAL_ERROR)` | System Manager | System Manager | Arrêt inconditionnel du système en cas d'échec du bootstrapping (Zéro Tolérance). |
| 10 | `call_07-PHASE1...` | System Manager | Next Module | Transition vers la validation croisée si le HCheck est SUCCESS. |


