
## `0101-CORE-Check-Connectivite-Critique`

<p align="center">
  <img src="img/0101-CORE-Check-Connectivite-Critique.jpg" width="900">
</p>

---

### Objectif
Garantir la disponibilité des services critiques **DB** et **IBKR** avant le *bootstrapping*. Toute défaillance critique entraîne un **arrêt immédiat** du système.

### Principe
L'orchestration est assurée par le **System Manager** via le fragment de référence **`0000-RESILIENT-CHECK-CONNECTION-SVC`**, qui gère la logique de *Retry*, l'alerte (`Notification Manager`) et l'audit (`Log Service`) en cas d'échec.

### Étapes Séquentielles

#### 1. Vérification de la Base de Données (DB)
* **Moniteur Injecté :** **`Database Connector`**.
* **Action :** Le `System Manager` appelle `ref 0000-RESILIENT-CHECK-CONNECTION-SVC`.
* **Succès :** Le `Database Connector` logue le succès (`logInfo(DB_Connection_OK)`) et le processus passe à l'étape 2.
* **Échec Critique :** Le fragment `ref` renvoie l'exception `CRITICAL_FAILURE`, entraînant l'arrêt du `System Manager` (`destroy`).

---

#### 2. Vérification de l'IBKR Gateway
* **Garde :** Exécuté uniquement si la connexion DB est réussie.
* **Moniteur Injecté :** **`IBKR Gateway`**.
* **Action :** Le `System Manager` appelle `ref 0000-RESILIENT-CHECK-CONNECTION-SVC`.
* **Succès :** L'`IBKR Gateway` logue le succès (`logInfo(IBKR_Connection_OK)`). La séquence de vérification critique est terminée.
* **Échec Critique :** Le fragment `ref` renvoie l'exception `CRITICAL_FAILURE`, entraînant l'arrêt du `System Manager` (`destroy`).

---

### Conclusion
Si les deux appels `ref` retournent `Connection_OK`, l'orchestration est réussie et le `System Manager` poursuit les étapes du *bootstrapping*. Tout échec mène à la destruction contrôlée de l'application.
