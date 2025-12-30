# `DIL-AtomicDBWriteProces` 

<p align="center">
  <img src="../img/DIL-AtomicDBWriteProces.jpg" width="900">
</p>


Ce fragment modélise le processus générique qui garantit la **persistance atomique** des données critiques dans votre système de trading. Son exécution est **synchrone** et se déroule au sein d'un *thread* du Job Manager, garantissant que les données sont intégralement écrites ou annulées.

## Flux de Travail et Garantie ACID

1.  **Démarrage Transactionnel :** Le **Data Integrity Layer (DIL)** initie la transaction avec la **Database** (`START TRANSACTION`).
2.  **Mise à Jour :** Le DIL envoie toutes les commandes de mise à jour nécessaires (`executeUpdateCommands`) au moteur de base de données. Ces changements sont tracés en mémoire par la session.
3.  **Arbitrage du Résultat :** Le DIL gère le flux avec une structure **Try/Except** :
    * **Succès :** Le DIL envoie la commande **`COMMIT TRANSACTION`**. Si l'écriture réussit, le DIL logue l'audit de succès.
    * **Échec :** Si une exception est levée (contrainte violée, panne), le DIL envoie la commande **`ROLLBACK TRANSACTION`**. Toutes les modifications faites depuis le démarrage de la transaction sont annulées. Le DIL logue l'erreur critique et alerte le Notification Manager.

## Gestion des Ressources (`closeSession`)

Pour garantir l'efficacité du pool de connexions, l'action de nettoyage de session est vitale :

* L'opération **`closeSession()`** est exécutée **après** le `COMMIT` ou le `ROLLBACK`.
* Cette méthode **relâche la session** et retourne la connexion physique au pool de connexions.
* Ceci est une étape indispensable qui empêche le système d'épuiser son pool de connexions disponibles, assurant ainsi la performance pour les jobs suivants.


| ID | Fonction / Message | Émetteur | Récepteur | Description |
|:---|:---|:---|:---|:---|
| 1 | START TRANSACTION | Data Integrity Layer | Database | Initialise une transaction atomique au niveau du moteur de base de données. |
| 2 | executeUpdateCommands(DataPayload) | Data Integrity Layer | Database | Envoie les instructions SQL de mise à jour (Insert/Update/Delete) basées sur le payload. |
| 3 | [COMMIT TRANSACTION] : commitTransaction() | Data Integrity Layer | Database | Valide et rend permanentes toutes les modifications de la transaction en cours. |
| 4 | ILoggingService.logAudit(Transaction_Success) | Data Integrity Layer | Log Service | Enregistre une trace d'audit confirmant le succès de l'opération de persistance. |
| 5 | [ROLLBACK TRANSACTION] : rollbackTransaction() | Data Integrity Layer | Database | Annule toutes les modifications effectuées depuis le START TRANSACTION en cas d'erreur. |
| 6 | ILoggingService.logCriticalError(TransactionFailed) | Data Integrity Layer | Log Service | Enregistre les détails de l'échec pour diagnostic technique immédiat. |
| 7 | INotificationService.sendCriticalAlert(CRITICAL_DB_FAILURE) | Data Integrity Layer | Notification Manager | Déclenche une alerte prioritaire (Email/SMS/Slack) suite à l'échec de l'écriture. |
| 8 | closeSession() | Data Integrity Layer | Database | Ferme la session et libère la connexion physique vers le pool de connexions (indispensable). |

---

### Ports et Interfaces

**PersistencePort**
* **Implémenté par** : `Data Integrity Layer (DIL)` / `AtomicDBWriteProcess`
* **Injecté dans / Utilisé par** : `Portfolio Manager`, `Order Manager`, `Job Manager`
* **Responsabilité opérationnelle** : Orchestration de la persistance atomique (Start, Commit, Rollback) des données critiques.
* **Règles d’accès ou d’usage** : Accès direct au DIL strictement interdit. L'exécution doit garantir l'isolation totale des objets métier et s'effectuer sur le pool de threads `CRITICAL`.

**ITransactionalDatabase** (Interface d'Infrastructure créée)
* **Implémenté par** : `Database Service`
* **Injecté dans / Utilisé par** : `Data Integrity Layer (DIL)`
* **Responsabilité opérationnelle** : Exécution physique des commandes SQL (`executeUpdateCommands`) et gestion de l'état transactionnel au niveau du moteur DB.
* **Règles d’accès ou d’usage** : Usage exclusif par le DIL. Toute session doit impérativement être libérée via `closeSession()` en fin de cycle (succès ou échec) pour éviter l'épuisement du pool de connexions.

**ILogger**
* **Implémenté par** : `Logger Global` / `Log Service`
* **Injecté dans / Utilisé par** : Tous les managers, `Data Integrity Layer (DIL)`
* **Responsabilité opérationnelle** : Journalisation des traces d'audit (`logAudit`) en cas de succès et des erreurs techniques (`logCriticalError`) en cas d'échec de transaction.
* **Règles d’accès ou d’usage** : Pour cette séquence, les appels doivent être synchrones afin de garantir la présence de la trace avant la clôture de la session ou la propagation de l'erreur.

**INotificationService**
* **Implémenté par** : `AlertingService` / `Notification Manager`
* **Injecté dans / Utilisé par** : `Monitor`, `SystemManager`, `Data Integrity Layer (DIL)`
* **Responsabilité opérationnelle** : Diffusion immédiate d'alertes critiques (`sendCriticalAlert`) vers les canaux externes en cas de rupture d'intégrité de la base de données.
* **Règles d’accès ou d’usage** : Doit être implémenté de manière **non-bloquante** (Asynchrone) pour ne pas retarder l'appel vital à `closeSession()` dans le thread du DIL. Usage strictement limité aux sévérités `CRITICAL` ou `FATAL`.


**IJobSubmissionPort**
* **Implémenté par** : `Job Manager`
* **Injecté dans / Utilisé par** : `Data Ingestion Layer (DIL)`, `Order Manager`
* **Responsabilité opérationnelle** : Point d'entrée pour l'exécution de la séquence `AtomicDBWrite` en tant que tâche asynchrone découplée du flux producteur.
* **Règles d’accès ou d’usage** : Doit impérativement assigner le job au pool de threads `CRITICAL` pour garantir la priorité d'exécution et le respect des contraintes de latence du système de trading.

