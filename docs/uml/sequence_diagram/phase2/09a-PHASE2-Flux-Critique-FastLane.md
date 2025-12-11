## `09a-PHASE2-Flux-Critique-FastLane`

<p align="center">
  <img src="../img/09a-PHASE2-Flux-Critique-FastLane.jpg" width="900">
</p>


---

### 1. Objectif

La finalité de ce module est de garantir la **disponibilité immédiate** des prix de marché les plus récents dans le cache en mémoire (`:DataCache`), avec une **latence minimale absolue**, en assurant que le thread de réception de données ne soit **jamais bloqué** par des opérations d'écriture.

---

### 2. Contexte

Ce module est le **cœur opérationnel** de la Phase II (In-Trade). Il s'inscrit directement dans la boucle principale d'exécution. Il est activé dès l'ouverture du marché et représente la **Fast-Lane** des données, qui est critique pour la prise de décision en temps réel et la surveillance du risque. Il est **isolé** de toutes les opérations lentes (Bulk I/O, persistance base de données).

---

### 3. Logique Générale

Le fonctionnement repose sur un modèle **Producteur/Consommateur** découplé par une **Queue Non Bloquante** (`:FastLaneQueue`) :

* Le **Producteur** (`:LiveDataHub`) reçoit les `TickData` bruts, vérifie leur intégrité et leur latence. Si le flux est sain, il agrège les Ticks en un objet `MarketQuote` consolidé. Il **dépose** ensuite ce `MarketQuote` dans la `:FastLaneQueue` de manière asynchrone et continue immédiatement à écouter le prochain Tick, sans attendre la fin de l'écriture.
* Le **Consommateur** (un thread dédié du `:ThreadManager` / `Pool I/O Real-Time`) est en **boucle d'écoute persistante** sur la `:FastLaneQueue`. Dès qu'un `MarketQuote` est disponible, il le retire de la queue et exécute son unique mission : l'écriture dans le `:DataCache`.

---

### 4. Règles Critiques

* **Priorité Sécurité :** La vérification de la latence (`checkLatency()`) est exécutée **avant** toute agrégation ou distribution. En cas de latence critique ou de perte de connexion, le processus s'interrompt immédiatement pour alerter le `:SystemManager` via la référence `REF: SM-HandleCriticalDataLoss`. L'enregistrement (`logCriticalError`) de l'incident est synchrone et prioritaire.
* **Non-Blocage Absolu :** L'opération clé (`enqueue` sur la `:FastLaneQueue`) doit être **non bloquante** pour le thread du `:LiveDataHub`. Cela garantit que l'agrégateur ne perd jamais de temps et peut absorber le flux maximum de `Tick Data`.
* **Isolation des Tâches :** Le calcul intensif (agrégation en `MarketQuote`) est effectué par le Producteur (`:LiveDataHub`), tandis que l'I/O critique (écriture en cache) est effectuée par le Consommateur (`:ThreadManager`). Cela isole le CPU du temps I/O.
* **Structure de Données :** Seul l'objet **`MarketQuote`** (la cotation consolidée pour un actif) transite par la `FastLaneQueue` et est stocké dans le cache, minimisant la charge utile et la latence.

---

### 5. Conclusion

Ce module garantit un flux de prix **déterministe et ultra-rapide** pour le système. Il assure que les données critiques du marché sont disponibles en mémoire avec la plus faible latence possible pour la surveillance du risque (Risk Monitor) et l'exécution des stratégies (Portfolio Manager), tout en intégrant un mécanisme de sécurité immédiat contre la défaillance des données sources.

---

### Description des Fonctions

`tickData(tick_id, asset_id_ref, ...)`:'IBKR Gateway reçoit une mise à jour brute du marché et la transmet de manière asynchrone au Live Data Hub. C'est l'événement déclencheur de chaque itération de la boucle de traitement. Le message transporte l'intégralité des attributs de l'objet `TickData`.

`checkLatency()` : Exécuté immédiatement après la réception du Tick. Le Live Data Hub compare le `timestamp` du `TickData` reçu avec l'heure actuelle du système. Si la différence dépasse un seuil prédéfini (latence max) ou si d'autres métriques de santé du flux sont violées, il renvoie un statut `CRITICAL_ERROR`. C'est le point de décision du fragment **ALT**.

`logCriticalError(EventDetails)` : Si le `checkLatency()` détecte une défaillance critique, le Live Data Hub envoie un message synchrone au service de journalisation. L'opération est synchrone pour garantir que la preuve de l'incident est enregistrée et auditée **avant** que le système ne procède à l'arrêt ou à la tentative de redémarrage.

`REF: SM-HandleCriticalDataLoss(FluxDataLostEvent)`: Ceci est une référence à une séquence UML externe. Si une erreur critique est détectée, le Live Data Hub alerte le System Manager. Le System Manager prend alors le contrôle pour exécuter la procédure d'urgence : annulation des ordres, déconnexion/reconnexion, et décision d'un arrêt fatal ou d'une tentative de reprise.

`aggregateToSnapshot()` : Exécuté uniquement si la latence est jugée acceptable. Le Live Data Hub utilise les Ticks accumulés localement (sur son thread) depuis le dernier snapshot et les consolide. Il calcule les métriques agrégées (Bid/Ask consolidés, Volume cumulé, etc.) et produit l'objet **`MarketQuote`** final prêt à être consommé.

`enqueue(MarketQuote)` : Le Live Data Hub (Producteur) insère l'objet `MarketQuote` (le prix prêt) dans la queue non bloquante. C'est l'opération critique de **découplage**. Le `LiveDataHub` ne se bloque pas et peut passer immédiatement à l'écoute du prochain Tick.

`dequeue()` :  Un thread dédié du Pool I/O Real-Time (Consommateur) retire le `MarketQuote` de la queue. L'opération est modélisée comme un loop continu, représentant la haute fréquence à laquelle le thread vérifie et consomme les nouveaux messages.

`writeToCache(MarketQuote)` : Le thread du Pool I/O Real-Time exécute l'écriture physique du `MarketQuote` dans le cache. C'est l'opération finale de la Fast-Lane. Bien que l'opération soit très rapide (mémoire), elle est synchrone pour le thread consommateur, qui attend la confirmation avant de revenir au `dequeue`.
