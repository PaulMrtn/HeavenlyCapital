## Diagramme d'Activité : Phase III - Post-Trade

<p align="center">
  <img src="img/DA_03_TradingSystem_PostTrade.svg" width="900">
</p>

Cette phase est dédiée à la **clôture sécurisée** du cycle de trading, à l'audit complet des transactions, à la persistance des données massives de marché et à la **préparation atomique** du plan d'action pour le cycle suivant. Elle est caractérisée par une forte orchestration asynchrone pour gérer les dépendances I/O.

---

### 7. Clôture des Opérations et Séquence d'Audit

La phase Post-Trade est déclenchée lorsque le **System Manager** reçoit le signal de fermeture du marché du **Market Clock**.

#### 7.1 Réconciliation Finale et Intégrité

Le **Portfolio Manager (PM)** exécute immédiatement la **Réconciliation Finale** en comparant l'état final du portefeuille (positions, cash) avec les données du courtier via l'IBKR Gateway, garantissant ainsi l'intégrité financière.

Si un **Écart est Détecté** lors de cette vérification :
Le **PM** émet une **Alerte Critique et Journalise l'Incident** (soumettant un `EventLog` de type `CRITICAL_ERROR/DATA_INTEGRITY_CHECK` au Log Service et une alerte immédiate au Monitoring Module).
Le PM finalise la tâche en enregistrant l'événement **`DATA_INTEGRITY_CHECK`** en base de données, un signal d'audit critique.

Une fois la Réconciliation Complétée (avec ou sans écart), cette étape sert de **point de synchronisation** (A5) pour lancer toutes les tâches de fin de journée.

---

### 8. Persistance Orchestrée et Démarrage des Dépendances I/O

À partir du point de synchronisation (A5), trois tâches asynchrones sont lancées pour la persistance et la préparation du cycle, mais leur exécution est strictement ordonnée en raison des dépendances de données.

#### 8.1 Persistance des Données de Marché (Bulk I/O)

La persistance des données de marché est la plus lente et la plus lourde. Le **Live Data Hub (LDH) / DIL** soumet l'ordre de **FLUSH du Buffer de Ticks/Snapshots** accumulés durant la journée. Cette tâche est orientée vers l'efficience des ressources :
1.  Le **Thread Manager** alloue la tâche au **Pool I/O Bulk** (faible priorité).
2.  Le **Job Manager** ordonnance la Tâche de Persistance (A7).

La complétion de cette tâche (A7) est critique car elle est le préalable à l'audit financier.

#### 8.2 Rapport et Audit Dépendant (Pool I/O Audit)

La **Soumission de la Tâche de Rapport** (PnL, métriques agrégées) est lancée, mais son exécution est bloquée par un **Nœud de Jonction (J2)**.

Le **Job Manager** utilise le **Nœud de Jonction (J2)** pour garantir que le lancement de la tâche de reporting n'a lieu qu'après avoir reçu la **Notification de Complétion de la Persistance Bulk (A7)**. Ceci assure que les données brutes sont disponibles pour l'agrégation. Une fois débloqué, le **Thread Manager** alloue la tâche au **Pool I/O Audit** et le **Job Manager** l'ordonnance (A9).

La complétion du Reporting (A9) devient à son tour le préalable au calcul de la stratégie.

---

### 9. Préparation du Cycle Suivant

Le **System Manager** vérifie le calendrier (A10) pour déterminer le type de la prochaine journée.

#### 9.1 Calcul de la Stratégie Dépendant (I/O Critical)

Si le jour suivant est marqué comme un **Jour de Rebalancement** (Condition C2), le calcul de la stratégie est nécessaire, mais il doit intégrer les résultats de l'audit et du reporting.

1.  Le **Job Manager** utilise un **Nœud de Jonction (J3)** pour bloquer le lancement de l'**Exécution du Strategy Engine (A11)** jusqu'à ce que :
    * Le Reporting/Audit (A9) soit complété.
    * La Condition C2 soit vraie (Jour de Rebalancement).
2.  Une fois le calcul du **Portfolio Target** effectué par le **Strategy Engine**, l'objectif (le plan d'ordres) est soumis pour **Persistance Atomique (A12)**.
3.  Le **Thread Manager** alloue cette tâche au **Pool I/O Critical**, et le **Job Manager** l'ordonnance (A13). Cette utilisation du pool critique garantit que le plan du lendemain est sauvegardé immédiatement et de manière sécurisée.

#### 9.2 Persistance de la Configuration (I/O Critical Parallèle)

Parallèlement au flux de dépendance, le **Session Manager** soumet la tâche de **Persistance de l'État Final de la Configuration** de la session (A14). Cette sauvegarde est critique et ne dépend d'aucune donnée d'audit. Elle est immédiatement allouée au **Pool I/O Critical** (A15).

#### 9.3 Transition Finale

Une fois que les deux tâches critiques finales (Persistance du Target A13 et Persistance de la Configuration A15) sont complétées et que le **Job Manager** reçoit les notifications de leur succès, il débloque le **Nœud de Jonction Final (N1)**. Le **System Manager** bascule alors le système en phase **Off-Cycle (Veille)** (A16), marquant la fin du cycle de trading. 
