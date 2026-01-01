## `18-PHASE4-Calcul-Strategie`

<p align="center">
  <img src="../img/18-PHASE4-Calcul-Strategie.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'orchestrer le calcul et la persistance des portefeuilles cibles. Il filtre les stratégies éligibles au rebalancement et transforme les configurations actives en décisions d'investissement sécurisées en base de données, tout en adaptant le comportement du système à l'état de santé opérationnel.

---

### 2. Contexte

Ce module est le moteur décisionnel de la **Phase IV**. Il intervient après l'ingestion des données EODHD et s'appuie sur le mode système (`NOMINAL` ou `DEGRADED`) pour sécuriser l'exécution. Son rôle est de centraliser l'intelligence de planification du cycle en décidant, pour chaque session, si le déclenchement du moteur de calcul est requis.

---

### 3. Logique Générale

Le **System Manager (SM)** pilote un flux structuré intégrant résilience et délégation :

* **Vérification de Santé :** Avant tout calcul, le SM interroge son état interne via `getSystemMode()`. Si le mode est `DEGRADED` (ex: suite à un échec d'ingestion EODHD), il applique une politique restrictive via `applyDegradedPolicy()` pour protéger le capital.
* **Auto-Vérification Temporelle :** Pour chaque configuration chargée, le SM valide le calendrier via `isRebalanceDay(Config.ID)`.
* **Exécution Isolée :** Si le test est positif, le SM sollicite le **Strategy Engine** via `executeStrategy(Config)`. Cet appel est conçu comme un socle de délégation, permettant de déporter le calcul vers un autre cœur via le **Job Manager** sans impacter la logique métier.
* **Persistance Unitaire :** Le `TargetPortfolioDTO` produit est immédiatement envoyé au **Data Ingestion Layer (DIL)** via `persistSingleTarget()` pour une écriture transactionnelle.
* **Gestion des Échecs et Alertes :** En cas d'erreur de calcul ou de persistance, le SM déclenche une notification asynchrone via le **Notification Manager** (`notifyStrategyOrderFailure`) pour alerter les opérateurs sans bloquer la boucle de traitement des autres sessions.

---

### 4. Règles Critiques

* **Priorité à la Résilience :** L'état `DEGRADED` prime sur le calcul nominal. Le SM doit impérativement brider les paramètres de stratégie si les données de marché fraîches sont absentes.
* **Centralisation du Calendrier :** Le SM détient la responsabilité du "Go/No-Go" temporel via `isRebalanceDay`, assurant que le **Strategy Engine** n'est activé que pour des opérations productives.
* **Indépendance des Flux :** La persistance est réalisée au fil de l'eau. L'échec d'une écriture ou d'un calcul pour une session spécifique n'entrave pas le traitement des autres stratégies de la boucle.
* **Optimisation des Ressources :** En internalisant la vérification du rebalancement, le SM évite des instanciations inutiles du moteur de calcul et des requêtes de données superflues vers le DAL.
* **Socle de Délégation :** L'appel au moteur de calcul doit rester fonctionnellement pur (Config in / DTO out) pour faciliter le futur passage à une exécution multi-threadée sur un pool `BULK`.
* **Indépendance des Sessions :** L'échec d'une stratégie spécifique ne doit jamais interrompre le cycle global. Chaque erreur génère une alerte isolée et le SM passe à la session suivante.
* * **Traçabilité des Décisions :** Le système doit loguer explicitement les sessions ignorées (`SESSION_SKIPPED`) afin de distinguer un oubli technique d'une décision volontaire basée sur le calendrier.
* **Atomicité de Persistance :** Chaque cible validée doit être écrite via le port de persistance du DIL pour garantir l'intégrité de la source de vérité avant la phase d'exécution d'ordres.


---

### 5. Conclusion

Ce module garantit une gestion rigoureuse et autonome des cycles de trading. En combinant l'auto-vérification du calendrier et la délégation du calcul complexe, il assure une production de cibles optimisée, résiliente et directement exploitable par les phases d'exécution, tout en étamt robuste face aux pannes et préparer pour une montée en charge multi-cœurs.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|getSystemMode()|System Manager|System Manager|Vérification interne du statut opérationnel du système (NOMINAL ou DEGRADED).|
|2|applyDegradedPolicy()|System Manager|System Manager|Application des restrictions métier ou de risque si le mode dégradé est actif.|
|3|logEvent(STRATEGY_CALC_START)|System Manager|SystemLogger|Journalisation du démarrage de la phase de calcul des stratégies.|
|4|loadActiveStrategyConfigs()|System Manager|DataAccessLayer|Requête de récupération des fichiers de configuration JSON pour les stratégies actives.|
|5|return List< ConfigJSON >|DataAccessLayer|System Manager|Retour de la liste des configurations à traiter pour le cycle actuel.|
|6|isRebalanceDay(Config.ID)|System Manager|System Manager|Validation logique permettant de déterminer si la stratégie doit s'exécuter ce jour.|
|7|logEvent(SESSION_START, Config.ID)|System Manager|SystemLogger|Marquage du début de traitement pour une session de stratégie identifiée.|
|8|executeStrategy(Config)|System Manager|StrategyEngine|Appel au moteur de calcul pour transformer la configuration en décisions d'investissement.|
|9|return TargetPortfolioDTO|StrategyEngine|System Manager|Retour de l'objet de transfert contenant le portefeuille cible calculé.|
|10|persistSingleTarget(TargetPortfolioDTO)|System Manager|DataIngestionLayer|Commande de persistance unitaire du résultat via le port de persistance du DIL.|
|11|logEvent(SESSION_COMPLETE, Config.ID)|System Manager|SystemLogger|Journalisation du succès du cycle complet pour une session donnée.|
|12|logEvent(SESSION_ERROR, Config.ID)|System Manager|SystemLogger|Journalisation d'une défaillance technique ou métier durant le traitement de la session.|
|13|notifyStrategyOrderFailure(Config.ID, ErrorCode)|System Manager|Notification Manager|Envoi d'une alerte asynchrone détaillant l'échec de la session pour intervention.|
|14|logEvent(STRATEGY_PHASE_COMPLETE)|System Manager|SystemLogger|Confirmation finale de la clôture de la Phase IV avant passage à l'exécution.|

---

### 6. Ports et Interfaces



---


