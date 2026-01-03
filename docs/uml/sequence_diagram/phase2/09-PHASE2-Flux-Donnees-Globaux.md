## `09-PHASE2-Flux-Donnees-Globaux`

<p align="center">
  <img src="../img/09-PHASE2-Flux-Donnees-Globaux.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'orchestrer le traitement complet des données de marché en temps réel, garantissant le **parallélisme** et le **découplage strict** entre les exigences de faible latence (Fast-Lane) et les exigences d'audit (Slow-Lane).

---

### 2. Contexte

Ce module s'inscrit comme le premier grand processus de la Phase II (In-Trade), démarrant dès l'ouverture du marché. Il est la porte d'entrée de toutes les données de prix pour l'ensemble du système de trading. Il existe pour **isoler** les opérations rapides et critiques (nécessaires pour le risque et l'exécution) des opérations lourdes et lentes (nécessaires pour la conformité et l'historique), assurant ainsi que l'une ne bloque jamais l'autre. La Fast-Lane produit des MarketQuote auto-contenues, chacune horodatée et associée à un snapshot_id logique. La Slow-Lane reconstruit a posteriori les SnapshotHeader à des fins de persistance et d’audit, sans jamais imposer de synchronisation ou de complétude au runtime critique.

---

### 3. Logique Générale

Le processus est déclenché par le `SystemManager` qui ordonne au `LiveDataHub` de commencer l'acquisition des données. Une fois l'écoute des Ticks démarrée via `IBKR Gateway`, le `LiveDataHub` initie le traitement parallèle des deux flux :

