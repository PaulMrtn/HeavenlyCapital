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

| Fonction / Message | Rôle | Paramètres | Type de Retour |
| :--- | :--- | :--- | :--- |
| `getRequiredMarketDataContracts()` | Récupère la liste des tickers auprès de la Config. | `aucun` | `List<Contract>` |
| `requestMarketDataFeed()` | Initialise l'ordre de récupération des données. | `Contracts` | `void` |
| `connectToFeedAPI()` | Établit la liaison physique avec IBKR. | `aucun` | `ConnStatus` |
| `subscribe()` | Transmet les ordres d'abonnement au LDH. | `Contracts` | `void (Asynch)` |
| `startStreaming()` | Active le flux asynchrone vers le LDH. | `Target: LDH` | `Stream` |
| `HCheckGlobal()` | **[NEW]** Lance le Health Check asynchrone (Couverture + Fraîcheur). | `timeout: ms` | `Promise<Status>` |
| `validateFlow()` | **[NEW]** Logique interne : Seuil ≥ X% ET données fraîches. | `aucun` | `Boolean` |
| `logCriticalEvent()` | **[NEW]** Journalise l'échec définitif (IDs manquants, latence). | `ErrorCode, Meta`| `void` |
| `systemStop()` | Arrêt inconditionnel du système en cas de `FAILURE`. | `CRITICAL_ERR` | `void (Final)` |

---

### 1. Refonte du Health Check (HCheck Global)
* **[TODO] Fusionner les contrôles :** Créer une fonction de validation unique regroupant le seuil de couverture et la fraîcheur.
* **[TODO] Seuil de Couverture :** Valider la séquence uniquement si ≥ 80% des instruments ont reçu au moins un tick.
* **[TODO] Contrôle de Fraîcheur :** Rejeter systématiquement les ticks dont le timestamp est incohérent avec l'heure système (anti-cache obsolète).
* **[TODO] Migration Asynchrone :** Implémenter le HCheck en mode non-bloquant (Promise/Callback) pour libérer le System Manager.

### 2. Résilience et Performance
* **[TODO] Boucle de Retry :** Insérer entre le début du streaming et le HCheck une boucle de 3 tentatives avec backoff exponentiel.
* **[TODO] Isolation Critique :** Forcer l'assignation de l'ensemble de la séquence au Pool de Threads "CRITICAL".

### 3. Gestion d'Erreur et Traçabilité
* **[TODO] Log de Mort (DIL) :** En cas d'échec définitif, déclencher une écriture via le DIL (AtomicDBWrite) avant le `systemStop`.
* **[TODO] Métadonnées d'Audit :** Capturer dans le log : IDs des instruments manquants, latence finale et raison de l'échec.

* **Inconditionnalité :** Si le seuil de 80% ou la fraîcheur échouent, l'arrêt système (`systemStop`) est obligatoire.
* **Pas de Mode Dégradé :** L'option de démarrage avec alertes pour instruments manquants est désactivée.
* **Pas de Log Initial :** La journalisation après la récupération simple de la liste des contrats est jugée inutile et supprimée.
