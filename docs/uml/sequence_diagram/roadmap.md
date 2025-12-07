##  Feuille de Route Détaillée (Roadmap / To-Do List)

### 1. Diagrammes Transversaux et Processus Critiques

Ces diagrammes doivent être réalisés en premier, car ils sont utilisés dans les phases $\text{Pre-Trade}$, $\text{In-Trade}$ et $\text{Post-Trade}$.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| $\blacksquare$ | **01-CORE-Check-Connectivité-Critique.puml** | Modélise la vérification séquentielle de la connexion DB et IBKR, incluant la logique de `Retry` et la notification d'erreur. | * **Décomposition :** $\text{System Manager} \rightarrow \text{Database Connector} \rightarrow \text{IBKR Gateway}$. * **Détail :** Ajouter les boucles de `Retry` et la condition d'arrêt (`CRITICAL_ERROR`). |
| $\blacksquare$ | **02-CORE-Persistance-Atomique-FILL.puml** | Décrit le traitement asynchrone d'une exécution de bout en bout, de l'$\text{IBKR Gateway}$ à la persistance en base de données. | * **Décomposition :** $\text{IBKR Gateway} \rightarrow \text{Event} \rightarrow \text{Order Manager} / \text{Portfolio Manager}$. * **Détail :** Mettre en évidence la soumission au $\text{Job Manager}$ (Pool I/O Real-Time) et l'écriture $\text{DIL} \rightarrow \text{Database}$. |
| $\blacksquare$ | **03-CORE-Soumission-Job-Prioritaire.puml** | Illustre la réception d'un ordre (`Urgent` ou `Standard`) par l'$\text{Order Manager}$ et l'arbitrage par le $\text{Job Manager}$. | * **Décomposition :** $\text{Order Manager} \rightarrow \text{Job Manager} \rightarrow \text{Thread Manager} \rightarrow \text{IBKR Gateway}$. * **Détail :** Utiliser des fragments `alt` pour l'arbitrage Prioritaire / Standard et l'allocation du $\text{Pool I/O Critical}$. |
| $\blacksquare$ | **04-CORE-Persistance-Bulk-Snapshot.puml** | Décrit le processus d'ingestion massive des $\text{Snapshots}$ dans le $\text{Pool I/O Bulk}$ du $\text{DIL}$ pour isoler le $\text{Bulk I/O}$ du $\text{Critical I/O}$. | * **Décomposition :** $\text{Live Data Hub} \rightarrow \text{DIL} \rightarrow \text{Job Manager}$ (Pool I/O Bulk) $\rightarrow \text{Database}$. |

***

### 2. Diagrammes de la Phase Pre-Trade (Bootstrapping)

Cette phase est séquentielle et utilise le diagramme 01 en référence.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| $\blacksquare$ | **05-PHASE1-Bootstrapping-Global.puml** | Séquence principale du $\text{System Manager}$ : Réveil, vérifications critiques (`ref: 01`), calcul $\text{MarketDayStatus}$ et $\text{STOP}$ si jour non ouvré. | * **Décomposition :** Séquence de démarrage (1. $\text{WAKEUP}$, 2. `ref: 01`, 3. $\text{Status Calculation}$). * **Détail :** Inclure la vérification $\text{MarketDayStatus}$ avec un fragment `alt` pour la transition $\text{Off-Cycle}$. |
| $\blacksquare$ | **06-PHASE1-Initialisation-Session-Parallele.puml** | Modélise l'instanciation des sessions, des managers locaux ($\text{PM}$, $\text{RM}$, $\text{OM}$) et le chargement des données en parallèle. | * **Décomposition :** $\text{System Manager} \rightarrow \text{Session Manager} \rightarrow \text{Boucle d'instanciation PM/RM/OM}$. * **Détail :** Montrer le lancement parallèle des requêtes $\text{DAL}$ pour charger les $\text{Orders}$ et les $\text{RiskLimits}$ (Branche A) et la $\text{Gateway}$ (Branche B). |

***

### 3. Diagrammes de la Phase In-Trade (Temps Réel)

Cette phase est principalement asynchrone et repose sur l'événement `MINUTE_TICK` et le flux continu de $\text{Tick Data}$.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| $\blacksquare$ | **07-PHASE2-Flux-Temps-Reel-LDH.puml** | Modélise l'acquisition $\text{Tick Data}$, la $\text{Surveillance Critique}$ et la distribution parallèle du $\text{Snapshot}$ vers le $\text{Cache}$ (Fast-Lane) et le $\text{Buffer}$ (Slow-Lane). | * **Décomposition :** $\text{IBKR Gateway} \rightarrow \text{Live Data Hub}$. * **Détail :** Inclure la vérification de $\text{Latence Critique}$ et le `fork` vers le $\text{Cache}$ et la soumission du $\text{Bulk I/O}$ (`ref: 04`). |
| $\blacksquare$ | **08-PHASE2-Surveillance-Urgence-RiskMonitor.puml** | Séquence critique du $\text{Risk Monitor}$ lisant le $\text{Cache}$, déclenchant un $\text{Ordre d'Urgence}$ et utilisant la soumission prioritaire (`ref: 03`). | * **Décomposition :** $\text{Risk Monitor} \rightarrow \text{Cache} \rightarrow \text{Order Manager}$. * **Détail :** Se concentrer sur la haute priorité et l'utilisation de `ref: 03`. |
| $\blacksquare$ | **09-PHASE2-Boucle-Decision-Standard.puml** | Modélise la décision de $\text{Rééquilibrage}$ du $\text{Portfolio Manager}$ (PM) et la soumission d'$\text{Ordres Standards}$ via l'$\text{Order Manager}$ (`ref: 03`). | * **Décomposition :** $\text{Market Clock} \rightarrow \text{PM} \rightarrow \text{Order Manager}$. * **Détail :** Utiliser un fragment `alt` pour la condition `Jour de Rééquilibrage` et l'utilisation de `ref: 03`. |

***

### 4. Diagrammes de la Phase Post-Trade (Clôture Atomique)

Cette phase est séquentielle et critique pour l'intégrité des données. Elle utilise les deux processus de persistance atomique.

| Num. | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :--- | :--- | :--- | :--- |
| $\blacksquare$ | **10-PHASE3-Cloture-Audit-Reconciliation.puml** | Modélise la synchronisation du système, la $\text{Réconciliation Finale}$ par le $\text{PM}$, et le lancement du $\text{Rapport d'Audit Primaire}$. | * **Décomposition :** $\text{System Manager} \rightarrow \text{Job Manager}$ (Attente de vidage buffers) $\rightarrow \text{PM}$ ($\text{Reconciliation}$). * **Détail :** Insister sur l'attente du vidage des buffers (Verrou/Latch) et l'émission de l'$\text{Alerte Critique}$ en cas d'écart. |
| $\blacksquare$ | **11-PHASE3-Preparation-Atomique-Cycle-Suivant.puml** | Modélise la dernière étape : le $\text{Strategy Engine}$ calcule le $\text{Portfolio Target}$, puis la persistance atomique du $\text{Target}$ et de la $\text{Configuration}$ (Pool I/O Post-Trade). | * **Décomposition :** $\text{Strategy Engine} \rightarrow \text{DIL}$ (Target) / $\text{Session Manager}$ (Config). * **Détail :** Montrer la double soumission au $\text{Pool I/O Post-Trade}$ et la transition finale $\text{Off-Cycle}$ uniquement après validation des deux écritures. |

---
