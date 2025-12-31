## `16-PHASE4-Ingestion-EOD-Init`

<p align="center">
  <img src="../img/17-PHASE4-Ingestion-EOD-Init.jpg" width="900">
</p>

---

### 1. Objectif

Ce module vise à garantir l'**ingestion, le traitement et la persistance atomique** des données de marché de fin de journée (EOD) les plus récentes. Il est la **seule source de vérité** pour les données de marché qui seront utilisées par le *Strategy Engine* (`18-PHASE4`).

---

### 2. Contexte

La séquence s'exécute dans la **Phase IV (Préparation du Target Portfolio)**, après la validation du Jour Ouvré et de la connectivité. Le processus, orchestré par le `Data Ingestion Layer` (DIL), est indispensable car il assure la **préparation analytique** des données (calculs intermédiaires) avant de les rendre disponibles pour la prise de décision stratégique.

---

### 3. Logique Générale

Le processus est orchestré par le `DIL` de manière séquentielle et conditionnelle :

* **Récupération Résiliente :** Le `DIL` obtient les données de l'`EODHD API` via un appel résilient (`REF-API-RESILIENT-CALL`) qui gère de manière autonome les pannes réseau transitoires. **Cette référence reste à être formalisée sous forme de schéma.**
* **Vérification d'Intégrité :** Les données brutes récupérées sont soumises à la validation métier (`checkDataIntegrity`) pour exclure les jeux de données corrompus (ex: données manquantes ou valeurs illogiques).
* **Calcul Intermédiaire :** Les données intègres subissent ensuite le traitement nécessaire (`processMarketData`), tel que l'ajustement des prix (splits/dividendes) ou le calcul de facteurs fondamentaux, pour générer le `Processed_Data_DTO` prêt pour l'audit et la stratégie.
* **Persistance Atomique :** Les données calculées sont persistées en base de données via le fragment **`REF-DIL-AtomicDBWriteProces`**, qui garantit une écriture **tout ou rien** via une transaction.
* **Résultat :** Le statut final (Succès ou Échec) est remonté au `System Manager` pour la prise de décision sur la poursuite du cycle.
---

### 4. Règles Critiques

* **Uniformité de la Résilience :** L'appel à l'`EODHD API` utilise le même patron de résilience que les vérifications de connectivité, assurant une gestion des erreurs I/O homogène.
* **Intégrité en Cascade :** Le traitement (`processMarketData`) n'est exécuté que si la vérification d'intégrité réussit. La persistance atomique n'est initiée que si le traitement réussit. L'échec de l'une de ces étapes doit entraîner une fin de processus sécurisée.
* **Atomicité Absolue :** Le `REF-DIL-AtomicDBWriteProces` est le seul garant de l'intégrité des données stratégiques. Toute défaillance durant l'écriture doit déclencher un `rollback` immédiat et complet.
* **Arrêt sur Défaillance (Fail-Fast) :** Tout échec critique (récupération persistante, intégrité compromise, erreur atomique) doit générer un statut d'échec nécessitant une intervention du `System Manager` et, potentiellement, l'arrêt du processus.

---

### 5. Conclusion

Le module `17-PHASE4-Ingestion-EOD-Init` est la **chambre forte** des données du cycle. Il garantit non seulement la récupération fiable de la source externe, mais aussi l'**auditabilité** et la **préparation analytique** des données. En assurant la qualité et la persistance atomique des informations de marché traitées, il établit la base indispensable de confiance pour le démarrage des calculs stratégiques.

