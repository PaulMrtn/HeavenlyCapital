## `09-PHASE2-Flux-Donnees-Globaux`

<p align="center">
  <img src="../img/09-PHASE2-Flux-Donnees-Globaux.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'orchestrer le traitement complet des données de marché en temps réel, garantissant le **parallélisme** et le **découplage strict** entre les exigences de faible latence (Fast-Lane) et les exigences d'audit (Slow-Lane).

---


### 2. Contexte

Ce module s'inscrit comme le premier grand processus de la Phase II (In-Trade), démarrant dès l'ouverture du marché. Il est la porte d'entrée de toutes les données de prix pour l'ensemble du système de trading. Il existe pour **isoler** les opérations rapides et critiques (nécessaires pour le risque et l'exécution) des opérations lourdes et lentes (nécessaires pour la conformité et l'historique), assurant ainsi que l'une ne bloque jamais l'autre.

---


### 3. Logique Générale

Le processus est déclenché par le `SystemManager` qui ordonne au `LiveDataHub` de commencer l'acquisition des données. Une fois l'écoute des Ticks démarrée via `IBKR Gateway`, le `LiveDataHub` initie **simultanément** deux processus indépendants modélisés par le fragment parallèle :

* **Fast-Lane (Référence 09a) :** Le flux ultra-rapide et non bloquant qui conduit les `MarketQuote` agrégés vers le `DataCache` via une queue asynchrone pour une disponibilité immédiate (destination : Risk Monitor / Portfolio Manager).
* **Slow-Lane (Référence 09b) :** Le flux périodique et auditable qui transfère les buffers de données agrégées vers le `DIL` pour une persistance en masse (Bulk I/O) vers la base de données (destination : Audit / Historique).

L'exécution des deux flux se poursuit en parallèle jusqu'à la fermeture du marché.

---


### 4. Règles Critiques

* **Garantie de Parallélisme :** L'utilisation du fragment Parallèle est fondamentale pour garantir que la charge de travail du `Pool I/O Bulk` (Slow-Lane) ne perturbe jamais la boucle critique du `Pool I/O Real-Time` (Fast-Lane).
* **Source Unique :** Le `LiveDataHub` agit comme source unique de vérité et déclencheur pour les deux flux, assurant que les données Fast-Lane et Slow-Lane proviennent du même calcul d'agrégation.
* **Résilience Intrinsèque :** Bien que les flux soient indépendants, le mécanisme de surveillance de la latence du `09a` reste prioritaire. Une défaillance de la Fast-Lane entraîne un arrêt (Kill Switch) potentiel du système entier, y compris de la Slow-Lane.

---

### 5. Conclusion

Ce module établit le socle de données de marché pour la Phase II. Il garantit que les exigences contradictoires de **rapidité (exécution)** et de **traçabilité (audit)** sont satisfaites simultanément et sans compromis sur la performance, en exploitant l'isolation complète des ressources de calcul et d'I/O.
