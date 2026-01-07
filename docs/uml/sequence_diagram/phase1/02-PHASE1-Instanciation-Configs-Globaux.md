## `02-PHASE1-Instanciation-Configs-Globaux`

<p align="center">
  <img src="../img/02-PHASE1-Instanciation-Configs-Globaux.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de centraliser la récupération de **toutes les configurations statiques immuables** nécessaires au système de trading. Ces données sont utilisées pour instancier immédiatement les **composants globaux (Singletons)** critiques et le socle de supervision, les rendant opérationnels pour la suite du *bootstrapping*.

---

### 2. Contexte et Dépendances

Ce module s'inscrit directement après la validation de la connectivité et du jour ouvré (Phase 01). Il représente la première étape d'allocation des ressources en mémoire vive. Les Singletons créés ici (`IBKR Gateway`, `Live Data Hub`, `Historic Live Hub`) sont des dépendances fondamentales pour tous les managers métier instanciés ultérieurement.

---

### 3. Logique Générale et Optimisation

* **Lecture Atomique :** Le **`System Manager`** ordonne au **`Data Access Layer (DAL)`** de lire en un seul bloc toutes les configurations depuis la base de données afin de minimiser la latence I/O.
* **Stockage Immuable :** Les données sont chargées dans un objet de type **Dictionnaire ou Map immuable**. Aucun composant ne peut modifier la configuration système durant la session.
* **Injection Immédiate :** Le `System Manager` utilise ces paramètres pour créer séquentiellement chaque composant avec son état de configuration final et valide injecté directement dans le constructeur.

---

### 4. Règles Critiques de Sécurité et Fail-Fast

* **Intégrité par H-Check :** Un **H-Check unitaire** est effectué immédiatement après chaque création pour valider l'intégrité de l'objet en mémoire.
* **Spécificité LDH :** Le H-Check du Live Data Hub vérifie la validité des seuils, l'injection du port de persistance et l'absence de connexion réseau active à ce stade.
* **Spécificité LHB :** Le H-Check du Live History Buffer valide que les **Buffers A/B** sont correctement alloués, que l'**index initial est à 0**, qu'**aucun writer n'est actif** et que l'**EventBusPort** est injecté mais silencieux. Le lien de souscription est actif (vérification du pointeur). En cas d'échec de l'un de ces points, le systemStop est déclenché immédiatement.
* **Politique d'Arrêt (Fail-Fast) :** En cas d'échec d'un H-Check (corruption mémoire ou erreur fatale), le système doit interrompre immédiatement le bootstrapping via un appel à `systemStop(CRITICAL_ERROR)` avec log prioritaire.
* **Architecture des Ports :**
  * **PersistencePort (DIL) :** Unique point d’accès pour toute écriture en base. Il est injecté dans le `Live Data Hub` et les managers métier.
  * **StaticConfigPort :** Utilisé uniquement par le `System Manager` pour la lecture unique des données immuables.
  * **MarketDataPort :** Fournit un accès en lecture seule aux données de marché via le `Live Data Hub`.
  * **BrokerGatewayPort :** Abstraction totale de la communication broker via `IBKR Gateway`.


---

### 5. Conclusion

Ce module garantit que le système de trading repose sur un socle de services globaux sains, immuables et supervisés. L'injection systématique des ports (Persistence, MarketData) et la validation immédiate par H-Check empêchent toute propagation d'erreur en amont de l'allocation des ressources métier coûteuses.

---

|ID|Fonction / Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|readAllStaticConfigs()|System Manager|Data Access Layer|Requête d'extraction de l'ensemble des paramètres de configuration immuables du système.|
|2|create()|Data Access Layer|Config|Instanciation de l'objet Config destiné à stocker les paramètres en mémoire vive.|
|3|write(AllConfigs)|Data Access Layer|Config|Injection des données lues en base de données dans l'objet de configuration structuré.|
|4|ConfigData|Data Access Layer|System Manager|Retour de l'objet de configuration global hydraté au superviseur.|
|5|getStaticConfig(IBKR_Config)|System Manager|System Manager|Extraction des paramètres spécifiques à la passerelle de courtage Interactive Brokers.|
|6|new IBKRGateway(IBKR_Config, PersistencePort)|System Manager|IBKR Gateway|Instanciation du singleton de communication broker avec injection de sa config et du port de persistance.|
|7|HCheckUnitary(IBKRGateway)|System Manager|System Manager|Vérification de l'intégrité mémoire et de l'état initial de la passerelle IBKR.|
|8|getConfig(LDH_Config)|System Manager|System Manager|Extraction des paramètres de seuils et de structure pour les hubs de données.|
|9|new LiveHistoryBuffer(Config)|System Manager|Historic Live Hub|Création du buffer historique et pré-allocation de la matrice de données linéaire.|
|10|new LiveDataHub(LDH_Config, PersistencePort, ILiveDataSubscriber(LHB))|System Manager|Live Data Hub|Instanciation du hub de flux avec liaison synchrone vers le buffer historique.|
|11|HCheckUnitary(LDH, LHB)|System Manager|System Manager|Validation groupée de la cohérence du flux de données et de l'allocation mémoire du buffer.|
|12|getConfig(ML_Forecast_Config)|System Manager|System Manager|Extraction des configurations liées aux modèles de Machine Learning et au répertoire d'artefacts.|
|13|new ForecastManager(ML_Forecast_Config, ILiveDataReader, IMarketDataObserverPort)|System Manager|ForecastManager|Instanciation du hub analytique avec injection des ports de lecture historique et d'observation.|
|14|HCheckUnitary(ForecastManager)|System Manager|System Manager|Vérification de la découverte des modèles ML et de l'intégrité des checksums sur le file system.|
|15|systemStop(CRITICAL_ERROR)|System Manager|Error Service|Déclenchement de l'arrêt d'urgence du bootstrapping en cas d'échec d'un Health-Check.|

