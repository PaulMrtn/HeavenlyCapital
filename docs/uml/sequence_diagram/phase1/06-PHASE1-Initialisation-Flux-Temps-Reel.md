## `06-PHASE1-Initialisation-Flux-Temps-Reel`

<p align="center">
  <img src="../img/06-PHASE1-Initialisation-Flux-Temps-Reel.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'établir la connexion technique aux serveurs de données de marché et de valider que le flux de prix est actif, conforme aux besoins de l'univers de trading, et correctement acheminé vers le cache du `Live Data Hub` (LDH) puis à la mémoire structurée du `Historic Live Hub` (LHB).

---

### 2. Contexte

Cette étape intervient immédiatement après le chargement des données statiques et des états de sessions. Elle constitue le pont critique entre l'infrastructure externe (`IBKR Gateway`) et le cœur analytique composé du `Live Data Hub` (LDH) et du `Historic Live Hub` (LHB). Sans la validation de cette phase, le `IMarketDataHealthPort`, le `Risk Monitor` et le `Portfolio Manager` restent inactifs pour garantir la sécurité des opérations.

---

### 3. Logique Générale

1. **Extraction :** Le `System Manager` interroge le **`TradingUniversePort`** (via la DAL) pour obtenir la liste exhaustive des instruments à surveiller.
2. **Initialisation :** Il transmet cette liste à l'**`IMarketDataBootstrapPort`** de l'IBKR Gateway pour ouvrir la connexion API et souscrire aux flux.
3. **Acheminement :** L'IBKR Gateway dirige les ticks entrants vers le **`MarketDataSinkPort`** du LDH qui propage immédiatement les données au LHB via l'interface `ILiveDataSubscriber`.
4. **Validation de Chaîne:** Le `System Manager` déclenche un contrôle de santé via l'interface **`IMarketDataHealthPort`**. Le LDH doit confirmer qu'il reçoit des données fraîches pour une majorité de l'univers demandé avant la fin du temps imparti. Le succès requiert la preuve que la donnée a traversé toute la chaîne jusqu'au LHB.
5. **Arbitrage :** Le passage à la validation croisée n'est autorisé que si la couverture est suffisante et le mécanisme de buffering opérationnel. En cas d'échec (timeout ou couverture insuffisante), le système s'arrête immédiatement.


---

### 4. Règles Critiques

* **Activation du Flux :** L'établissement de la connexion technique doit être synchrone, mais le flux de données entrant (`ticks`) est strictement **asynchrone** pour ne pas bloquer le fil d'orchestration du System Manager.
* **Intégrité de la Chaîne de Flux (End-to-End) :** La validation "Preuve de Vie" est globale et indivisible : **IBKR → LDH → LHB**. Si le `Live Data Hub` (LDH) reçoit les données mais échoue à les transmettre au `Historic Live Hub` (LHB) via l'interface `ILiveDataSubscriber` (ex: erreur de pointeur ou saturation mémoire), le système déclenche un **`systemStop`** immédiat.
* **Validation Statistique et Temporelle :** Le contrôle `HCheckGlobal(timeout)` n'est validé que si **100% des instruments critiques** reçoivent des prix actifs avec un delta de temps (latence) conforme aux paramètres système. L'absence de réception avant l'expiration du timeout est traitée comme une **défaillance critique**.
* **Initialisation du Double Buffering :** Avant de clore la phase, le LHB doit confirmer que son mécanisme interne est opérationnel : le **Buffer A** doit être actif pour l'écriture et le **Buffer B** disponible pour la lecture (état **`LHB_READY`**).
* **Encapsulation et Souveraineté :** Le LDH est le seul récepteur autorisé des prix bruts provenant de l'IBKR Gateway via le `MarketDataSinkPort`. Le LHB est l'unique portier de l'historique intraday. Aucun manager (PM ou RM) ne doit communiquer directement avec la passerelle pour les données de marché.
* **Zéro Tolérance (Fail-Fast) :** Tout échec de l'interface `IMarketDataBootstrapPort` (erreur API), de `IMarketDataHealthPort` (timeout) ou de l'interface **`ILiveDataSubscriber`** entraîne l'arrêt inconditionnel du bootstrapping via `systemStop(CRITICAL_ERROR)`.
* **Immuabilité de l'Univers :** La liste des instruments récupérée au début de cette phase (via le `TradingUniversePort`) est considérée comme figée pour toute la durée de l'initialisation.

---

### 5. Conclusion

Ce module garantit que le système dispose d'un **canal de données de marché actif et testé** avant la mise en service. Le succès est la preuve que les prix temps réel sont disponibles pour le *Risk Monitor* et le *Portfolio Manager*. L'échec entraîne un arrêt sécurisé immédiat du système.

---

