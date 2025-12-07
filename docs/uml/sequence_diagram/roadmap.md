## Feuille de Route Détaillée (Roadmap / To-Do List) Mise à Jour

### 1. Diagrammes Transversaux et Processus Critiques (Priorité Absolue)

Ces diagrammes doivent être réalisés en premier, car ils définissent les mécanismes fondamentaux (I/O, sécurité, priorisation) utilisés dans les phases **Pre-Trade**, **In-Trade** et **Post-Trade**.

| Num. | ✅ | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :---: | :---: | :--- | :--- | :--- |
| **01** | [ ] | `01-CORE-Check-Connectivite-Critique.puml` | Modélise la vérification séquentielle de la connexion **DB** et **IBKR**, incluant la logique de **Retry** et la notification d'erreur. | * Décomposition : $\text{System Manager}$ → $\text{Database Connector}$ → $\text{IBKR Gateway}$. * Détail : Ajouter les boucles de **Retry** et la condition d'arrêt ($\text{CRITICAL\_ERROR}$). |
| **02** | [ ] | `02-CORE-Persistance-Atomique-FILL.puml` | Décrit le traitement asynchrone d'une exécution (**Fill**) de bout en bout, de l'$\text{IBKR Gateway}$ à la persistance en base de données. | * Décomposition : $\text{IBKR Gateway}$ → $\text{Event}$ → $\text{Order Manager}$ / $\text{Portfolio Manager}$. * Détail : Mettre en évidence la soumission au $\text{Job Manager}$ ($\text{Pool I/O Real-Time}$) et l'écriture $\text{DIL}$ → $\text{Database}$. |
| **03** | [ ] | `03-CORE-Soumission-Job-Prioritaire.puml` | Illustre la réception d'un ordre (Urgent ou Standard) par l'$\text{Order Manager}$ et l'arbitrage par le $\text{Job Manager}$. | * Décomposition : $\text{Order Manager}$ → $\text{Job Manager}$ → $\text{Thread Manager}$ → $\text{IBKR Gateway}$. * Détail : Utiliser des fragments **alt** pour l'arbitrage Prioritaire / Standard et l'allocation du $\text{Pool I/O Critical}$. |
| **04** | [ ] | `04-CORE-Persistance-Bulk-Snapshot.puml` | Décrit le processus d'ingestion massive des $\text{Snapshots}$ dans le **Pool I/O Bulk** du $\text{DIL}$ pour isoler le $\text{Bulk I/O}$ du $\text{Critical I/O}$. | * Décomposition : $\text{Live Data Hub}$ → $\text{DIL}$ → $\text{Job Manager}$ ($\text{Pool I/O Bulk}$) → $\text{Database}$. |
| **05** | [ ] | **`05-CORE-Gestion-Erreur-KillSwitch.puml`** | **[AJOUT CRITIQUE]** Séquence de réaction à une $\text{CRITICAL\_ERROR}$ (ex: perte IBKR), exécution du **Kill-Switch** et annulation des ordres. | * Décomposition : $\text{LDH}$/$\text{IBKR Gateway}$ émet $\text{CRITICAL\_ERROR}$ → $\text{System Manager}$ → $\text{Order Manager}$ (Annulation massive). * Détail : $\text{OM}$ soumet les annulations au $\text{Job Manager}$ (haute priorité). |

---

### 2. Diagrammes de la Phase Pre-Trade (Bootstrapping)

Cette phase est séquentielle et utilise le diagramme **01** en référence.

| Num. | ✅ | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :---: | :---: | :--- | :--- | :--- |
| **06** | [ ] | `06-PHASE1-Bootstrapping-Global.puml` | Séquence principale du $\text{System Manager}$ : Réveil, vérifications critiques (ref: 01), calcul $\text{MarketDayStatus}$ et $\text{STOP}$ si jour non ouvré. | * Décomposition : Séquence de démarrage (1. $\text{WAKEUP}$, 2. ref: 01, 3. $\text{Status Calculation}$). * Détail : Inclure la vérification $\text{MarketDayStatus}$ avec un fragment **alt** pour la transition $\text{Off-Cycle}$. |
| **07** | [ ] | `07-PHASE1-Initialisation-Session-Parallele.puml` | Modélise l'instanciation des sessions, des managers locaux ($\text{PM}$, $\text{RM}$, $\text{OM}$) et le chargement des données en parallèle. | * Décomposition : $\text{System Manager}$ → $\text{Session Manager}$ → $\text{Boucle d’instanciation PM/RM/OM}$. * Détail : Montrer le lancement **parallèle** des requêtes $\text{DAL}$ pour charger les $\text{Orders}$ et les $\text{RiskLimits}$ (Branche A) et la $\text{Gateway}$ (Branche B). |

