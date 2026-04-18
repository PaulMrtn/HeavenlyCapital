# Résumé Technique : Modèle de Décision Séquentielle sur Prix Intraday

---

## 1. Objectif

Créer un **modèle prédictif séquentiel** capable de déterminer en temps réel **la zone optimale de sortie** dans une séquence de prix intraday normalisés, avec la contrainte qu'une décision doit être prise avant la fin de la séquence.

L'objectif n'est pas d'identifier un instant unique $t^*$, mais de **maximiser la valeur normalisée capturée** au moment de la décision, sachant que cette valeur optimale correspond à une zone temporelle, pas un point.

---

## 2. Données

- **Séquence** : $X = (x_1, x_2, \ldots, x_T)$, avec $T = 390$ étapes (1 minute chacune, soit 6h30).
- **Observation à chaque étape** : vecteur de caractéristiques $x_t \in \mathbb{R}^d$.
- **Normalisation** : chaque séquence est normalisée à 0 en $t = 0$. La valeur $v(t)$ à l'étape $t$ représente le rendement cumulé depuis l'ouverture.
- **Hétérogénéité** : les séquences appartiennent à des **régimes de marché distincts** qui impliquent des comportements d'arrêt fondamentalement différents.

> ⚠️ Il n'y a pas de label $t^*$ unique annoté. La target est construite algorithmiquement à partir des valeurs normalisées observées en rétrospectif.

---

## 3. Classification préalable des régimes

### Pourquoi classifier

Un modèle de scoring global entraîné sur tous les régimes apprend une moyenne incohérente. La stratégie optimale d'arrêt est radicalement différente selon le type de série :

| Régime | Comportement du prix | Logique d'arrêt |
|---|---|---|
| **Range / oscillant** | Fluctuations sans direction nette | Plusieurs zones de sortie quasi-équivalentes ; attendre après un pic local = perte |
| **Trend directionnel** | Mouvement soutenu dans une direction | Attendre est presque toujours optimal ; la zone optimale est en fin de séquence |
| **Autres** | Spike, retournement, bruit pur... | À déterminer empiriquement |

### Architecture du classifieur

- **Entrée** : les $N$ premières étapes de la séquence (valeur de $N$ à déterminer empiriquement).
- **Sortie** : label de régime $c \in \{1, \ldots, K\}$.
- **Contraintes** :
  - Robustesse au bruit (features agrégées : volatilité réalisée, pente de régression linéaire, amplitude normalisée, autocorrélation...).
  - Convergence rapide : le régime doit être stable avant que le scorer ait besoin de l'information.

> ⚠️ Le nombre de classes $K$ et leurs frontières sont à déterminer par analyse empirique.

---

## 4. Target : le score de qualité $q(t)$

### Définition

La target n'est pas un label binaire mais un **score continu** :

$$q(t) \in [0, 1]$$

qui mesure la qualité de la décision de sortir à l'étape $t$. Ce score atteint son maximum dans la zone optimale et décroît autour sans frontière nette.

### Construction

$$q(t) = g\bigl(v(t),\ c\bigr)$$

où $v(t)$ est la valeur normalisée observée à $t$ (calculable en rétrospectif) et $c$ le régime de la séquence.

La fonction $g$ est une transformation de $v(t)$ : lissage, normalisation par séquence (max $= 1$), potentiellement pondérée par la position temporelle.

### Forme selon le régime

**Régime range** — $q(t)$ multi-modale :

$$q(t) \propto \tilde{v}(t) \quad \text{avec } \tilde{v} = \text{prix lissé (ex : moyenne mobile)}$$

Plusieurs pics locaux ont un $q(t)$ élevé, reflétant les multiples zones de sortie acceptables.

**Régime trend** — $q(t)$ monotone croissante :

$$q(t) \propto v(t) \quad \text{avec normalisation par } \max_t v(t)$$

