## `07-PHASE1-Validation-Croisee-HeartCheck`

<p align="center">
  <img src="../img/07-PHASE1-Validation-Croisee-HeartCheck.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'effectuer la **validation croisée finale** et un **contrôle de santé global (`HeartCheck`)** sur l'ensemble du système. Il garantit la cohérence opérationnelle et la sécurité des liens entre les managers avant de faire la transition vers l'état `READY_FOR_TRADING` et le mode veille.

---

### 2. Contexte

Cette étape est la **dernière de la Phase 1 (Pre-Trade)**. Elle est exécutée après le succès du **chargement statique** (Phase 05) et de l'**initialisation du flux temps réel** (Phase 06). Elle est critique car elle confirme que les données chargées par un manager sont compatibles avec les règles et l'état des autres, agissant comme le **point de non-retour sécurisé** avant de donner le feu vert pour la session de trading.

---

### 3. Logique Générale

Le **`System Manager`** orchestre une série de vérifications en cascade pour recueillir le statut opérationnel de chaque manager et la cohérence inter-composants :

* **Vérifications Unitaires (Prêt à Opérer) :**
    * **`HCheckPortfolioReady()` :** Le `Portfolio Manager (PM)` confirme que toutes ses structures de données sont chargées et que sa logique de stratégie est instanciée correctement.
    * **`HCheckRiskMonitorReady()` :** Le `Risk Monitor (RM)` confirme que ses limites de risque sont activées et que ses mécanismes de surveillance (thread d'écoute) sont lancés.

* **Validations Croisées (Cohérence Métier) :**
    * **`ValidateRiskLimits(RM)` (par le PM) :** Le `PM` vérifie la compatibilité de son état avec les contraintes du `RM`. *Exemple : Le PM vérifie qu'il s'est correctement abonné au topic de notification du RM pour les événements de liquidation ou de déclenchement de Stop-Loss.*
    * **`ValidatePortfolioState(PM)` (par le RM) :** Le `RM` vérifie que les limites qu'il a chargées sont applicables à l'état du `PM`. *Exemple : Confirmer qu'aucun Stop-Loss chargé n'est déjà dépassé par les prix actuels disponibles dans le `LDH`.*

* **Vérification de l'Infrastructure :**
    * **`HCheckExternalConnection()` (par l'OM) :** L'`Order Manager (OM)` confirme que la connexion physique et logique avec l'API du courtier (`IBKR Gateway`) est active et capable d'envoyer des ordres.
    * **`HCheckMarketDataAvailable()` (par le LDH) :** Le `Live Data Hub (LDH)` confirme qu'il reçoit un flux actif et récent de données de marché.

Tous les statuts de vérification sont collectés dans une liste.

---

### 4. Règles Critiques

* **Tolérance aux Erreurs Asymétrique :**
    * Toute défaillance de vérification concernant une session **`LIVE`** entraîne un arrêt immédiat et fatale via **`systemStop(CRITICAL_ERROR)`**.
    * Les échecs de session **`PAPER`** sont isolés, logués, et la session est invalidée, permettant au *bootstrapping* de continuer pour les sessions critiques.
* **Évaluation Centralisée :** La décision d'arrêt ou de poursuite est gérée uniquement par la fonction **`evaluateBootstrapStatus()`** du `System Manager` après que tous les résultats ont été recueillis.
* **Finalité :** Le système ne passe en état **`READY_FOR_TRADING`** qu'après le succès de toutes les vérifications LIVE, puis se place en attente asynchrone (`Wait for MarketOpenEvent()`).

---

### 5. Conclusion

Ce module garantit la **double intégrité (données et connexion)** et la **cohérence métier** du système. Le succès de cette étape signifie que l'état du portefeuille est validé par rapport aux règles de risque et que tous les canaux de communication (entrée de prix et sortie d'ordres) sont actifs et testés. Le système est alors sécurisé et prêt à réagir à l'ouverture du marché.

---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | HCheckPortfolioReady() | System Manager | Portfolio Manager | Vérifie l'instanciation correcte des structures de données et de la logique de stratégie. |
| 2 | HCheckRiskMonitorReady() | System Manager | Risk Monitor | Confirme l'activation des limites et le lancement des threads de surveillance. |
| 3 | ValidateRiskLimits(RM) | System Manager | Portfolio Manager | Demande au PM de valider sa compatibilité technique avec les notifications du RM. |
| 4 | updateStatus(PM_Validation_Status) | Portfolio Manager | SessionStatusList | Enregistre le résultat de la validation croisée du PM dans la structure de données centrale. |
| 5 | ValidatePortfolioState(PM) | System Manager | Risk Monitor | Demande au RM de vérifier que les limites chargées sont cohérentes avec l'état actuel du PM. |
| 6 | updateStatus(RM_Validation_Status) | Risk Monitor | SessionStatusList | Enregistre le résultat de la validation de cohérence du RM. |
| 7 | HCheckExternalConnection() | System Manager | Order Manager | Teste la connectivité physique et logique avec l'API du courtier (ex: IBKR). |
| 8 | updateStatus(OM_Check_Status) | Order Manager | SessionStatusList | Enregistre l'état de la connexion sortante (ordres). |
| 9 | HCheckMarketDataAvailable() | System Manager | Live Data Hub | Vérifie la réception effective d'un flux de prix récent (Données de marché). |
| 10 | updateStatus(LDH_Check_Status) | Live Data Hub | SessionStatusList | Enregistre l'état de la connexion entrante (flux). |
| 11 | getFinalStatusList() | System Manager | SessionStatusList | Récupère l'agrégat de tous les statuts pour évaluation finale. |
| 12 | evaluateBootstrapStatus(List) | System Manager | System Manager | Analyse les résultats (Logique de tolérance Live vs Paper). |
| 13 | UpdateSystemStatus(READY_FOR_TRADING) | System Manager | System Manager | Transition interne vers l'état opérationnel final si succès. |
| 14 | Wait for MarketOpenEvent() | System Manager | System Manager | Mise en veille asynchrone en attente du signal d'ouverture du marché. |


