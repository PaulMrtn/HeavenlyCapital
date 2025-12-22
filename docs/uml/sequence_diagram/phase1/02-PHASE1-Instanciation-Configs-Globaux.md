## `02-PHASE1-Instanciation-Configs-Globaux`

<p align="center">
  <img src="../img/02-PHASE1-Instanciation-Configs-Globaux.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de centraliser la récupération de **toutes les configurations statiques immuables** nécessaires au système de trading. Ces données sont utilisées pour instancier immédiatement les **composants globaux (Singletons)** critiques et le socle de supervision, les rendant opérationnels pour la suite du *bootstrapping*.

---

### 2. Contexte et Dépendances

Ce module s'inscrit directement après la validation de la connectivité et du jour ouvré (Phase 01). Il représente la première étape d'allocation des ressources en mémoire vive. Les Singletons créés ici (`IBKR Gateway`, `Live Data Hub`, `SystemHealthService`, `ErrorService`) sont des dépendances fondamentales pour tous les managers métier instanciés ultérieurement.

---

### 3. Logique Générale et Optimisation

* **Lecture Atomique :** Le **`System Manager`** ordonne au **`Data Access Layer (DAL)`** de lire en un seul bloc toutes les configurations depuis la base de données afin de minimiser la latence I/O.
* **Stockage Immuable :** Les données sont chargées dans un objet de type **Dictionnaire ou Map immuable**. Aucun composant ne peut modifier la configuration système durant la session.
* **Injection Immédiate :** Le `System Manager` utilise ces paramètres pour créer séquentiellement chaque composant avec son état de configuration final et valide injecté directement dans le constructeur.

---

### 4. Règles Critiques de Sécurité et Fail-Fast

* **Socle d'Infrastructure :** Avant l'allocation des managers métier, le système doit instancier le **SystemHealthService** (contrôle des threads) et le **CriticalErrorHandlingService** (gestion des actions Fail-Fast).
* **Intégrité par H-Check :** Un **H-Check unitaire** est effectué immédiatement après chaque création pour valider l'intégrité de l'objet en mémoire.
    * **Spécificité LDH :** Le H-Check du Live Data Hub vérifie la validité des seuils, l'injection du port de persistance et l'absence de connexion réseau active à ce stade.
* **Politique d'Arrêt (Fail-Fast) :** En cas d'échec d'un H-Check (corruption mémoire ou erreur fatale), le système doit interrompre immédiatement le bootstrapping via un appel à `systemStop(CRITICAL_ERROR)` avec log prioritaire.
* **Architecture des Ports :**
    * **PersistencePort (DIL) :** Unique point d’accès pour toute écriture en base. Il est injecté dans le `Live Data Hub` et les managers métier. L’accès direct au DIL est strictement interdit.
    * **StaticConfigPort :** Utilisé uniquement par le `System Manager` pour la lecture unique des données immuables.
    * **MarketDataPort :** Fournit un accès en lecture seule aux données de marché via le `Live Data Hub`.
    * **BrokerGatewayPort :** Abstraction totale de la communication broker via `IBKR Gateway`.

---

### 5. Conclusion

Ce module garantit que le système de trading repose sur un socle de services globaux sains, immuables et supervisés. L'injection systématique des ports (Persistence, MarketData) et la validation immédiate par H-Check empêchent toute propagation d'erreur en amont de l'allocation des ressources métier coûteuses.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | `readAllStaticConfigs()` | System Manager | DAL | Requête synchrone pour l'intégralité du référentiel (IP, Ports, API Keys, Buffers). |
| 2 | `write(AllConfigs)` | DAL | Config | Hydratation de l'objet de stockage mémoire immuable. |
| 3 | `ConfigData (Reply)` | DAL | System Manager | Retour de l'objet structuré contenant les paramètres globaux. |
| 4 | **Instanciation Infra** | System Manager | Services | Création séquentielle de `SystemHealthService` et `CriticalErrorHandlingService`. |
| 5 | `new IBKRGateway(Config)` | System Manager | IBKR Gateway | Instanciation avec injection de la configuration spécifique. |
| 6 | `HCheckUnitary(IG)` | System Manager | System Manager | Validation locale et bloquante. Échec = Arrêt système. |
| 7 | `new LiveDataHub(Config, Port)` | System Manager | Live Data Hub | Instanciation avec injection de la config et du **PersistencePort**. |
| 8 | `HCheckUnitary(LDH)` | System Manager | System Manager | Validation finale de l'intégrité du Hub de données. |
| 9 | `call_03-PHASE1...` | System Manager | System Manager | Passage à la phase d'initialisation des threads. |

---

### 6. Ports et Interfaces

**PersistencePort**
* **Implémenté par :** Data Integrity Layer (DIL) / AtomicDBWriteProcess
* **Injecté dans :** Portfolio Manager (PM), Order Manager (OM), Live Data Hub (LDH) si nécessaire
* **Responsabilité :** Point unique d’accès pour toute persistance critique du système :
  * Snapshots de positions et portefeuilles
  * Journaux de sessions et SessionBooks
  * Ordres et exécutions (Fills)
  * États courants du système métier
* **Règles d’accès :**
  * Accès direct au DIL interdit en dehors de ce port
  * Persistance **atomique** obligatoire : startTransaction / commit / rollback
  * Isolation stricte : aucun module externe ne peut modifier ou lire directement les objets métier sans passer par ce port
  * Supporte les écritures synchronisées et sécurisées pour les opérations critiques
* **Phase d’utilisation :**
  * Bootstrapping et runtime métier, selon contexte
  * Tous accès critiques doivent transiter par ce port
* **Objectif :** Assurer la cohérence, atomicité et auditabilité des données critiques à travers tout le système


**StaticConfigPort**  
- Implémenté par : Data Access Layer (DAL)  
- Utilisé par : System Manager (bootstrapping uniquement)  
- Responsabilité : Lecture unique des configurations statiques, données immuables  
- Règles : Jamais injecté dans les managers métier  

**Port : MarketDataPort**
  * **Implémenté par :** LDH Global (ou Live Data Hub, il faut choisir une terminologie unique dans toute la doc)
  * **Injecté dans :** Portfolio Manager, Risk Monitor, éventuellement Order Manager si lecture nécessaire
  * **Responsabilité :** Diffusion des flux de marché en lecture seule (prix, volume, snapshots)
  * **Règles d’usage :** Accès immuable, interdiction de modification. Timeout et retry gérés au niveau du port. Aucune persistance ni accès direct au DIL.


**BrokerGatewayPort**
* **Implémenté par :** Gateway externe IBKR
* **Injecté dans :** Order Manager (OM)
* **Responsabilité :**
  * Abstraction complète de la communication avec le broker
  * Transmission technique des ordres et réception des callbacks
  * Gestion de la priorité des ordres (`CRITICAL` vs `STANDARD`)
* **Règles d’usage :**
  * Aucun accès direct autorisé par PM ou RM (tout passe par OM)
  * Le Risk Monitor soumet les ordres urgents via **IOrderSubmissionPort**, qui délègue ensuite vers le **BrokerGatewayPort** dans OM
* **Objectif :** Isoler le courtier des modules métier tout en permettant le passage sécurisé des ordres critiques et standards




