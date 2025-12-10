## `05-PHASE1-Chargement-Parallele`

<p align="center">
  <img src="img/05-PHASE1-Chargement-Parallele.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de charger l'état initial complet de toutes les sessions de trading **en parallèle**. Il vise à minimiser le temps de latence au démarrage en exécutant les opérations de lecture de base de données (I/O) de manière concurrente.

---

### 2. Contexte

Cette étape se situe immédiatement après l'**instanciation des managers locaux** (Phase 04) et utilise les **Pools de Threads** (initialisés en Phase 03). Elle est la première phase à exploiter la parallélisation pour préparer les managers (`PM` et `RM`) avec les données nécessaires à leur fonctionnement.

---

### 3. Logique Générale

Le **`System Manager`** délègue entièrement la charge de travail au **`Thread Manager`**. Pour chaque session active :

1.  Deux commandes de travail (`Job`) sont créées : une pour le **`Portfolio Manager`** (`loadInitialState`) et une pour le **`Risk Monitor`** (`loadRiskSnapshot`).
2.  Ces commandes sont soumises au `Thread Manager` avec l'instruction d'exécution **parallèle**.
3.  Des **PoolWorkers** distincts (issus des pools alloués) exécutent les tâches, demandant simultanément leurs données respectives au `Database Connector`.
4.  Une fois les données reçues, chaque manager (PM et RM) effectue son **contrôle d'intégrité métier** (`HCheckDataIntegrity`) sur les objets chargés.
5.  Le `Thread Manager` attend le résultat de toutes les tâches soumises et renvoie la liste des statuts au `System Manager` pour évaluation finale.
---

### 4. Règles Critiques

* **Non-Blocage :** Le thread du **`System Manager`** ne doit pas être bloqué par l'attente de la base de données. Il est libéré dès la soumission des tâches.
* **Tolérance aux Erreurs Asymétrique :**
    * Tout échec de chargement ou de validation d'une session **`LIVE`** est une erreur fatale. Le `System Manager` doit immédiatement appeler **`systemStop(CRITICAL_ERROR)`**.
    * L'échec d'une session **`PAPER`** est logué, la session est marquée Invalide et retirée du flux, mais le *bootstrapping* **continue** pour les sessions valides.
* **I/O Maximisation :** Le parallélisme est utilisé pour masquer la latence des opérations I/O bloquantes de la base de données.
* **Vérification Métier :** Le **`HCheckDataIntegrity`** est un garde-fou. Il assure la **cohérence logique** des données (ex. : la somme des lots correspond à la position totale) avant la mise en service du manager.

---

### 5. Conclusion

Ce module garantit un **démarrage rapide et résilient** du système en gérant efficacement l'attente I/O. Il assure également que chaque manager local (PM et RM) est prêt et que son état initial est validé. Le succès de cette étape permet de passer à l'initialisation du flux de données temps réel.