---

### 3. Diagrammes de la Phase In-Trade (Temps Réel)

Cette phase est principalement asynchrone et repose sur l'événement $\text{MINUTE\_TICK}$ et le flux continu de $\text{Tick Data}$.

| Num. | ✅ | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :---: | :---: | :--- | :--- | :--- |
| **08** | [ ] | `08-PHASE2-Flux-Temps-Reel-LDH.puml` | Modélise l'acquisition $\text{Tick Data}$, la **Surveillance Critique** et la distribution parallèle du $\text{Snapshot}$ vers le $\text{Cache}$ ($\text{Fast-Lane}$) et le $\text{Buffer}$ ($\text{Slow-Lane}$). | * Décomposition : $\text{IBKR Gateway}$ → $\text{Live Data Hub}$. * Détail : Inclure la vérification de $\text{Latence Critique}$ et le fork vers le $\text{Cache}$ et la soumission du $\text{Bulk I/O}$ (ref: 04). |
| **09** | [ ] | `09-PHASE2-Surveillance-Urgence-RiskMonitor.puml` | Séquence critique du $\text{Risk Monitor}$ lisant le $\text{Cache}$, déclenchant un **Ordre d’Urgence** et utilisant la soumission prioritaire (ref: 03). | * Décomposition : $\text{Risk Monitor}$ → $\text{Cache}$ → $\text{Order Manager}$. * Détail : Se concentrer sur la haute priorité et l'utilisation de ref: 03. |
| **10** | [ ] | `10-PHASE2-Boucle-Decision-Standard.puml` | Modélise la décision de **Rééquilibrage** du $\text{Portfolio Manager (PM)}$ et la soumission d'$\text{Ordres Standards}$ via l'$\text{Order Manager}$ (ref: 03). | * Décomposition : $\text{Market Clock}$ → $\text{PM}$ → $\text{Order Manager}$. * Détail : Utiliser un fragment **alt** pour la condition $\text{Jour de Rééquilibrage}$ et l'utilisation de ref: 03. |

---

### 4. Diagrammes de la Phase Post-Trade (Clôture Atomique)

Cette phase est séquentielle et critique pour l'intégrité des données. Elle utilise les deux processus de persistance atomique.

| Num. | ✅ | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :---: | :---: | :--- | :--- | :--- |
| **11** | [ ] | `11-PHASE3-Cloture-Audit-Reconciliation.puml` | Modélise la synchronisation du système, la **Réconciliation Finale** par le $\text{PM}$, et le lancement du $\text{Rapport d’Audit Primaire}$. | * Décomposition : $\text{System Manager}$ → $\text{Job Manager}$ (Attente de vidage buffers) → $\text{PM}$ ($\text{Reconciliation}$). * Détail : Insister sur l'attente du vidage des buffers (Verrou/Latch) et l'émission de l'$\text{Alerte Critique}$ en cas d'écart. |
| **12** | [ ] | `12-PHASE3-Preparation-Atomique-Cycle-Suivant.puml` | Modélise la dernière étape : le $\text{Strategy Engine}$ calcule le $\text{Portfolio Target}$, puis la **persistance atomique** du $\text{Target}$ et de la $\text{Configuration}$ ($\text{Pool I/O Post-Trade}$). | * Décomposition : $\text{Strategy Engine}$ → $\text{DIL}$ (Target) / $\text{Session Manager}$ (Config). * Détail : Montrer la double soumission au $\text{Pool I/O Post-Trade}$ et la transition finale $\text{Off-Cycle}$ uniquement après validation des deux écritures. |

---

### 5. Diagramme du Backtest Core (R&D / Processus Indépendant)

Ce diagramme modélise l'environnement de simulation et d'optimisation hors-ligne.

| Num. | ✅ | Nom du Diagramme de Séquence (Filename) | Description | Tâches de Réalisation |
| :---: | :---: | :--- | :--- | :--- |
| **13** | [ ] | **`13-BACKTEST-Optimisation-Pipeline.puml`** | **[AJOUT R&D]** Séquence d'exécution du $\text{Backtest Engine}$ par le $\text{Parametric Optimizer}$ pour évaluer un jeu de paramètres via la $\text{Pipeline Core}$. | * Décomposition : $\text{Parametric Optimizer}$ → $\text{Backtest Engine}$ → **Boucle** de simulation (pas de temps). * Détail : Montrer l'appel de $\text{IBacktestRunner}$ pour chaque jeu de paramètres et l'invocation de la $\text{Pipeline Core}$. |