Attendre rapporte en moyenne davantage ; $q(t)$ reflète le rendement cumulé.

> ⚠️ Questions ouvertes : niveau de lissage optimal, normalisation par séquence ou globale, traitement du bruit sur $v(t)$. À valider empiriquement.

---

## 5. Modèle de scoring

### Un scorer par régime

Pour chaque régime $c$, un modèle indépendant :

$$p_t^{(c)} = f^{(c)}(x_t) \in [0, 1]$$

entraîné uniquement sur les séquences du régime $c$, avec pour target $q(t)$ construit selon ce régime.

### Règle de décision

$$y_t = \begin{cases} \text{True} & \text{si } p_t \cdot \text{penalty}(t) \geq \theta \\ \text{False} & \text{sinon} \end{cases}$$

- $\theta$ : seuil ajustable, calibré sur données de validation.
- $\text{penalty}(t)$ : fonction croissante en $t$, qui compense la contrainte de décision forcée et pousse à décider si le score est suffisant. Forme à déterminer (linéaire, sigmoïde, exponentielle...).

### Contrainte de décision obligatoire

$$y_T = \text{True} \quad \text{(forcé si aucune décision avant } T\text{)}$$

Cette contrainte remplit deux rôles :
1. **Production** : garantit qu'une décision est toujours émise.
2. **Entraînement** : couplée à la pénalité, elle pousse le modèle à anticiper la zone optimale.

---

## 6. Fonction de perte

$$\mathcal{L} = \sum_{t=1}^{T-1} \ell\bigl(p_t,\ q(t)\bigr) \cdot \text{penalty}(t) \;+\; \ell(p_T,\ 1)$$

- $\ell$ : perte entre le score prédit et la target continue. Selon la formulation choisie : MSE si $q(t)$ reste continu, cross-entropy si $q(t)$ est binarisé (seuil à définir).
- Le terme $\ell(p_T, 1)$ encode directement la contrainte de décision forcée.
- La pénalité $\text{penalty}(t)$ pondère chaque étape pour décourager les décisions tardives.

---

## 7. Pipeline de production

1. Les $N$ premières étapes arrivent → **le classifieur détermine le régime** $c$.
2. À chaque étape $t > N$ : le scorer $f^{(c)}$ calcule $p_t$, applique la pénalité, compare au seuil $\theta$.
3. Si $y_t = \text{True}$ → décision prise, séquence terminée.
4. Si $t = T$ et aucune décision → $y_T = \text{True}$ forcé.
5. **Performance** : distribution de $v(\hat{t}) / \max_t v(t)$ — rendement capturé vs maximum théorique, par régime.

---

## 8. Roadmap empirique

| Priorité | Tâche | Débloque |
|---|---|---|
| 1 | Analyser visuellement un échantillon de séquences ; calculer des features descriptives | Nombre de régimes $K$, features discriminantes |
| 2 | Construire $q(t)$ pour chaque régime identifié ; valider la stabilité inter-séquences | Target d'entraînement cohérente |
| 3 | Entraîner et évaluer le classifieur de régime ; tester différentes valeurs de $N$ | Routing fiable en début de séquence |
| 4 | Entraîner un scorer par régime ; baseline logistique puis XGBoost / réseau | Score $p_t$ prédictif |
| 5 | Calibrer $\theta$ et $\text{penalty}(t)$ ; backtester sur données test | Règle de décision opérationnelle |

---

## 9. Concepts clés

| Concept | Rôle |
|---|---|
| Optimal Stopping | Cadre théorique : choisir le meilleur moment dans une séquence |
| Score continu $q(t)$ | Target réaliste : zone optimale, pas instant unique |
| Classification de régime | Pré-requis : un scorer par type de série |
| Pénalité temporelle | Incite à décider tôt sans sacrifier la qualité |
| Décision forcée en $T$ | Sécurité production + signal d'entraînement |
| Modèle générique | Adaptable à tout scorer binaire ou continu |