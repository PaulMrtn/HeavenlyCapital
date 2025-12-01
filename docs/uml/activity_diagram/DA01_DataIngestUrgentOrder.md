## Processus : Ingestion de Données et Ordre d'Urgence (DA-01)

Ce processus décrit l'acquisition des données de marché, leur transformation en Snapshots, et la gestion du flux d'exécution d'ordre d'urgence (ex: Stop-Loss), garantissant l'isolation des tâches I/O lentes (persistance) via la gestion des priorités du Thread Manager.

<p align="center">
  <img src="img/DA01_DataIngestUrgentOrder.png" alt="diagramme" />
</p>

---

### 1. Ingestion et Préparation des Données (Flux A/T)

| Étape | Composant | Description |
| :--- | :--- | :--- |
| **A1-A2** | IBKR Gateway → Live Data Hub | Réception du TickData brut et mise à jour immédiate du Cache de Ticks. |
| **A3** | Live Data Hub | **Transformation :** Consolidation des Ticks en objets SnapshotHeader et MarketQuote. |
| **A-FORK** | Live Data Hub | **Division des Flux :** Le Snapshot achevé déclenche un Nœud qui initie deux chemins parallèles (Persistance et Surveillance). |

---

### 2. Persistance Asynchrone (Flux A)

Ce chemin est isolé pour la robustesse et utilise le Pool I/O Basse Priorité.

| Étape | Composant | Description |
| :--- | :--- | :--- |
| **A4** | Live Data Hub | **Buffering :** Le Snapshot est ajouté à la File d'Attente de Persistance (Buffer) gérée par le Hub. |
| **A5** | Live Data Hub → Thread Manager | Le Hub soumet une Tâche de Vidage (Drain Task) au Thread Manager. |
| **A6-A7** | Thread Manager → DIL | Le Thread Manager affecte la tâche au **Pool I/O Basse Priorité**, puis déclenche l'exécution du Drain Task. |
| **A8-A9** | DIL → Database Connector | Le Data Ingestion Layer vide le Buffer et réalise l'écriture atomique en base de données, terminant le flux asynchrone. |

---

### 3. Surveillance et Décision d'Urgence (Flux T/B)

Ce chemin est critique et utilise le Fast-Lane pour les ordres d'exécution.

| Étape | Composant | Description |
| :--- | :--- | :--- |
| **T1-T2** | Live Data Hub → Job Manager → Risk Monitor | **Cadencement :** Le Hub notifie le Job Manager (via IMarketEventPublisher). Le Job Manager exécute la tâche d'évaluation du risque sur le Risk Monitor. |
| **B1** | Risk Monitor | Lecture du Snapshot et exécution de l'algorithme Stop-Loss. |
| **B-DECIDE** | Risk Monitor | **Nœud de Décision :** Évaluation du résultat de B1. |
| **[Else]** | Risk Monitor → Final Node | Si la condition Stop-Loss n'est pas remplie (Aucun Ordre Généré), le flux se termine immédiatement. |
| **[Ordre Généré]** | Risk Monitor → Job Manager | Création de l'ordre d'urgence et soumission au Job Manager. |
| **B3-B4** | Job Manager → Thread Manager | **Fast-Lane :** Le Thread Manager reçoit l'ordre et garantit l'affectation immédiate d'un thread du **Pool I/O Haute Priorité**. |
| **B5-F** | Job Manager → IBKR Gateway | Exécution immédiate de l'ordre sur le Fast-Lane, terminant le processus. |
