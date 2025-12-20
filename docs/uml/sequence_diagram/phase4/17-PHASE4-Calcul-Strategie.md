## `17-PHASE4-Calcul-Strategie`

<p align="center">
  <img src="../img/17-PHASE4-Calcul-Strategie.jpg" width="900">
</p>

---

### 1. Objectif

La finalité de ce module est d'orchestrer le calcul et la persistance des portefeuilles cibles. Il filtre les stratégies éligibles au rebalancement et transforme les configurations actives en décisions d'investissement sécurisées en base de données.

---

### 2. Contexte

Ce module est le moteur d'exécution de la **Phase IV**. Il intervient une fois les configurations chargées depuis le **DAL**. Son rôle est de centraliser l'intelligence de planification du cycle en décidant, pour chaque session, si le déclenchement du moteur de calcul est requis pour la journée en cours.

---

### 3. Logique Générale

Le **System Manager (SM)** pilote une boucle itérative structurée comme suit :

* **Auto-Vérification (SM vers SM) :** Pour chaque configuration, le SM appelle sa propre méthode interne `isRebalanceDay(Config.ID)`. Il analyse les règles temporelles du JSON pour confirmer si la stratégie doit agir ce jour.
* **Exécution Déléguée :** Si le test interne est positif, le SM sollicite le **Strategy Engine**. Ce dernier devient alors responsable de récupérer ses données via le **DAL** et de produire le `TargetPortfolioDTO`.
* **Persistance Unitaire :** Tout résultat produit est immédiatement envoyé au **Data Ingestion Layer (DIL)** pour une écriture en base de données.
* **Gestion du saut :** Si l'auto-vérification est négative, le SM passe immédiatement à la session suivante sans solliciter les ressources de calcul.

---

### 4. Règles Critiques

* **Centralisation du Calendrier :** Le SM détient la responsabilité du "Go/No-Go" temporel via `isRebalanceDay`, assurant que le **Strategy Engine** n'est activé que pour des opérations productives.
* **Indépendance des Flux :** La persistance est réalisée au fil de l'eau. L'échec d'une écriture ou d'un calcul pour une session spécifique n'entrave pas le traitement des autres stratégies de la boucle.
* **Optimisation des Ressources :** En internalisant la vérification du rebalancement, le SM évite des instanciations inutiles du moteur de calcul et des requêtes de données superflues vers le DAL.
* **Traçabilité des Décisions :** Le système doit loguer explicitement les sessions ignorées (`SESSION_SKIPPED`) afin de distinguer un oubli technique d'une décision volontaire basée sur le calendrier.

---

### 5. Conclusion

Le module **17-PHASE4-Calcul-Strategie** garantit une gestion rigoureuse et autonome des cycles de trading. En combinant l'auto-vérification du calendrier et la délégation du calcul complexe, il assure une production de cibles optimisée, résiliente et directement exploitable par les phases d'exécution.