---

### 6. Ports et Interfaces

**StaticConfigPort**
* **Implémenté par** : `Data Access Layer (DAL)`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Lecture unique des configurations statiques immuables (paramètres système, seuils globaux) nécessaires au démarrage.
* **Règles d’accès ou d’usage** : Bootstrapping uniquement. Lecture seule, snapshot immuable.

**PersistencePort**
* **Implémenté par** : `Data Integrity Layer (DIL)`
* **Injecté dans / Utilisé par** : `IBKR Gateway`, `Live Data Hub` (LDH)
* **Responsabilité opérationnelle** : Point d’accès unique pour toute persistance critique. Injecté dans le LDH pour garantir la traçabilité des flux dès l'initialisation.
* **Règles d’accès ou d’usage** : Transactions atomiques obligatoires. Accès direct au DIL interdit.

**BrokerGatewayPort**
* **Implémenté par** : `Gateway externe (IBKR)`
* **Injecté dans / Utilisé par** : `System Manager` (via l'instanciation de l'IBKR Gateway)
* **Responsabilité opérationnelle** : Abstraction complète du courtier. Transmission technique et réception des callbacks.
* **Règles d’accès ou d’usage** : Encapsulation totale.

**IErrorHandler**
* **Implémenté par** : `ErrorService`
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Gestion centralisée des erreurs critiques et propagation des erreurs fatales.
* **Règles d’accès ou d’usage** : Appels synchrones pour erreurs critiques (Fail-Fast).

**ILiveDataSubscriber**
* **Implémenté par** : `LiveHistoryBuffer` (LHB)
* **Injecté dans / Utilisé par** : `LiveDataHub` (LDH)
* **Responsabilité opérationnelle** : Réceptionner les snapshots consolidés du LDH pour stockage en série temporelle.
* **Règles d’accès ou d’usage** : Port passif durant la phase d'initialisation.

**ILiveHistoryControlPort**
* **Implémenté par** : `LiveHistoryBuffer` (LHB)
* **Injecté dans / Utilisé par** : `System Manager`
* **Responsabilité opérationnelle** : Piloter le cycle de vie du buffer (allocation des 1000 slots, swap, purge).
* **Règles d’accès ou d’usage** : Appel synchrone obligatoire en Phase 1 pour la pré-allocation mémoire.

**IEventBusPort**
* **Implémenté par** : `EventBus`
* **Injecté dans / Utilisé par** : `LiveHistoryBuffer` (LHB), `DataCache` (LDH)
* **Responsabilité opérationnelle** : Notification asynchrone signalant la disponibilité d'une nouvelle donnée dans le buffer.
* **Règles d’accès ou d’usage** : Injecté en Phase 1 mais maintenu silencieux jusqu'au début de la session.

**ILiveHistoryFreezePort**
* **Implémenté par :** LiveHistoryBuffer
* **Injecté dans** : System Manager
* **Responsabilité :**
  * Geler définitivement la structure mémoire du buffer historique
  * Interdire toute reconfiguration après bootstrap
* **Règles :**
  * Appel synchrone
  * Irréversible
  * PHASE2 uniquement


### DATA OBJET

Objet observé : IBKRGateway / LiveDataHub / LiveHistoryBuffer (Type : Singletons / Objets Métiers)
Usage : Composants globaux (Infrastructure et Domaine).
Évaluation : Sub-optimal (au niveau sémantique)
Recommandation : Entités de Domaine (Process-scoped)
Justification : Ces objets ne sont pas de simples conteneurs de données, mais des Entités. Ils possèdent une identité propre, un cycle de vie (Bootstrap -> Active -> Shutdown) et maintiennent un état interne complexe (connexion, index de buffer). Leur intégrité est d'ailleurs validée par les HCheckUnitary.
