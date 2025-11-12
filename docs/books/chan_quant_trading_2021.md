# Quantitative Trading: How to Build Your Own Algorithmic Trading Business

**Auteur :** Ernest P. Chan  

**Année :** 2021  

**Lien :** [Lien vers le PDF](https://mega.nz/file/WPABhCDa#Ynh7CnAPXfUaa9VtpckLmiAjzp_GNb7fCtssEw4FIdk)

## Note

### Introduction

- Metalabeling en finance : un model de ML qui predit la qualite de l oupout du modele master (cf. Marcos Lopez Prado)
  https://en.wikipedia.org/wiki/Meta-Labeling

- Capital disponible influence l’usage du levier : un compte plus petit limite la capacité à emprunter pour amplifier les positions sans prendre de risque excessif.
  
- Capital disponible influence le delta hedging : avec moins de capital, il devient difficile de couvrir efficacement les expositions sur le marché et les devises (FX), ce qui augmente le risque.

- Data Feeder : NASDAQ API (https://data.nasdaq.com/databases/SEP) et Algoseek (https://www.algoseek.com/data-drive.html), les sources sans survivorship bias.

### Backtesting

- Intégrer le ratio d’information dans les métriques en définissant un benchmark adapté, contrairement au ratio de Sharpe qui suppose une stratégie currency neutral et utilise le taux sans risque comme référence

- La stratégie doit rester positive selon les échelles de temps, avec un Sharpe ≥ 1 annuel, ≥ 2 mensuel et ≥ 3 journalier. il n'est pas necssaire de soustraire le taux sans risque, sauf si financement par emprunt. (tester sa signification statistique et determiner la taille de l'echantillon necessaire qui correspondra a la duree du paper trading (un rolling test ?)
  
- Intégration des métriques de **drawdown** et de **watermark** pour suivre les pertes maximales et le capital de référence le plus élevé.

- Le **CAGR** (taux de croissance annuel composé) mesure la **croissance moyenne annuelle** d’un capital sur une période donnée, en tenant compte de la **capitalisation des rendements**.


- Does the strategy lose steam in recent years compared to its earlier years?

- Sur les données OHLCV, les valeurs High et Low sont peu fiables car fortement influencées par le bruit du marché, les anomalies de cotation et les mouvements ponctuels à faible volume.

- Seules les données des dix dernières années sont réellement pertinentes pour la construction de modèles prédictifs, attention à un changement de régime soudain, qui peut rendre les données historiques obsolètes

- En règle générale, il est recommandé de ne pas utiliser plus de cinq paramètres dans un modèle (toute constante confondu).

- **Parameterless Trading Model (86/256)**  
  - **Parameterless models** : privilégier des modèles sans paramètres ou à faible complexité pour réduire le risque de **overfitting**.  
  - **Conditional Parameter Optimization (CPO)** : utiliser des approches de *machine learning* pour ajuster dynamiquement les paramètres selon les conditions de marché.  
  - **Sensitivity Analysis** : vérifier la **robustesse** du modèle en testant de légères variations de paramètres — ils doivent être peu sensibles au résultat final.  
  - **Model Simplification** : chercher en permanence à **simplifier le modèle** ; évaluer l’impact de la suppression de chaque condition sur la performance globale.  
  - **Capital Allocation across parameter sets** : répartir le capital entre différentes combinaisons de paramètres avec un **poids défini en backtest**, pour diversifier le risque de sur-optimisation.  

- **Strategy Adaptation** : Si la stratégie tend à devenir **moins rentable**, ajuster légèrement certaines **conditions** ou **paramètres**, notamment l’**univers d’investissement**

### Execution Systems

-  Le slippage provient du contrôle de risque du broker, de la latence entre le broker et la bourse, et d’un accès limité à la liquidité (ex. absence de dark pools).

-  IBKR propose d’abord un **compte démo** pour tester la plateforme et l’API avec des prix fictifs, puis un **paper trading** pour simuler le trading sur le marché réel sans risque, avant de passer au **compte réel** pour trader avec son capital.
  
-  Il faut **continuer le paper trading** pour tester des **stratégies alternatives** et identifier celles qui pourraient **remplacer ou améliorer la stratégie utilisée sur le compte réel**.

### Money and Risk Management

- La formule de Kelly permet de déterminer l’allocation optimale du capital et le levier à utiliser afin de trouver le juste équilibre entre gestion du risque et maximisation de la croissance.

- Si la ruine peut survenir avec une probabilité non nulle à un moment donné, la richesse à long terme est nécessairement nulle, tout comme le taux de croissance de la richesse à long terme.

- le risque réduit toujours le taux de croissance à long terme
