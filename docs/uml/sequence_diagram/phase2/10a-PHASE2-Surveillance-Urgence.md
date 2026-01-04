## `10a-PHASE2-Surveillance-Urgence`

<p align="center">
<img src="../img/10a-PHASE2-Surveillance-Urgence.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'assurer une **surveillance critique et temps réel du capital**. Il doit détecter toute violation des limites de risque (techniques ou de marché) via une analyse déterministe s'appuyant sur un modèle de décision. Sa mission est de déclencher une liquidation avec une **priorité maximale absolue** tout en garantissant l'irréfutabilité par un audit bloquant, sans jamais impacter la performance du thread de stratégie.

---

### 2. Contexte

Ce processus est le cœur défensif de la **Phase II (In-Trade)**. Il est piloté par le **`RiskMonitor`**, opérant sur un thread dédié à haute priorité (scheduling FIFO/Real-time). Contrairement aux architectures classiques, il est **réveillé de manière asynchrone** par l'**`EventBus`**. Il utilise un mécanisme de **Shared Memory State** pour obtenir l'état du portefeuille, garantissant qu'aucune contention ne ralentit la surveillance.

---

### 3. Logique Générale

Le flux repose sur trois piliers de données synchronisés pour garantir une décision atomique :

1. **Réveil Contextuel** : L'**`EventBus`** diffuse `notifyDataReady(MarketStateContext)`. Ce contexte transporte l'`index` de synchronisation qui verrouille temporellement la lecture dans le **`Live Historic Buffer (LHB)`**.
2. **Capture de l'Exposition (Pattern Shared Memory)** : Le `RiskMonitor` consulte le **`PositionExposureStore`**. Il récupère un objet immuable **`PositionExposureSnapshot`** via une lecture **Lock-Free**. Ce snapshot contient les positions nettes, le levier et les marges déjà calculés par le `PortfolioManager`.
3. **Extraction Marché (Raw Data Access)** : Le moniteur extrait une tranche de données brutes (`RawBufferSlice`) directement depuis le **LHB** en utilisant l'index du contexte.
4. **Inférence & Évaluation** :
  * **Pipeline Interne** : Le `RiskMonitor` transforme les données brutes en entrées pour ses modèles (Feature Engineering local).
  * **Exécution du Modèle** : Évaluation de la conformité (Baseline, ML, ou règles métier).
5. **Exécution d'Urgence** : Si une violation est prédite, le système bascule dans un flux de liquidation forcée incluant un audit synchrone avant l'envoi vers l'**`OrderManager`**.

---

### 4. Règles Critiques

* **Sémantique Lock-Free (IPositionExposureReader)** : La lecture du snapshot d'exposition ne doit utiliser aucun verrou (mutex/semaphore). L'implémentation doit reposer sur un `AtomicReference` avec un **swap atomique** côté `PortfolioManager` pour garantir une latence de lecture constante ().
* **Immuabilité Stricte** : Le `PositionExposureSnapshot` est un **Value Object** pur. Une fois instancié, aucune de ses propriétés ne peut être modifiée. Toute mise à jour implique la création d'un nouvel objet par le `PortfolioManager`.
* **Autonomie du Feature Engineering** : Le `RiskMonitor` est responsable de sa propre transformation de données à partir des "Slices" brutes du LHB. Cela évite de surcharger le LHB avec des calculs spécifiques à chaque moniteur.
* **Audit Bloquant et Synchrone** : L'étape `logCriticalEvent` (ID 7) est la seule étape volontairement lente. Elle **doit confirmer l'écriture physique (fsync)** de l'incident avant que l'ordre ne soit soumis à la queue d'exécution, assurant la conformité réglementaire.
* **Priorité 'CRITICAL'** : L'ordre généré doit porter un tag de priorité maximale, forçant l'**`OrderManager`** à vider la `PriorityQueue` en faveur de cet ordre avant tout traitement de stratégie standard.

---

### 5. Conclusion

Ce module constitue la "ceinture de sécurité" du système. Par son architecture **Context-Driven** et son usage de la **Shared Memory**, il garantit que la sécurité n'est jamais sacrifiée au profit de la vitesse, tout en s'assurant que le processus de surveillance lui-même n'ajoute aucun "jitter" (variation de latence) à la boucle de trading principale.

---

|ID|Fonction/Message|Émetteur|Récepteur|Description|
|:---|:---|:---|:---|:---|
|1|notifyDataReady(MarketStateContext)|EventBus|Risk Monitor|Notification asynchrone déclenchant le cycle de surveillance avec l'index de synchronisation du LHB.|
|2|getCurrentExposure()|Risk Monitor|Portfolio Manager|Appel non-bloquant pour consulter l'état actuel de l'exposition via le PositionExposureStore.|
|3|<< return >> PositionExposureSnapshot|Portfolio Manager|Risk Monitor|Retour de l'objet immuable contenant les positions et agrégats d'exposition.|
|4|getRawBufferSlice()|Risk Monitor|Live Historic Buffer|Extraction des séries temporelles brutes à partir de l'index fourni par le contexte.|
|5|checkRiskViolation()|Risk Monitor|Risk Monitor|Calcul interne (Feature Engineering + Modèle ML) pour détecter un dépassement de seuil.|
|6|createEmergencyOrder(PositionState)|Risk Monitor|Risk Monitor|Génération d'un ordre de liquidation si une violation critique est confirmée.|
|7|logCriticalEvent(OrderEvent)|Risk Monitor|Log Service|Enregistrement synchrone et bloquant de l'incident pour garantir l'auditabilité.|
|8|submitEmergencyOrder(Request, CRITICAL)|Risk Monitor|Order Manager|Transmission de l'ordre d'urgence avec le niveau de priorité maximale.|
|9|enqueue(OrderRequest)|Order Manager|PriorityQueue|Insertion de l'ordre en tête de la file d'attente prioritaire de l'OM.|
|10|Return: EnqueueConfirmed|PriorityQueue|Order Manager|Confirmation technique de la mise en file d'attente sécurisée.|
|11|Return: OrderSubmitted|Order Manager|Risk Monitor|Confirmation finale du traitement de l'ordre au moniteur de risque.|
|ref|(OM-RouteOrderToBroker)|Order Manager|Externe|Fragment de référence pour le routage physique de l'ordre vers le broker.|

---
