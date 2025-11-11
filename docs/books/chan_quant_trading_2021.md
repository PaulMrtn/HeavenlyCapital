# Quantitative Trading: How to Build Your Own Algorithmic Trading Business

**Auteur :** Ernest P. Chan  

**Année :** 2021  

## Note
- Metalabeling en finance : un model de ML qui predit la qualite de l oupout du modele master (cf. Marcos Lopez Prado)
  https://en.wikipedia.org/wiki/Meta-Labeling

- Capital disponible influence l’usage du levier : un compte plus petit limite la capacité à emprunter pour amplifier les positions sans prendre de risque excessif.
  
- Capital disponible influence le delta hedging : avec moins de capital, il devient difficile de couvrir efficacement les expositions sur le marché et les devises (FX), ce qui augmente le risque.

- Data Feeder : NASDAQ API (https://data.nasdaq.com/databases/SEP) et Algoseek (https://www.algoseek.com/data-drive.html), les sources sans survivorship bias.

- Intégrer le ratio d’information dans les métriques en définissant un benchmark adapté, contrairement au ratio de Sharpe qui suppose une stratégie currency neutral et utilise le taux sans risque comme référence

- La stratégie doit rester positive selon les échelles de temps, avec un Sharpe ≥ 1 annuel, ≥ 2 mensuel et ≥ 3 journalier. il n'est pas necssaire de soustraire le taux sans risque, sauf si financement par emprunt.
  
- Intégration des métriques de **drawdown** et de **watermark** pour suivre les pertes maximales et le capital de référence le plus élevé.

- Le **CAGR** (taux de croissance annuel composé) mesure la **croissance moyenne annuelle** d’un capital sur une période donnée, en tenant compte de la **capitalisation des rendements**.


- Does the strategy lose steam in recent years compared to its earlier years?

- Sur les données OHLCV, les valeurs High et Low sont peu fiables car fortement influencées par le bruit du marché, les anomalies de cotation et les mouvements ponctuels à faible volume.

- Seules les données des dix dernières années sont réellement pertinentes pour la construction de modèles prédictifs.


## Liens et références
- [Lien vers le livre](https://mega.nz/file/WPABhCDa#Ynh7CnAPXfUaa9VtpckLmiAjzp_GNb7fCtssEw4FIdk)
