## `07-PHASE1-Validation-Croisee-HeartCheck`

<p align="center">
  <img src="../img/07-PHASE1-Validation-Croisee-HeartCheck.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'effectuer la **validation croisée finale** et un **contrôle de santé global (`HeartCheck`)** sur l'ensemble du système. Il garantit la cohérence opérationnelle et la sécurité des liens entre les managers via les interfaces `IBootstrapReadinessCheck` et `ICrossValidator` avant de faire la transition vers l'état `READY_FOR_TRADING`.

---

### 2. Contexte

Cette étape est la **dernière de la Phase 1 (Pre-Trade)**. Elle est exécutée après le succès du **chargement statique** (Phase 05) et de l'**initialisation du flux temps réel** (Phase 06). Elle est critique car elle confirme que les données chargées par un manager sont compatibles avec les règles et l'état des autres, agissant comme le **point de non-retour sécurisé** avant de donner le feu vert pour la session de trading.

---

### 3. Logique Générale

Le **`System Manager`** (`IBootstrapCoordinator`) orchestre une série de vérifications en cascade pour recueillir le statut opérationnel de chaque manager et la cohérence inter-composants.

* **Vérifications Unitaires (`IBootstrapReadinessCheck`) :** Validation de l'intégrité technique, de l'instanciation des structures et de l'état des threads.
* **Vérifications ML** : Chaque Manager effectue une inférence "à blanc" (dummy inference) sur ses modèles ML injectés (`IExecutionDecisionModel` / `IStopPredictionModel`). Cela garantit que la pipeline de calcul est chargée en mémoire et opérationnelle sans crash système.
* **Contrainte de Latence ML** : Chaque oracle ML doit respecter un budget maximal d’inférence strictement borné.
* **Validations Croisées (`ICrossValidator`) :** Validation de la cohérence métier inter-domaines, comme la compatibilité entre les limites de risque et l'état du portefeuille.
* **Vérification de l'Infrastructure (`IExternalConnectivity`) :** Test de la liaison physique et logique avec le courtier avec un **timeout strict de 5000ms**.
* **Centralisation des Statuts :** Pour garantir le découplage, les managers retournent leurs résultats au `System Manager`, qui se charge seul de mettre à jour la `SessionStatusList` via `ISessionStatusWriter`.

---

### 4. Règles Critiques

* **Tolérance aux Erreurs Asymétrique :** Toute défaillance concernant une session **`LIVE`** entraîne un arrêt immédiat via `systemStop(CRITICAL_ERROR)`. Les échecs en session **`PAPER`** sont isolés et la session est invalidée sans interrompre le bootstrap global.
* **Défaillance ML** :Toute défaillance des oracles ML (exception, non-réponse ou dépassement du budget de latence) entraîne un FAIL immédiat uniquement pour les sessions en mode LIVE, sans bloquer les sessions PAPER.
* **Évaluation Centralisée :** La décision finale est gérée uniquement par `evaluateBootstrapStatus()` après la collecte complète des statuts.
* **Persistance au fil de l'eau :** Chaque statut est écrit immédiatement par le `System Manager` pour garantir la traçabilité en cas de crash durant la phase de HeartCheck.
---

### 5. Conclusion

