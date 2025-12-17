## `15-PHASE3-Arrêt-Sécurisé`

<p align="center">
  <img src="../img/15-PHASE3-Arrêt-Sécurisé.jpg" width="900">
</p>

---

### 1. Objectif

Ce module a pour finalité de réaliser l'**extinction ordonnée** de l'application de trading. Il garantit que toutes les opérations critiques de la Phase III sont terminées, que les connexions externes sont fermées proprement, et que le processus logiciel est arrêté, laissant le système dans l'état sécurisé et auditable **`OFF_CYCLE`**.

---

### 2. Contexte

Ceci est la dernière étape de la **Phase III (Post-Trade)**. Elle s'exécute uniquement après que le **System Manager** a reçu la confirmation que les persistances atomiques du SessionBook (Étape 13) et de la Configuration de Reprise (Étape 14) ont réussi. Le but est de passer de l'état actif de clôture à l'état inactif (éteint) en minimisant les risques de données résiduelles en mémoire ou de connexions réseau actives.

---

### 3. Logique Générale

Le **System Manager (SM)** initie la séquence en ordonnant au **Session Manager** d'attendre la complétion des derniers jobs I/O en cours via le **Job Manager**. Une fois que la couche métier est stable et que tous les threads I/O sont terminés, le SM prend la main pour l'arrêt des ressources globales. Il ordonne au **LiveDataHub (LDH)** de se désabonner des flux de prix (via l'**IBKR Gateway**) puis de couper la connexion physique. Une fois la déconnexion confirmée, le SM enregistre l'état final (`OFF_CYCLE`) dans le **Logger** et procède à l'**Arrêt du Processus** logiciel de l'application.

---

### 4. Règles Critique

s* **Précondition Stricte :** Le processus d'arrêt ne doit pas commencer tant que la complétion des jobs Post-Trade est confirmée, garantissant que les écritures critiques ne sont pas interrompues.
* **Ordre de Déconnexion :** La déconnexion doit être propre et hiérarchique : désabonnement avant coupure de la connexion physique.
* **Timeout Sévère :** Un délai d'attente court et fixe (e.g., 30 secondes) doit être appliqué à l'attente des derniers jobs I/O. Si ce délai est dépassé, l'arrêt doit basculer vers une erreur critique (`alt [Timeout]`) et forcer l'extinction immédiate pour éviter un état indéfini.
* **Auditabilité :** La transition finale vers l'état `OFF_CYCLE` doit être enregistrée de manière asynchrone dans le journal du système (Logger) juste avant l'arrêt physique du processus.

---

### 5. Conclusion

Le module **15-PHASE3-Arrêt-Sécurisé** est le garant de la **propreté de l'extinction**. Il s'assure qu'au moment où l'application est éteinte, toutes les données de reprise nécessaires sont sécurisées et que les ressources externes (flux de marché, connexions API) ont été libérées selon les protocoles établis.
