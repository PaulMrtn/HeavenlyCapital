## `07-PHASE1-Validation-Croisee-HeartCheck`

<p align="center">
  <img src="07-PHASE1-Validation-Croisee-HeartCheck.jpg" width="900">
</p>


### 1. Objectif

La finalité de ce module est d'effectuer la **validation croisée finale** et un **contrôle de santé global (`HeartCheck`)** sur l'ensemble du système. Il garantit la cohérence opérationnelle et la sécurité des liens entre les managers avant de faire la transition vers l'état `READY_FOR_TRADING` et le mode veille.

---

### 2. Contexte

Cette étape est la **dernière de la Phase 1 (Initialisation)**. Elle est exécutée après le succès du **chargement statique** (Phase 05) et de l'**initialisation du flux temps réel** (Phase 06). Elle est critique car elle confirme que les données chargées par un manager sont compatibles avec les règles et l'état des autres, agissant comme le **point de non-retour sécurisé** avant de donner le feu vert pour le trading.

---

### 3. Logique Générale

Le **`System Manager`** orchestre une série de vérifications en cascade pour recueillir le statut opérationnel de chaque manager et la cohérence inter-composants :

* **Vérifications Unitaires (Prêt à Opérer) :**
    * **`HCheckPortfolioReady()` :** Le `Portfolio Manager (PM)` confirme que toutes ses structures de données sont chargées et que sa logique de stratégie est instanciée correctement.
    * **`HCheckRiskMonitorReady()` :** Le `Risk Monitor (RM)` confirme que ses limites de risque sont activées et que ses mécanismes de surveillance (thread d'écoute) sont lancés.

* **Validations Croisées (Cohérence Métier) :**
    * **`ValidateRiskLimits(RM)` (par le PM) :** Le `PM` vérifie la compatibilité de son état avec les contraintes du `RM`. *Exemple : Vérifier que la marge requise pour toutes les positions du portefeuille ne dépasse pas le solde de liquidité disponible.*
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