Ce module garantit la **double intégrité (données et connexion)** et la **cohérence métier** du système. Le succès de cette étape signifie que l'état du portefeuille est validé par rapport aux règles de risque et que tous les canaux de communication (entrée de prix et sortie d'ordres) sont actifs et testés. Le système est alors sécurisé et prêt à réagir à l'ouverture du marché.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1  | HCheckPortfolioReady()            | System Manager | Portfolio Manager  | Vérifie l'instanciation des structures de données et de la stratégie (IBootstrapReadinessCheck) et valide la pipeline d'inférence de l'IExecutionDecisionModel. |
| 2  | updateStatus(PM_Status)           | System Manager | SessionStatusList  | Centralise l'enregistrement du statut technique du PM (ISessionStatusWriter). |
| 3  | HCheckRiskMonitorReady()          | System Manager | Risk Monitor       | Confirme l'activation des limites et le lancement des threads (IBootstrapReadinessCheck)et valide la pipeline d'inférence de l'IStopPredictionModel. |
| 4  | updateStatus(RM_Status)           | System Manager | SessionStatusList  | Centralise l'enregistrement du statut technique du RM (ISessionStatusWriter). |
| 5  | ValidateRiskLimits(RM)            | System Manager | Portfolio Manager  | Demande au PM de valider sa compatibilité technique avec le RM (ICrossValidator). |
| 6  | updateStatus(PM_CrossVal_Status)  | System Manager | SessionStatusList  | Enregistre le résultat de la validation de cohérence métier du PM. |
| 7  | ValidatePortfolioState(PM)        | System Manager | Risk Monitor       | Demande au RM de vérifier la cohérence limites/positions (ICrossValidator). |
| 8  | updateStatus(RM_CrossVal_Status)  | System Manager | SessionStatusList  | Enregistre le résultat de la validation de cohérence métier du RM. |
| 9  | HCheckExternalConnection()        | System Manager | Order Manager      | Teste la liaison courtier via IExternalConnectivity (Timeout 5s). |
| 10 | updateStatus(OM_Check_Status)     | System Manager | SessionStatusList  | Enregistre l'état de la connexion sortante (ordres). |
| 11 | HCheckMarketDataAvailable()       | System Manager | Live Data Hub      | Vérifie la réception effective du flux de prix via MarketDataPort. |
| 12 | updateStatus(LDH_Check_Status)    | System Manager | SessionStatusList  | Enregistre l'état de la connexion entrante (flux). |
| 13 | getFinalStatusList()              | System Manager | SessionStatusList  | Récupère l'agrégat de tous les statuts pour évaluation. |
| 14 | evaluateBootstrapStatus(List)     | System Manager | System Manager     | Arbitrage final basé sur la logique LIVE vs PAPER (IBootstrapCoordinator). |
| 15 | UpdateSystemStatus(READY)         | System Manager | System Manager     | Transition interne vers l'état opérationnel READY_FOR_TRADING. |
| 16 | systemStop(CRITICAL_ERROR)        | System Manager | Error Service      | Arrêt fatal immédiat via IErrorHandler si erreur détectée en mode LIVE. |
| 17 | Wait for MarketOpenEvent()        | System Manager | System Manager     | Mise en veille asynchrone en attente du signal d'ouverture du marché. |

---

### 6. Ports et Interfaces

**IBootstrapReadinessCheck**
* **Implémenté par** : `PortfolioManager`, `RiskMonitor`, `OrderManager`, `LiveDataHub`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Validation de l'intégrité technique (instanciation des structures, état des threads, readiness local).
  * Vérifier que l'état interne est LHB_READY. :
    * Valider que le Buffer Actif reçoit les écritures et que le Buffer Passif est accessible en lecture.
    * Contrôler que le dernier snapshot indexé respecte le seuil de fraîcheur par rapport au temps système.
    * S'assurer de l'absence de backlog bloquant dans la file d'attente de persistance vers la Slow-Lane.
* **Règles d’accès ou d’usage** : Appel synchrone obligatoire en Phase 1. Interdiction de mutation d'état (Read-Only technique).
* **Règle ML** : L'implémentation dans le PM et le RM doit inclure un appel d'inférence de test sur l'interface de l'oracle ML. Si le modèle lève une exception ou ne répond pas dans le temps imparti, le Manager doit retourner un statut FAILED.

**ICrossValidator**
* **Implémenté par** : `PortfolioManager`, `RiskMonitor`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Validation de la cohérence métier inter-domaines (compatibilité Risk Limits vs Portfolio State).
* **Règles d’accès ou d’usage** : Exclusivité au bootstrap. Dépendance requise aux données de marché pour validation des seuils.

**IExternalConnectivity**
* **Implémenté par** : `OrderManager`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Vérification de la liaison physique et logique avec le courtier (Gateway/FIX).
* **Règles d’accès ou d’usage** : Timeout strict de 5000ms. Tout échec est considéré comme une erreur critique en mode LIVE.

