# 📄 Documentation du Processus : Création de Commandes de Rééquilibrage

## 1. Introduction et Objectif

Ce document décrit le flux de création et de persistance des ordres dans le cadre d'un processus de **Rééquilibrage (`REBALANCE`)**.

L'objectif principal est de s'assurer que chaque requête d'ordre :
1. Est correctement **validée** avant toute action.
2. Est **persistée** de manière transactionnelle.
3. Est traitée de manière atomique : **l'échec d'un seul ordre entraîne la réitération de la fonction pour l'ensemble du lot**.

---

## 2. Participants du Processus (Lifelines)

| Participant | Type | Rôle |
| :--- | :--- | :--- |
| **`StrategyEngine`** | Acteur Externe | Système initiant la demande de création d'ordres par lots. |
| **`Order Manager`** | Contrôleur / Service | Service principal gérant la logique du flux, la validation, la persistance et la gestion des erreurs. |
| **`Order`** | Entité / Objet | Représentation interne d'une commande individuelle (classe de données). |
| **`Data Feeder Interface`** | Couche de Persistance | **Couche de Persistance/Référentiel (`Data Layer Persistence Object`)**. Elle gère l'écriture en base de données des objets `Order`. |
| **`Log Service`** | Service Utilitaire | Service centralisé pour l'enregistrement des événements (erreurs, succès, statuts). |

---

## 3. Flux de Messages Détaillé

Le processus est initié par une requête contenant un lot d'ordres (`batchId`). Le flux interne s'exécute dans une **boucle (`loop`)** pour traiter chaque ordre de la liste.

### A. Initiation et Préparation

| Étape | De | À | Message | Description |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `StrategyEngine` | `Order Manager` | `requestStrategyOrder(REBALANCE, List<OrderRequestDTO>, batchId)` | Démarre la création des ordres pour le lot spécifié. |
| **2** | `Order Manager` | `Order` | `<<create>> new Order(requestData + batchId)` | Crée un nouvel objet `Order`. **Note :** L'initialisation inclut une vérification d'intégrité des données. |

### B. Validation des Données (Fragment `alt`)

Si la validation interne échoue :

| Étape | De | À | Message | Description |
| :---: | :--- | :--- | :--- | :--- |
| **3** | `Order Manager` | `Log Service` | `LogEvent(ORDER_INVALID)` | Enregistre l'échec de validation. |
| **4** | `Order Manager` | `StrategyEngine` | `BatchQueueResult(STATUS: VALIDATION_ERROR, batchId, orderCount)` | **Rapport d'Erreur :** Notifie l'échec. **La fonction est ensuite réitérée** (mécanisme de *retry*). |

Si la validation **réussit** :

| Étape | De | À | Message | Description |
| :---: | :--- | :--- | :--- | :--- |
| **5** | `Order Manager` | `Order` | `updateStatus(INITIALIZED)` | Met à jour le statut de l'objet `Order`. |
| **6** | `Order Manager` | `Data Feeder Interface` | `persist Order(Order.data)` | Tente de persister l'objet en base de données via la couche de persistance. |

### C. Persistance et Transaction (Fragment `alt`)

Si la persistance échoue (`ERR_DB_PERSISTENCE`) :

| Étape | De | À | Message | Description |
| :---: | :--- | :--- | :--- | :--- |
| **7** | `Order Manager` | `Log Service` | `LogEvent(ORDER_DB_PERSISTENCE)` | Enregistre l'erreur de persistance. |
| **8** | `Order Manager` | `Order Manager` (Implicite) | `RollbackTransaction(batchId)` | Déclenche l'annulation de la transaction pour le lot. |
| **9** | `Order Manager` | `StrategyEngine` | `BatchQueueResult(STATUS: PERSISTENCE_ERROR, batchId, orderCount)` | **Rapport d'Erreur :** Notifie l'échec. **La fonction est ensuite réitérée**. |

Si la persistance **réussit** :

| Étape | De | À | Message | Description |
| :---: | :--- | :--- | :--- | :--- |
| **10** | `Order Manager` | `Log Service` | `LogEvent(ORDER_CREATED_&_QUEUED)` | Enregistre le succès de la création et de la mise en file d'attente. |
| **11** | `Order Manager` | `Order Manager` (Implicite) | `addToQueue(Order.id)` | Ajoute l'identifiant de la commande à une file d'attente interne (système *Execution Queue*). |

### D. Résultat Final

| Étape | De | À | Message | Description |
| :---: | :--- | :--- | :--- | :--- |
| **12** | `Order Manager` | `StrategyEngine` | `BatchQueueResult(STATUS: QUEUED_SUCCESS, batchId, orderCount)` | **Rapport de Succès :** Envoyé après que tous les ordres du lot aient été traités avec succès. |

---

## 4. Améliorations et Notes Futures

### A. Attribut de Priorité (Planifié)
* Il est prévu d'ajouter un attribut de **`priority`** à la classe de données **`Order`** pour une meilleure gestion de l'exécution en file d'attente.

### B. Gestion de la File d'Attente (À Retirer)
* L'étape **11** (`addToQueue`) et la référence `_QUEUED` dans le log **10** sont destinées à être **retirées**.
* Le système futur lira les ordres pour exécution **directement depuis la base de données** après la persistance (Étape 6).

### C. Clarification Nominale de la Persistance (Recommandation)
* Bien que `Data Feeder Interface` agisse comme une couche de persistance, son renommage en **`OrderRepository`** ou **`PersistenceService`** est suggéré pour mieux s'aligner sur les conventions d'architecture logicielles et améliorer la clarté.
