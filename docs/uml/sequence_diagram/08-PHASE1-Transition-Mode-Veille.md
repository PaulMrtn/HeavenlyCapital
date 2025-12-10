## `08-PHASE2-Transition-Mode-Veille`

<p align="center">
  <img src="img/08-PHASE2-Transition-Mode-Veille.jpg" width="900">
</p>

--- 

### 1. Objectif

La finalité de ce module est de faire passer le système de l'état d'initialisation réussie à l'état de **veille sécurisée et active** (`WAITING`), et d'attendre l'événement temporel déclencheur de l'ouverture du marché.

---

### 2. Contexte

Cette séquence marque la fin de la **Phase 1 (Bootstrapping)** et le début de la **Phase 2 (Veille)**. Elle est déclenchée après la validation finale (Étape 07) qui a confirmé la cohérence opérationnelle et l'intégrité de l'infrastructure. Son rôle est de maintenir la disponibilité opérationnelle du système sans exécuter de stratégie de trading.

---

### 3. Logique Générale

Le **`System Manager (SM)`** commence par mettre à jour l'état global du système à **`READY_FOR_TRADING`**. Le système entre ensuite dans un mode **d'attente asynchrone** (`Wait for MarketOpenEvent()`). Pendant cette attente passive, une boucle de surveillance est lancée en arrière-plan. Cette boucle exécute un **Heartbeat** périodique, où l'`Order Manager (OM)` vérifie activement la stabilité de la connexion avec l'`IBKR Gateway`. Le mode veille se termine uniquement lorsque le **`Market Clock`** envoie le signal **`MarketOpenEvent()`**, ce qui déclenche la transition immédiate vers la Phase 3 (Trading Actif).

---

### 4. Règles Critiques

* **Point de Non-Retour :** La mise à jour du statut vers **`READY_FOR_TRADING`** confirme que tous les contrôles de sécurité (LIVE vs PAPER) ont été passés avec succès.
* **Surveillance Obligatoire :** La boucle de **Heartbeat** doit être maintenue. Si la vérification périodique de la connexion externe par l'`OM` échoue durant cette phase, le `SM` doit déclencher un **arrêt d'urgence** (`systemStop(CRITICAL_ERROR)`) car l'exécution serait impossible à l'ouverture.
* **Déclenchement Temporel :** Le seul événement qui met fin à l'attente est le signal asynchrone émis par le **`Market Clock`** à l'heure d'ouverture définie.

---

### 5. Conclusion

Ce module garantit que le système reste **sain et réactif** pendant la période d'attente. Il s'assure que toutes les conditions techniques sont remplies pour un démarrage immédiat et sécurisé, assurant une transition sans accroc de l'état de préparation à l'état d'exécution au moment précis de l'ouverture du marché.
