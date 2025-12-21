## `02-PHASE1-Instanciation-Configs-Globaux`

<p align="center">
  <img src="../img/02-PHASE1-Instanciation-Configs-Globaux.jpg" width="900">
</p>


### 1. Objectif

La finalité de ce module est de centraliser la récupération de **toutes les configurations statiques** nécessaires au système de trading et d'utiliser immédiatement ces données pour instancier les **composants globaux (Singletons)** critiques, les rendant opérationnels pour la suite du *bootstrapping*.

---

### 2. Contexte

Ce module s'inscrit directement après la validation de la connectivité et du jour ouvré (**01-PHASE1-Connectivite-Critique**). Il représente la première étape d'allocation et de configuration des ressources en mémoire vive. Il est indispensable car les Singletons créés ici (`IBKR Gateway` et `Live Data Hub`) sont des dépendances fondamentales pour tous les managers locaux qui seront instanciés plus tard.

---

### 3. Logique Générale

Le fonctionnement est basé sur le principe de l'**optimisation I/O** et de l'**injection immédiate de dépendance**. Le **`System Manager`** ordonne au **`Data Access Layer (DAL)`** de lire **en un seul bloc** toutes les configurations depuis la base de données. Ces données sont stockées temporairement en mémoire. Le `System Manager` utilise ensuite ces paramètres pour créer séquentiellement l'`IBKR Gateway` et le `Live Data Hub`, s'assurant que chaque Singleton est créé avec son état de configuration final et valide.

---

### 4. Règles Critiques

* **Lecture Atomique :** Le **`DAL`** doit s'assurer que la lecture de l'ensemble des configurations est réalisée en une seule fois pour **minimiser la latence I/O** vers la base de données.
* **Intégrité de l'Instanciation :** Les Singletons doivent être instanciés avec leur configuration injectée dans le constructeur. Ils ne doivent pas dépendre de valeurs par défaut ou d'une configuration ultérieure. Un **H-Check unitaire** est effectué immédiatement après chaque création pour valider l'intégrité de l'objet en mémoire.
* **Pas de Démarrage Actif :** Bien qu'ils soient instanciés, les Singletons ne lancent **pas encore** leurs boucles de connexion ou de traitement des données. Ils passent simplement à l'état "Prêt".

---

### 5. Conclusion

Le module **`02-PHASE1-Instanciation-Configs-Globaux`** garantit que la lecture des configurations critiques est **rapide et complète**, et que les composants globaux nécessaires au flux de trading (`IBKR Gateway`, `LDH`) sont **instanciés de manière sécurisée et valide** en mémoire avant que le système ne procède à la création des ressources coûteuses et des managers métier.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | readAllStaticConfigs() | System Manager | Data Access Layer | Requête synchrone pour extraire l'intégralité du référentiel de configuration DB en un seul appel I/O. |
| 2 | write(AllConfigs) | Data Access Layer | Config | Hydratation de l'objet de stockage mémoire 'Config' avec les données brutes lues. |
| 3 | ConfigData | Data Access Layer | System Manager | Retour de l'objet structuré contenant les paramètres globaux (Reply Message). |
| 4 | getStaticConfig(IBKR_Config) | System Manager | System Manager | Extraction locale des paramètres spécifiques à la passerelle IBKR. |
| 5 | new IBKRGateway(IBKR_Config) | System Manager | IBKR Gateway | Instanciation du Singleton de communication avec injection de sa configuration. |
| 6 | HCheckUnitary(IG) | System Manager | System Manager | Validation interne (HeartCheck) de l'intégrité de l'objet IBKRGateway en mémoire. |
| 7 | getStaticConfig(LDH_Config) | System Manager | System Manager | Extraction locale des paramètres spécifiques au Live Data Hub. |
| 8 | new LiveDataHub(LDH_Config) | System Manager | Live Data Hub | Instanciation du Singleton de gestion des flux de données temps réel. |
| 9 | HCheckUnitary(LDH) | System Manager | System Manager | Validation interne de l'intégrité de l'objet LiveDataHub en mémoire. |
| 10| call_03-PHASE1-Initialisation-Threads()| System Manager | System Manager | Passage ordonné à la phase suivante du bootstrapping. |

---

### 6. Ports et Interfaces

**PersistencePort**  
- Implémenté par : Data Integrity Layer (DIL)  
- Injecté dans : Live Data Hub, Portfolio Manager, Order Manager  
- Responsabilité : Unique point d’accès pour toute écriture en base (snapshots, états courants, résultats de session)  
- Règles : Accès direct au DIL interdit en dehors de ce port  

**StaticConfigPort**  
- Implémenté par : Data Access Layer (DAL)  
- Utilisé par : System Manager (bootstrapping uniquement)  
- Responsabilité : Lecture unique des configurations statiques, données immuables  
- Règles : Jamais injecté dans les managers métier  

**MarketDataPort**  
- Implémenté par : Live Data Hub  
- Injecté dans : Portfolio Manager, Risk Monitor, Order Manager  
- Responsabilité : Accès en lecture seule aux données de marché  
- Règles : Aucune persistance ni accès DIL via ce port  

**BrokerGatewayPort**  
- Implémenté par : IBKR Gateway  
- Injecté dans : Order Manager (exécution), Portfolio Manager (lecture d’état)  
- Responsabilité : Abstraction complète de la communication avec le broker  
- Règles : Aucun manager ne dépend directement de l’API IBKR

---

### NOTE

L’objectif est de compléter l’instanciation des services globaux critiques afin de fournir un socle de supervision et de gestion centralisée des erreurs avant l’allocation des managers métier. Deux composants doivent être ajoutés : **SystemHealthService**, un singleton d’infrastructure chargé de contrôler l’état des dépendances critiques et des threads, et **CriticalErrorHandlingService**, un singleton core responsable de la gestion uniforme des erreurs critiques et de l’exécution des actions Fail-Fast.

**Contenu des Configs** : Les données lues par le DAL au message 1 correspondent exclusivement aux paramètres immuables de démarrage. Cela inclut les adresses IP/Ports (IBKR), les clés d'API (EODHD), les tailles de buffers (LDH) et les seuils de sécurité globaux. Ces données doivent être chargées dans un objet de type Dictionnaire ou Map immuable pour garantir qu'aucun composant ne puisse modifier la configuration système durant la session.

**H-Check Failure** : En cas de retour négatif lors des messages 6 ou 9 (HCheckUnitary), le System Manager doit immédiatement interrompre le bootstrapping. Cette défaillance est considérée comme une corruption mémoire ou une erreur d'instanciation fatale. L'action corrective est l'appel au fragment systemStop(CRITICAL_ERROR) avec log prioritaire sur le système de fichiers local.


Note 1 – H-Check LDH :
Le H-Check vérifie que la configuration est complète, que les valeurs critiques sont valides, que le port de persistance est injecté et qu’aucune connexion réseau n’est active. Il est local, rapide et bloquant. Échec → arrêt immédiat du bootstrapping.

Note 2 – Config + Sécurité :
Toutes les configurations sont chargées une seule fois, immuables et spécifiques à chaque composant. Chaque composant reçoit uniquement sa portion de config via le constructeur, ne peut la modifier, et passe le H-Check pour figer l’objet en mémoire.

Note 3 - DIL : Tous les managers métier doivent recevoir le PersistencePort (DIL) via injection constructeur. L’accès direct au DIL est interdit. Après injection, un H-Check valide la disponibilité du port. Les managers utilisent ce port pour toutes les écritures atomiques (snapshots, états, résultats de session).
