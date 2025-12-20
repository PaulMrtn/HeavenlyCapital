## `04-PHASE1-Instanciation-Managers-Locaux`

<p align="center">
  <img src="../img/04-PHASE1-Instanciation-Managers-Locaux.jpg" width="900">
</p>


### 1. Objectif

La finalité de ce module est d'allouer la couche d'exécution métier du système en instanciant **toutes les sessions de trading actives**. Cela comprend la création et la liaison des triplets de managers locaux (**Portfolio Manager**, **Risk Monitor**, **Order Manager**) pour chaque stratégie.

---

### 2. Contexte

Cette étape s'inscrit après l'initialisation des **services d'infrastructure persistants** (Singletons, Pools de Threads) et avant le chargement des données. Elle est cruciale car elle **lie la stratégie (PM)** aux **ressources globales (LDH, IG)** et au **mécanisme de sécurité (RM)**. Elle prépare la structure logique qui opèrera pendant la session de trading.

---

### 3. Logique Générale

Le **`System Manager`** orchestre une boucle itérative pour chaque identifiant de session récupéré dans la configuration. Pour chaque session :

1.  L'entité **`TradingSession`** est créée pour détenir l'identité et l'état local de la stratégie.
2.  Les trois managers locaux (`PM`, `RM`, `OM`) sont instanciés en **injectant leurs dépendances minimalistes** (configurations et Singletons globaux nécessaires).
3.  Les **canaux de communication locaux** sont établis :
    * Le **`PM` est lié à l'`OM`** pour la soumission d’ordres d’investissement (selon une stratégie définie).
    * Le **`RM` est lié à l'`OM`** pour l'émission d'ordres d'urgence (Stop-Loss).
    * Le **`RM` obtient la référence du `PM`** (`setPortfolioReference`) pour la lecture de l'état du portefeuille (position) et le déclenchement du **Kill Switch** asynchrone.
4.  Une vérification d'intégrité minimale (**`HCheckSessionReady`**) est effectuée pour s'assurer que tous les canaux critiques sont correctement établis avant de passer à l'étape suivante.

---

### 4. Règles Critiques

* **Couplage Faible :** Le **`Portfolio Manager`** est maintenu **minimaliste**. Il ne dépend pas de l'`IBKR Gateway` ou du `Risk Monitor` pour son exécution principale.
* **Séparation des Canaux :** Le chemin de la **performance** (`PM` $\rightarrow$ `OM`) est distinct du canal de la **sécurité** (`RM` $\rightarrow$ `OM`). La vérification de risque par le `RM` est hors-bande.
* **Isolation du Risque :** La création d'un **triplet de managers par session** garantit qu'un dysfonctionnement dans une stratégie ne peut pas compromettre les autres sessions actives.
* **Lien de Surveillance :** Le **`RM`** doit avoir une référence active et persistante au **`PM`** pour pouvoir lire la position mise à jour (nécessaire à la construction de l'ordre de liquidation) et pour exécuter l'arrêt d'urgence.

---

### 5. Conclusion

Ce module garantit que l'architecture métier est instanciée et que tous les **canaux de communication critiques** (Ordres, Surveillance, Données) entre les composants locaux sont établis. La structure du système est ainsi **isolée et sécurisée**, prête à charger les données initiales et à passer en mode veille de trading.


---

| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | getSessionsToLoad() | System Manager | Config | Récupération synchrone de la liste des identifiants de sessions actives pour la journée. |
| 2 | new TradingSession(ID, Status) | System Manager | TradingSession | Instanciation de l'objet entité portant l'état et l'identité de la session. |
| 3 | getConfigs(SessionID) | System Manager | Config | Extraction des paramètres spécifiques (seuils de risque, actifs) de la session. |
| 4 | new PortfolioManager(S, C, LDH) | System Manager | Portfolio Manager | Création du PM avec injection du LDH pour la réception des flux de prix. |
| 5 | new RiskMonitor(S, C, LDH) | System Manager | Risk Monitor | Création du RM avec injection du LDH pour la surveillance temps réel. |
| 6 | new OrderManager(S, IG) | System Manager | Order Manager | Création de l'OM avec injection de la Gateway IBKR pour l'exécution. |
| 7 | setOrderManager(OM) | System Manager | Portfolio Manager | Établissement du canal de transmission des ordres stratégiques. |
| 8 | setOrderManager(OM) | System Manager | Risk Monitor | Établissement du canal de transmission des ordres de liquidation (Urgence). |
| 9 | setPortfolioReference(PM) | System Manager | Risk Monitor | Injection de la référence du PM vers le RM pour la lecture des positions. |
| 10 | HCheckSessionReady(ID) | System Manager | System Manager | Auto-vérification finale de la validité des liens d'instanciation de la session. |
| 11 | call_05-PHASE1... | System Manager | System Manager | Passage à l'étape de chargement parallèle des données historiques. |


---

### NOTE
