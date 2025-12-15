## `12-PHASE3-Synchro-AuditInitial`

<p align="center">
  <img src="../img/12-PHASE3-Synchro-AuditInitial.md.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est de garantir l'**intégrité totale et l'atomicité** de l'état du système à la clôture du marché, en synchronisant la fin de toutes les opérations d'exécution pour permettre le démarrage sécurisé de la phase d'audit.

---

### 2. Contexte

Ce module est le **point de transition critique** entre la Phase II (In-Trade) et la Phase III (Post-Trade). Déclenché par le signal de fermeture du marché (`marketCloseEvent`), il existe pour **geler** l'état du système et **vérifier la cohérence** des données financières avant toute analyse ou calcul stratégique. Il est le garant de la fiabilité des audits post-trade.

---

### 3. Logique Générale

Le processus est initié par le `SystemManager` recevant l'événement de fermeture. Il procède en deux étapes principales :

1. **Synchronisation Forcée :** Le `SystemManager` ordonne au `JobManager` de **bloquer** l'exécution jusqu'à ce que tous les I/O critiques en cours (persistance des derniers Fills, vidage des buffers de Snapshots) soient **atomiquement confirmés** par le `DIL`.
2. **Réconciliation :** Le `PortfolioManager` récupère l'état final auprès du courtier (`IBKR Gateway`) et le compare avec l'état interne. Cette comparaison aboutit à deux chemins : soit le statut est **OK** (poursuite vers l'étape 13), soit il y a **échec critique**.

---

### 4. Règles Critiques

* **Atomicité Précédente :** La synchronisation (étape 3) est absolue. L'audit ne peut démarrer que si la validation de persistance du `DIL` est confirmée.
* **Log de Transition :** Le `marketCloseEvent` est journalisé de manière synchrone dès sa réception pour garantir une trace d'audit du moment exact de la fermeture.
* **Tolérance Zéro :** Si la Réconciliation révèle un **écart critique** (`data_discrepancy`), le `PortfolioManager` enregistre l'incident de manière **synchrone** (`logCriticalError`) et alerte immédiatement les opérateurs. Le processus normal (calcul de stratégie, étape 15) est alors **annulé** pour intervention manuelle.
* **État de Poursuite :** Le système ne procède aux étapes Post-Trade suivantes (Persistance des Métriques, Calcul de Stratégie) qu'à la condition stricte que le `SystemManager` ait reçu la confirmation `reconciliationOK()`.

---

### 5. Conclusion

Ce module est essentiel pour l'intégrité financière. Il garantit que le système passe en Phase III sur un **état final, complet et audité**, en isolant les conséquences d'un écart critique par une annulation immédiate du flux de travail stratégique et une alerte à priorité maximale.