**MarketDataPort**
* **Implémenté par** : `LiveDataHub`
* **Injecté dans / Utilisé par** : `PortfolioManager`, `RiskMonitor`
* **Responsabilité opérationnelle** : Diffusion des derniers prix de marché pour la validation de la santé du flux et des Stop-Loss.
* **Règles d’accès ou d’usage** : Lecture seule. Objets immuables. Accès via cache local uniquement.

**IPositionProvider**
* **Implémenté par** : `PortfolioManager`
* **Injecté dans / Utilisé par** : `RiskMonitor`
* **Responsabilité opérationnelle** : Fourniture des snapshots de positions pour contrôle de conformité par le risque.
* **Règles d’accès ou d’usage** : Lecture seule. Interdiction de verrous bloquants (Lock-free ou snapshotting).

**ISessionStatusWriter**
* **Implémenté par** : `Data Integration Layer (DIL)`
* **Injecté dans / Utilisé par** : `SystemManager`
* **Responsabilité opérationnelle** : Persistance centralisée des statuts de validation de chaque composant.
* **Règles d’accès ou d’usage** : Passage exclusif par le fragment `AtomicDBWrite`. Interdiction d'usage par les managers locaux.

**IBootstrapCoordinator**
* **Implémenté par** : `SystemManager`
* **Injecté dans / Utilisé par** : Bootstrap Thread / Main Entry
* **Responsabilité opérationnelle** : Arbitrage final des statuts collectés et transition vers l'état `READY_FOR_TRADING`.
* **Règles d’accès ou d’usage** : Logique de "Fail-fast". Exécution prioritaire sur le pool de threads `CRITICAL`.

**IErrorHandler**
* **Implémenté par** : `ErrorService`
* **Injecté dans / Utilisé par** : Tous les composants
* **Responsabilité opérationnelle** : Gestion et propagation des exceptions fatales lors des échecs de validation.
* **Règles d’accès ou d’usage** : Appel synchrone pour les erreurs bloquantes. Instance unique (Singleton).

**ILogger**
* **Implémenté par** : `Logger Global`
* **Injecté dans / Utilisé par** : Tous les composants
* **Responsabilité opérationnelle** : Audit trail de la séquence de validation et traçabilité des succès/échecs.
* **Règles d’accès ou d’usage** : Mode synchrone exigé durant cette phase de bootstrap pour garantir l'écriture des logs avant un crash potentiel.

**IExecutionDecisionModel**
Interface de validation d'exécution pour le Portfolio Manager.
* **Rôle :** Décision binaire (Go/No-Go) sur les ordres planifiés via calcul de features en temps réel (`last_price`).
* **Implémentation :** Artefacts ML immuables (XGBoost, Regressions, etc.).
* **Contraintes :**
  * **Stateless :** Aucune mémoire entre deux inférences.
  * **Isolation :** Zéro I/O (disque/réseau) lors du calcul.
  * **Ready-Check :** Support d'inférence "à blanc" au bootstrap (Phase 07).

**IStopPredictionModel**
Interface de protection préventive pour le Risk Monitor.
* **Rôle :** Anticipation de sortie de position (Smart Stop-Loss) avant les seuils mécaniques.
* **Implémentation :** Modèles de classification de risque.
* **Contraintes :**
  * **Lecture Seule :** Renvoie un booléen sans modifier l'état du Manager.
  * **Performance :** Temps de calcul déterministe (Priorité Critique).
  * **Isolation :** Ressources mémoire indépendantes de l'oracle du PM.

**ILiveDataReader**
* **Implémenté par** : `Historic Live Hub` (LHB)
* **Utilisé par** : `Portfolio Manager`, `Risk Monitor`
* **Responsabilité opérationnelle** : Fourniture de tranches de données (Slices/Vecteurs) pour les calculs ML en temps constant .
* **Règle HeartCheck** : Doit être testée en Phase 07 via une requête de lecture sur l'index courant pour valider la chaîne de décision.
**Impact architectural :** Sans cette mise à jour, votre `HeartCheck` valide que le moteur ML tourne "à vide", mais ne garantit pas qu'il puisse accéder aux données du LHB. L'intégration de ces étapes sécurise le cycle complet de décision.