|ID|Fonction / Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|getRequiredMarketDataContracts()|System Manager|Config|Récupération de la liste exhaustive des tickers nécessaires aux sessions de trading actives.|
|2|requestMarketDataFeed(Contracts)|System Manager|IBKR Gateway|Ordre d'initialisation technique pour la souscription aux flux de données de marché spécifiés.|
|3|connectToFeedAPI()|IBKR Gateway|IBKR Gateway|Établissement de la connexion TCP/API vers les serveurs de données du broker (Interactive Brokers).|
|4|subscribe(Contracts)|IBKR Gateway|Live Data Hub|Enregistrement des abonnements pour router les flux entrants vers le point d'entrée du hub.|
|5|startStreaming(LDH)|IBKR Gateway|IBKR Gateway|Déclenchement du flux asynchrone des données de marché vers le système local.|
|6|pushInitialSnapshot(MarketQuote)|IBKR Gateway|Historic Live Hub|Transmission du premier agrégat de prix pour valider l'interface d'écriture ILiveDataSubscriber du buffer.|
|7|HCheckGlobal(Timeout)|System Manager|Live Data Hub|Contrôle de santé global orchestré pour vérifier la preuve de vie et la couverture du flux.|
|8|validateFlow()|Live Data Hub|Live Data Hub|Vérification interne de la fraîcheur des données (Delta Temps) et de la complétude de l'univers reçu.|
|9|verifyBufferSwap()|Historic Live Hub|Historic Live Hub|Validation du mécanisme de Double Buffering et du swap atomique lock-free.|
|10|Return SUCCESS (Tick Received)|Live Data Hub|System Manager|Confirmation positive de l'établissement du canal de données complet (Broker -> LDH -> LHB).|
|11|Return FAILURE (Timeout)|Live Data Hub|System Manager|Signalement d'une anomalie critique (Absence de données ou latence excessive).|
|12|logCriticalEvent(ErrorCode, Metadata)|System Manager|Log Service|Journalisation détaillée des causes de l'échec pour l'audit post-mortem.|
|13|systemStop(CRITICAL_ERROR)|System Manager|System Manager|Déclenchement immédiat du protocole Fail-Fast et arrêt sécurisé du bootstrapping.|

---

### 6. Ports et Interfaces

**StaticConfigPort**
- **Implémenté par** : Data Access Layer (DAL)
- **Injecté dans / Utilisé par** : System Manager
- **Responsabilité opérationnelle** :
  - Fourniture de la configuration statique de la session
  - Exposition de l’univers de trading (liste exhaustive des instruments)
- **Règles d’accès ou d’usage** :
  - Lecture seule
  - Snapshot immuable pour toute la PHASE1
  - Interdiction d’usage en runtime

**IMarketDataBootstrapPort**
- **Implémenté par** : Broker Gateway (IBKR Gateway)
- **Injecté dans / Utilisé par** : System Manager
- **Responsabilité opérationnelle** :
  - Établissement de la connexion technique au fournisseur de données
  - Initialisation et enregistrement des abonnements marché
- **Règles d’accès ou d’usage** :
  - Appels synchrones uniquement
  - Usage strictement limité au bootstrapping
  - Aucun accès direct aux flux de prix
  - Échec ⇒ CRITICAL_FAILURE immédiat

**IMarketDataHealthPort**
- **Implémenté par** : Live Data Hub (LDH)
- **Injecté dans / Utilisé par** : System Manager
- **Responsabilité opérationnelle** :
  - Validation de la preuve de vie du flux de données marché
  - Vérification de la couverture des instruments requis
  - Contrôle de la fraîcheur des ticks reçus
- **Règles d’accès ou d’usage** :
  - Appel synchrone avec timeout dur
  - Aucune opération I/O externe bloquante
  - Logique de validation strictement encapsulée
  - Échec ⇒ arrêt immédiat du système

**MarketDataPort**
- **Implémenté par** : Live Data Hub (LDH Global)
- **Injecté dans / Utilisé par** : Portfolio Manager, Risk Monitor
- **Responsabilité opérationnelle** :
  - Diffusion des données de marché validées (prix, volumes, snapshots)
- **Règles d’accès ou d’usage** :
  - Lecture seule
  - Objets immuables
  - Activation interdite avant validation complète du flux
  - Inactif durant toute la PHASE1

**ILogger**
- **Implémenté par** : Logger Global
- **Injecté dans / Utilisé par** : System Manager
- **Responsabilité opérationnelle** :
  - Journalisation des événements critiques du bootstrapping
  - Enregistrement des métadonnées d’échec avant arrêt
- **Règles d’accès ou d’usage** :
  - Appels synchrones pour erreurs fatales
  - Aucune logique métier
  - Non bloquant hors chemin critique
 
**MarketDataSinkPort** 
* **Implémenté par** : Live Data Hub (LDH) ou tout service capable de recevoir et traiter les flux de marché entrants.
* **Injecté dans / Utilisé par** : IBKR Gateway, System Manager (pour orchestration initiale).
* **Responsabilité opérationnelle** :
  * Recevoir les flux de prix bruts provenant de la passerelle du courtier.
  * Acheminer ces données vers le cache interne et les composants consommateurs (Portfolio Manager, Risk Monitor) après validation minimale.
  * Garantir la **séquentialité** et la **complétude** des ticks pour permettre la persistance atomique.
  * Préparer les données pour la distribution aux services de persistance ou de calcul stratégique.
* **Règles d’accès ou d’usage** :
  * Aucun accès direct par PM, RM ou autres consommateurs métiers.
  * Lecture seule côté consommateurs : ils ne doivent jamais écrire dans ce flux.
  * Les écritures doivent passer uniquement par des services producteurs de flux (ex : IBKR Gateway).
  * Gestion des erreurs : tout échec critique dans le traitement doit remonter au System Manager pour déclencher des alertes ou un arrêt sécuritaire.


**TradingUniversePort**
* **Implémenté par** : Data Access Layer (DAL) ou tout service fournissant l’univers de trading
* **Injecté dans / Utilisé par** : System Manager
* **Responsabilité opérationnelle** :
  * Fournir la liste complète et à jour des instruments de marché disponibles pour le trading
  * Exposer les métadonnées associées à chaque instrument (type d’instrument, marché, devise, lot size, etc.)
  * Servir de source unique pour la validation et la préparation des flux de données et des abonnements
* **Règles d’accès ou d’usage** :
  * Lecture seule pendant tout le cycle de trading
  * Snapshot immuable pendant les phases critiques (PHASE1, PHASE4)
  * Interdiction d’écriture directe par les consommateurs
  * Toute modification doit passer par un service central de mise à jour de l’univers, versionné et auditable

