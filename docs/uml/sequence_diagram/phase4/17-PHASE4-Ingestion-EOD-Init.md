## `17-PHASE4-Ingestion-EOD-Init`

<p align="center">
  <img src="../img/17-PHASE4-Ingestion-EOD-Init.jpg" width="900">
</p>

---

### 1. Objectif

Ce module a pour finalité de garantir l'**ingestion résiliente, le traitement et la persistance atomique** des données multidimensionnelles (marché, fondamentaux, dérivés, ...) provenant du fournisseur **EODHD**. Il constitue la **source de vérité unique** pour les données de référence qui seront exploitées par le *Strategy Engine* (`18-PHASE4`) lors du calcul du Target Portfolio.

---

### 2. Contexte

La séquence s'exécute au sein de la **Phase IV (Préparation du Target Portfolio)**, immédiatement après la validation du Jour Ouvré et de la connectivité réseau. Le processus, orchestré par le **Data Ingestion Layer (DIL)**, est indispensable car il assure la **préparation analytique** (ajustements techniques et calculs intermédiaires) avant de rendre ces données disponibles pour la prise de décision stratégique.

---

### 3. Logique Générale

Le processus est orchestré par le **DIL** de manière séquentielle avec une gestion de basculement d'état :

* **Récupération Résiliente :** Le DIL interroge l'API via la fonction métier `fetchEODHDData()`. Cet appel intègre un **Timeout** et une politique de **Retry** pour absorber les pannes réseau transitoires.
* **Bascule en Mode Dégradé :** En cas d'échec persistant de récupération, le système émet une alerte via le `Notification Manager`, logue l'erreur, et le `System Manager` bascule en **`MODE_DEGRADED`** pour permettre au cycle de continuer sans bloquer le démarrage.
* **Vérification d'Intégrité :** Les données brutes récupérées (`EOD_Data_DTO`) subissent une validation métier (`checkDataIntegrity`) pour exclure les jeux de données corrompus ou les valeurs illogiques.
* **Calcul Intermédiaire :** Les données validées sont transformées (`processMarketData`) pour intégrer les ajustements (splits, dividendes) et générer le **`Processed_MarketData_DTO`**.
* **Persistance Atomique :** Les données calculées sont persistées via le fragment **`DIL-AtomicDBWriteProcess`**, garantissant une écriture transactionnelle "tout ou rien".

---

### 4. Règles Critiques

* **Résilience Non-Bloquante :** Contrairement aux phases précédentes, l'échec d'ingestion EODHD ne déclenche pas d'arrêt système mais une transition vers le **`MODE_DEGRADED`**, assurant la continuité opérationnelle.
* **Intégrité en Cascade :** Le traitement (`processMarketData`) n'est exécuté que si la vérification d'intégrité réussit. La persistance n'est initiée que si le traitement génère un DTO valide.
* **Atomicité Absolue :** Le `DIL-AtomicDBWriteProcess` est le seul garant de l'intégrité des données stratégiques sur disque. Toute défaillance lors de l'écriture entraîne un `rollback` immédiat.
* **Isolation des Flux :** Le système sépare strictement la donnée brute fournisseur (`EOD_Data_DTO`) de la donnée enrichie et auditée (`Processed_MarketData_DTO`) utilisée par la stratégie.

---

### 5. Conclusion

Le module **17-PHASE4-Ingestion-EODHD-Init** constitue la **chambre forte analytique** indispensable au cycle de trading. En sécurisant l'extraction des données fondamentales et de marché depuis **EODHD** et en assurant leur transformation atomique, il établit un socle de confiance pour le *Strategy Engine*. Sa capacité de basculement en mode dégradé garantit que l'infrastructure de trading reste résiliente face aux instabilités des fournisseurs tiers.

---

|ID|Fonction / Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|startEODIngestion()|System Manager|Data Ingestion Layer|Commande initiale lançant le processus de récupération des données EOD.|
|2|logEvent(EOD_INGESTION_START)|Data Ingestion Layer|Log Session|Journalisation du début de l'ingestion pour l'audit de session.|
|3|fetchEODHDData()|Data Ingestion Layer|EODHD API|Appel synchrone à l'API externe incluant la logique de Timeout et de Retry.|
|4|response(EOD_Data_DTO)|EODHD API|Data Ingestion Layer|Retour du flux de données brutes structurées.|
|5|sendAlert(EOD_API_DOWN)|Data Ingestion Layer|Notification Manager|Alerte asynchrone si l'API ne répond pas après épuisement des tentatives.|
|6|logError(EOD_FETCH_FAIL)|Data Ingestion Layer|Log Session|Journalisation de l'échec de récupération réseau.|
|7|eodIngestionComplete(Failure)|Data Ingestion Layer|System Manager|Notification d'échec technique au superviseur.|
|8|setSystemMode(DEGRADED)|System Manager|System Manager|Bascule en mode dégradé pour continuer le cycle sans les données du jour.|
|9|checkDataIntegrity(EOD_Data_DTO)|Data Ingestion Layer|Data Ingestion Layer|Validation métier de la structure et du contenu des données reçues.|
|10|processMarketData(EOD_Data_DTO)|Data Ingestion Layer|Data Ingestion Layer|Transformation des données (splits, ajustements) en Processed_MarketData_DTO.|
|ref|DIL-AtomicDBWriteProces|Data Ingestion Layer|Persistence Port|Fragment de persistance transactionnelle de la donnée traitée.|
|11|logEvent(EOD_INGESTION_COMPLETE)|Data Ingestion Layer|Log Session|Journalisation du succès total du flux d'ingestion.|
|12|eodIngestionComplete(Success)|Data Ingestion Layer|System Manager|Confirmation de réussite permettant de rester en mode NOMINAL.|
|13|sendAlert(EOD_INTEGRITY_FAILED)|Data Ingestion Layer|Notification Manager|Alerte signalant que les données reçues sont corrompues.|
|14|logCriticalError(EOD_INGESTION_FAIL)|Data Ingestion Layer|Log Session|Journalisation de l'erreur d'intégrité bloquante.|
|15|eodIngestionComplete(Failure)|Data Ingestion Layer|System Manager|Notification d'échec métier suite à la corruption des données.|
|16|setSystemMode(DEGRADED)|System Manager|System Manager|Bascule de sécurité pour protéger le Strategy Engine.|

---

### 6. Ports et Interfaces

