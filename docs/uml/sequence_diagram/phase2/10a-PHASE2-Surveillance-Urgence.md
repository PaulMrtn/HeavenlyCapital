## `10a-PHASE2-Surveillance-Urgence`

<p align="center">
<img src="../img/10a-PHASE2-Surveillance-Urgence.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de garantir la **détection immédiate** d'une violation critique des limites de risque et de déclencher l'exécution d'un ordre de liquidation (Stop-Loss ou Kill-Switch) avec une **priorité maximale absolue**, préservant ainsi le capital.

---

### 2. Contexte

Ce processus s'inscrit dans la **Phase II (In-Trade)** et est piloté par le **`RiskMonitor`**, un composant fonctionnant sur un thread de haute priorité dédié. Il est déclenché de manière asynchrone par l'événement **`notifySnapshotReady`** émis par le `LiveDataHub`, assurant que la surveillance s'effectue sur des données de prix complètes et cohérentes, à une fréquence régulière et critique (par exemple, toutes les minutes).

---

### 3. Logique Générale

Le `RiskMonitor` fonctionne en boucle continue. À chaque signal `SnapshotReady`, il initie un double processus de récupération synchrone (Fetch) : il lit le prix dans le **`DataCache`** et l'état de la position auprès du **`PortfolioManager`**. Muni de ces deux données, il procède à l'évaluation des seuils (`checkThresholds`). Si un seuil est franchi, il crée un ordre d'urgence, journalise l'incident de manière bloquante, puis soumet cet ordre à l'`OrderManager` avec une priorité **`CRITICAL`**. L'ordre est ensuite sécurisé dans la `PriorityQueue` de l'OM avant d'être routé pour l'exécution physique.

---

### 4. Règles Critiques

* **Déclenchement et Découplage :** Le `RiskMonitor` est entièrement découplé de la logique de trading standard. Il ne dépend que des sources de données passives (caches) et du `PortfolioManager` pour son état, et agit uniquement sur le signal cohérent du `Snapshot`.
* **Audit Synchrone :** L'enregistrement de l'incident (`logCriticalEvent`) est **obligatoirement synchrone et bloquant** (étape 9). Le `RiskMonitor` doit attendre la confirmation de l'écriture de la preuve d'audit avant de procéder à la soumission de l'ordre. C'est le prix de la conformité et de l'irréfutabilité.
* **Priorité Maximale :** L'ordre est soumis avec la priorité **`CRITICAL`**. L'`OrderManager` doit garantir que cet ordre est inséré en tête de la `PriorityQueue` et traité avant tout ordre `STANDARD` ou `NORMAL`.
* **Contrôle du Thread :** Le `RiskMonitor` utilise des appels synchrones pour l'audit et la soumission d'ordre (jusqu'à l'étape d'enfilement confirmée) afin de garantir que l'ordre est pris en charge avant que le thread ne soit libéré pour le cycle de surveillance suivant.

---

### 5. Conclusion

Le module **`10a-PHASE2-Surveillance-Urgence`** est le mécanisme de défense à haute priorité du système. Il garantit que toute violation de risque est détectée, auditée et contrée par une action immédiate (liquidation) dont la priorité d'exécution est formellement supérieure à toute autre opération de trading en cours.
