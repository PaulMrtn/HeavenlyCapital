## `04-PHASE1-Instanciation-Managers-Locaux`

<p align="center">
  <img src="img/04-PHASE1-Instanciation-Managers-Locaux.jpg" width="900">
</p>


### 1. Objectif

La finalité de ce module est d'allouer la couche d'exécution métier du système en instanciant **toutes les sessions de trading actives**. Cela comprend la création et la liaison des triplets de managers locaux (**Portfolio Manager, Risk Monitor, Order Manager**) pour chaque stratégie.

---

### 2. Contexte

Cette étape s'inscrit après l'initialisation des **services d'infrastructure persistants** (Singletons, Threads Pools) et avant le chargement des données. Elle est cruciale car elle **lie la stratégie (PM)** aux **ressources globales (LDH, IG)** et au **mécanisme de sécurité (RM)**. Elle prépare la structure logique qui opèrera pendant la session de trading.

---

### 3. Logique Générale

Le **`System Manager`** orchestre une boucle itérative pour chaque identifiant de session récupéré dans la configuration. Pour chaque session :

1.  L'entité **`TradingSession`** est créée pour détenir l'identité et l'état local de la stratégie.
2.  Les trois managers locaux (`PM`, `RM`, `OM`) sont instanciés en **injectant leurs dépendances** (configurations spécifiques à la session et les Singletons globaux nécessaires).
3.  Les **canaux de communication locaux** sont établis :
    * Le `PM` est lié à l'`OM` pour la **soumission d'ordres directe** (performance).
    * Le **`RM` établit sa référence au `PM`** (`setControlReference`) pour la lecture de l'état du portefeuille et le déclenchement du **Kill Switch** (sécurité).
4.  Une vérification d'intégrité minimale (**`HCheckSessionReady`**) est effectuée pour s'assurer que les managers sont correctement liés avant de passer à l'étape suivante.

---

### 4. Règles Critiques

* **Couplage Faible :** Le **`Portfolio Manager`** est maintenu **minimaliste**. Il ne dépend pas directement de l'`IBKR Gateway` ; sa seule voie d'accès au marché passe par l'`Order Manager`.
* **Séparation des Canaux :** Le chemin de la **performance** (`PM` $\rightarrow$ `OM`) est distinct du canal de la **sécurité** (`RM` $\leftrightarrow$ `PM`). La vérification de risque n'intervient pas de manière synchrone avant chaque ordre.
* **Isolation du Risque :** La création d'un **triplet de managers par session** garantit qu'un dysfonctionnement dans une stratégie ne peut pas compromettre les autres sessions actives.
* **Persistance :** Tous les managers locaux créés restent actifs et en mémoire pendant toute la durée du marché.

---

### 5. Conclusion

Ce module garantit que l'architecture métier est instanciée et que tous les **canaux de communication critiques** (Ordres, Surveillance, Données) entre les composants locaux sont correctement établis. Le système est ainsi prêt à charger les données initiales et à passer en mode veille de trading.