* **Fast-Lane (Référence 09a) :** Le **Live Data Hub (LDH)** alimente simultanément deux structures en mémoire vive. Cette double sortie garantit que tout composant décisionnel (Risk ou Portfolio) dispose d'une vue cohérente du marché.  Le flux ultra-rapide et non bloquant qui **agrège les ticks en temps réel** et conduit les `MarketQuote` vers le `DataCache` et le `Historic Live Buffer`.
  * **Vers le Data Cache (Miroir de l'Instant) :**
    * **Mécanisme :** Écrasement (Overwrite) atomique.
    * **Usage :** Fournit la `MarketQuote` la plus récente pour les calculs de latence zéro (ex: déclenchement d'un Stop-Loss immédiat par le RM).
  * **Vers le Historic Live Buffer (Mémoire de Session) :**
    * **Mécanisme :** Ajout (Append) séquentiel via l'interface `ILiveDataSubscriber`.
    * **Usage :** Alimente la série temporelle multidimensionnelle dans le **LHB**. Permet au PM d'analyser des tendances ou au RM de calculer une volatilité sur les  dernières minutes.

* **Slow-Lane (Référence 09b) :** Le flux périodique et auditable qui reçoit une **copie asynchrone des snapshots agrégés** de la Fast-Lane et les transfère vers le `DIL` pour une persistance en masse (Bulk I/O) vers la base de données (destination : Audit / Historique).
  * La persistance Bulk I/O écrit les MarketQuotes tels que reçus, sans transformation métier ni recalcul. Toute normalisation ou mapping est du ressort exclusif du DIL.
  * Chaque snapshot produit par la Fast-Lane est transmis à la Slow-Lane sous forme de copie asynchrone, ce qui peut entraîner un léger décalage par rapport à la Fast-Lane, mais garantit que les données restent cohérentes et immuables.
  * La Slow-Lane calcule localement les métriques sur drops, retards et nombre de ticks par snapshot. Ces mesures sont remontées vers le `MetricManager` sans affecter la Fast-Lane. La fréquence et le mode de reporting seront calibrés ultérieurement, l’objectif étant de suivre la qualité des données persistées sans ralentir la Fast-Lane.


L'exécution des deux flux se poursuit en parallèle jusqu'à la fermeture du marché, avec la Fast-Lane en priorité sur l’agrégation et la Slow-Lane en mode asynchrone pour persistance.

---

### 4. Règles Critiques

* **Source Unique et Synchronisation :** Le `LiveDataHub` (LDH) est l'unique garant de la cohérence globale. Un snapshot envoyé au **Data Cache** doit être rigoureusement identique à celui indexé simultanément dans le **Historic Live Buffer**.
* **Garantie de Parallélisme (Fast vs Slow) :** L'isolation via fragments parallèles est absolue. La charge du `Pool I/O Bulk` (Slow-Lane/Persistance) ne doit jamais impacter la boucle critique du `Pool I/O Real-Time` (Fast-Lane/Trading).
* **Accès Partagé et Universel :** Le système ne compartimente pas l'accès aux données par module métier. Le **Risk Monitor** (RM) et le **Portfolio Manager** (PM) ont mutuellement accès aux deux sources : le Data Cache pour l'instant , et le Historic Live Buffer pour la trajectoire historique.
* **Isolation des Lecteurs (Lock-Free) :** Bien que le RM et le PM partagent les sources, ils opèrent via des ports "Reader" strictement **lock-free**. Une analyse lourde (ex: calcul de volatilité par le PM sur le buffer) ne doit jamais ralentir la mise à jour atomique du cache par le LDH.
* **Hiérarchie des Droits (Writer Unique) :** Le `LiveDataHub` est l'unique entité autorisée à écrire dans le Data Cache et le Historic Live Buffer. Toute tentative de mutation directe par un module consommateur est proscrite par l'architecture des ports.
* **Périmètre de Responsabilité :** La séquence 09-09a-09b se limite exclusivement à la production, l'agrégation et l'écriture des données. Toute logique d'interprétation ou de décision métier est déléguée aux séquences consommatrices ultérieures.

---

### 5. Conclusion

Ce module établit le socle de données de marché pour la Phase II. Il garantit que les exigences contradictoires de **rapidité (exécution)** et de **traçabilité (audit)** sont satisfaites simultanément et sans compromis sur la performance, en exploitant l'isolation complète des ressources de calcul et d'I/O.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | startMarketDataService() | System Manager | Live Data Hub | Commande d'initialisation du service global de réception et de dispatching des données de marché. |
| 2 | startAcquisition(IBKRGateway) | Live Data Hub | IBKR Gateway | Instruction d'ouverture de la connexion et de souscription aux flux de Ticks via l'API du courtier. |
| 3 | AcquisitionStarted | IBKR Gateway | Live Data Hub | Signal de confirmation indiquant que le flux de données est actif et que la réception a commencé. |
| ref | 09a-PHASE2-Flux-Critique-FastLane | Live Data Hub | Cache + Buffer | Sous-processus parallèle gérant l'acheminement ultra-rapide des MarketQuotes vers la mémoire vive et le buffer. |
| ref | 09b-PHASE2-Persistance-Bulk-IO | Live Data Hub | Data Ingestion Layer | Sous-processus parallèle gérant l'écriture asynchrone et massive des données pour l'audit et l'historique. |


---

### 6. Ports et Interfaces

**IMarketDataBootstrapPort**
* **Implémenté par** : IBKR Gateway
* **Injecté dans / Utilisé par** : Live Data Hub (via orchestration System Manager)
* **Responsabilité opérationnelle** : Établissement de la connexion technique et initialisation de l'acquisition des flux (Message 2 : `startAcquisition`).
* **Règles d’accès ou d’usage** : Appel synchrone pour le démarrage ; échec entraîne un arrêt immédiat.

**MarketDataSinkPort**
* **Implémenté par** : Live Data Hub (LDH)
* **Injecté dans / Utilisé par** : IBKR Gateway
* **Responsabilité opérationnelle** : Réception des flux de prix bruts (Message 3 : `AcquisitionStarted` et flux suivants). Garantit la préparation des données pour les deux "Lanes" (Fast/Slow).
* **Règles d’accès ou d’usage** : Source unique de vérité pour le système. Les écritures proviennent exclusivement de la Gateway.

**ILiveDataOrchestrator**
* **Implémenté par** : Live Data Hub
* **Injecté dans / Utilisé par** : System Manager
* **Responsabilité opérationnelle** : Point d'entrée pour le pilotage du cycle de vie des données de marché (Message 1 : `startMarketDataService`).
* **Règles d’accès ou d’usage** : Gère la transition vers le mode "In-Trade". Doit confirmer que les deux flux (Fast/Slow) sont opérationnels.

**ISystemKillSwitchPort** 
Interface unique pour signaler une demande d’arrêt global du système.
- **Implémenté par** : `SystemManager`
- **Utilisé par** : Aucun composant métier par défaut
- **Responsabilité** : Exposer un point d’ancrage contractuel pour toute politique future de Kill Switch, sans déclencher directement l’arrêt.
- **Règles** :  Ne peut être appelé par LDH ni en Phase II, Ne déclenche jamais l’arrêt seul, toute action passe par `IProcessControlPort`, Aucun scénario décisionnel n’est défini ici.

**ILiveDataSubscriber**
* **Implémenté par** : `Historic Live Hub (LHB)`
* **Utilisé par** : `Live Data Hub (LDH)`
* **Responsabilité** : Interface de type "Push" permettant d'écrire chaque `MarketQuote` consolidée dans le **Historic Live Buffer**.
* **Règles d’accès** : Doit supporter le mécanisme de **Double Buffering** pour permettre une écriture Fast-Lane sans bloquer les lectures analytiques.

