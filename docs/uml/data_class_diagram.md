## Diagramme de Classes de Données UML

Ce document fournit la documentation du modèle de données UML (classes, énumérations et relations entre entités) de la station de trading.

### 1. Entités fondamentales de l’architecture de la station de trading

#### 1.1. `TradingSystem` 

TradingSystem représente l’instance centrale du système de trading (singleton), supervisant son état opérationnel, les connexions aux services et la version en cours. 
Il orchestre les sessions de trading et gère les snapshots de données associés.

**Attributs :**

* **`system_id`** (`UUID`, *Primary Key*): Identifiant unique du système (Instance unique : Singleton).
* `status` (`SystemStatus`): État opérationnel du système.
* `db_conn_status` (`boolean`): État actuel de la connexion à la DB. (True : Active)
* `ibkr_conn_status` (`boolean`): État actuel de la connexion à IBKR.
* `version_number` (`string`): Version actuelle du système trading.

**Énumérations :**

* `SystemStatus` : (`ACTIVE`, `STOPED`, `ERROR`)

**Relations entre entités :**

* `TradingSystem` 1 --- 1..* `TradingSession` 
  - Un système de trading peut contenir de multiples sessions.
* `TradingSystem` 1 --- 1 `SnapshotHeader` 
  - Un système de trading contient un gestionnaire de snapshots de données.


#### 1.2. `TradingSession` 

TradingSession modélise une session de trading, définissant le contexte, l’exécution et le suivi d’une stratégie sur un marché donné. 
Elle représente l’unité centrale permettant de gérer et d’orchestrer l’ensemble des activités liées à une session de trading.

**Attributs :**

* **`session_id`** (`UUID`, *Primary Key*): Identifiant unique de la session.
* `calendar_id_ref` (`UUID`, *Secondary Key*): Vers `TradingCalendar.calendar_id`
* `account_id` (`string`): ID du compte de trading réel ou papier (IBKR).
* `strategy_name` (`string`): Nom de la stratégie exécutée.
* `mode` (`ExecutionMode`): Mode d'exécution de la session.
* `status` (`SessionStatus`): L'état actuel de la session.
* `session_config` (`JSON`): Paramètres de calibration et d'exécution de la stratégie.
* `start_timestamp` (`DateTime`): Date et heure de début de la session.
* `end_timestamp` (`DateTime`): Date et heure de fin (NULL si la session est active).

**Énumérations :**

* `ExecutionMode` : (`LIVE`, `PAPER`, `BACKTEST`)
* `SessionStatus` : (`INITIALIZED`, `RUNNING`, `PAUSED`, `STOPPED`, `ERROR`)


**Relations entre entités :**

* `TradingSession` 1 --- 1 `TradingCalendar`
  - Une session doit contenir un calendrier de marché.
* `TradingSession` 1..* --- 1 `TradingSystem`
  - Une ou plusieurs sessions sont liées à un système de trading.
* `TradingSession` 1 --- 0..* `Order`
  - Une session peut contenir plusieurs ordres.
* `TradingSession` 1 --- 0..* `Fill`
  - Une session peut contenir plusieurs exécutions.
* `TradingSession` 1 --- 0..* `AcquisitionLot`
  - Une session peut contenir plusieurs lots d'acquisition.
* `TradingSession` 1 --- 0..* `RealizationLot`
  - Une session peut contenir plusieurs lots de réalisation.
* `TradingSession` 1 --- 0..* `Position`
  - Une session peut contenir plusieurs positions. 
* `TradingSession` 1 --- 0..* `Trade` 
  - Une session peut contenir plusieurs trades.
* `TradingSession` 1 --- 0..* `TickData` 
  - Une session peut contenir plusieurs tick.
* `TradingSession` 1 --- 0..* `EventLog` 
  - Une session peut contenir plusieurs événements.
* `TradingSession` 1 --- 0..* `JobExecution` 
  - Une session peut contenir plusieurs tâches à exécuter.


#### 1.4. `TradingCalendar` 

TradingCalendar représente la configuration temporelle d’une session de trading : horaires du marché, règles de rebalancement et jours spécifiques.
Il est attaché à une seule TradingSession (agrégation), car chaque session peut avoir son propre calendrier.

**Attributs :**

* **`calendar_id`** (`UUID`, *Primary Key*): ID du calendrier de trading.
* `market_timezone` (`string`): Fuseau horaire du marché (ex: 'America/New_York').
* `market_open_time` (`DateTime`): Heure d'ouverture standard du marché (ex: 09:30:00).
* `market_close_time` (`DateTime`): Heure de fermeture standard du marché (ex: 16:00:00).
* `trading_days` (`List<DateTime>`): Liste des dates des jours de marché.
* `rebalance_monthly_rule` (`List<DateTime>`): Dates spécifiques des rebalancements mensuel.
* `rebalance_weekly_rule` (`List<int>`): Dates spécifiques des rebalancements hebdomadaires, Règle : Les jours ouvrés du mois à utiliser (ex: [5, 10, 15, 20]).

**Relations entre entités :**

* `TradingCalendar` 1 --- 1 `TradingSession` (Aggregation)
  - Un calendrier de marché est associé à une session nde trading.


#### 1.5. `ScheduledJob` 

ScheduledJob représente une tâche planifiée dans la station de trading.
Elle est indépendante des sessions, opère principalement au niveau du TradingSystem, et peut être exécutée soit globalement, soit dans le contexte d'une session lorsque cela est pertinent.

**Attributs :**

* **`job_id`** (`UUID`, *Primary Key*): ID du gestionnaire de tâche.
* `trading_system_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSystem.system_id`
* `job_name` (`string`): Nom de la tâche (ex: "Asset Selection", "Data Import").
* `job_code` (`string`): Code unique ou type de la tâche.
* `is_global` (`boolean`): TRUE si la tâche est commune à toutes les sessions (ex: import de données), FALSE si elle est spécifique à une session (ex: sélection d'actifs).
* `job_config` (`JSON`): Configuration de la tâche (paramètres spécifiques)


**Relations entre entités :**
* `ScheduledJob` 1 --- 1 `TradingSystem` 
  - Le gestionnaire de tâche est lié au système de trading.
* `ScheduledJob` 1 --- 0..* `JobExecution`
  - Le gestionnaire de tâches regroupe l’ensemble des tâches à exécuter.


#### 1.6. `JobExecution`

JobExecution représente une instance d’exécution d’une tâche planifiée.
Elle conserve l’historique complet des runs d’un job, qu’il soit global ou attaché à une session.

**Attributs :**
* **`execution_id`** (`UUID`, *Primary Key*): ID de cette instance d'exécution.
* `job_id_ref` (`UUID`, *Secondary Key*): Vers `ScheduledJob.job_id`, l'ID de la tâche.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `start_timestamp` (`DateTime`): Date et heure de début de l'exécution de la tâche.
* `end_timestamp` (`DateTime`): Date et heure de fin de l'exécution de la tâche.
* `status` (`ScheduledJobStatus`): Status de cette exécution.
* `error_message` (`string`): Détails de l'erreur ou du warning si l'exécution n'est pas un succès.

**Énumérations :**
* `ScheduledJobStatus` : (`PENDING`, `RUNNING`, `COMPLETED_SUCCESS`, `COMPLETED_WARNING`, `FAILED`, `CANCELLED`)


**Relations entre entités :**
* `JobExecution` 1 --- 1..* `EventLog` 
  - Une exécution peut générer plusieurs événements.
* `JobExecution` 0..* --- 1 `TradingSession`
  - Chaque exécution appartient à une session.
* `JobExecution` 0..* --- 1 `ScheduledJob`
  - Chaque exécution appartient au gestionnaire de tâche.

---

### 2. Entités de gestion des données


#### 2.1. `TickData`

TickData représente l’état d'un actif à un instant donné sur le marché : quotes bid/ask, dernière transaction, volumes.

**Attributs :**

* **`tick_id`** (`UUID`, *Primary Key*): Identifiant unique du tick.
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `timestamp` (`DateTime`): Timestamp de la mise à jour du tick.
* `bid` (`float`): Prix du meilleur Bid.
* `bid_size` (`float`): Volume disponible au meilleur Bid.
* `ask` (`float`): Prix du meilleur Ask.
* `ask_size` (`float`): Volume disponible au meilleur Ask.
* `volume` (`float`): Volume de la dernière transaction.
* `last_price` (`float`): Le prix de la dernière transaction connue à cet instant.
* `min_tick` (`float`): Mouvement de prix minimum de l'actif


**Relations entre entités :**

* `TickData` 1.* --- 1 `Asset`
  - Un tick est associé à un asset.
  

#### 2.1. `SnapshotHeader`

SnapshotHeader représente un instantané global du marché à un moment donné.
Il regroupe toutes les cotations consolidées (MarketQuote) pour le TradingSystem à une fréquence donnée 

**Attributs :**

* **`snapshot_id`** (`UUID`, *Primary Key*): ID du snapshot
* `trading_system_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSystem.system_id`
* `timestamp` (`DateTime`): Timestamp de la mise à jour du snapshot.
* `interval_type` (`string`): La fréquence de cet instantané (ex: '1m', '5m').

**Relations entre entités :**

* `SnapshotHeader` 1 --- 1 `TradingSystem` 
  - Un snapshot est lié au système de trading.
* `SnapshotHeader` 1 --- 0..* `MarketQuote` 
  - Un snapshot regroupe l’ensemble des cotations de marché pour une date donnée.
  

#### 2.1. `MarketQuote`

MarketQuote représente la cotation consolidée d’un actif au sein d’un snapshot donné.
Contrairement à TickData (granularité tick-par-tick), MarketQuote regroupe les informations résumées sur l’intervalle du snapshot (1m, 5m, etc.).

**Attributs :**

* **`quote_id`** (`UUID`, *Primary Key*): ID de le cotation de marché
* * `snapshot_id_ref` (`UUID`, *Foreign Key*): Vers `SnapshotHeader.snapshot_id`
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `bid` (`float`): Prix du meilleur Bid.
* `bid_size` (`float`): Volume disponible au meilleur Bid.
* `ask` (`float`): Prix du meilleur Ask.
* `ask_size` (`float`): Volume disponible au meilleur Ask.
* `volume` (`float`): Volume cumulé depuis le dernier snapshot.
* `last_price` (`float`): Le prix de la dernière transaction depuis le dernier snapshot.

**Relations entre entités :**

* `MarketQuote` 0..* --- 1 `SnapshotHeader` 
  - Une cotation de marché à un instant donné est contenue dans un snapshot.
* `MarketQuote` 0..* --- 1 `Asset` 
  - Chaque cotation de marché est lié à un actif.

---

### 3. Entités Actif

#### 3.1. `Asset` (Classe de base) 

Asset représente un instrument financier générique et sert de base pour des classes spécialisées comme StockAsset, CurrencyAsset ou OptionAsset. 
Elle définit les caractéristiques essentielles d’un actif et centralise ses relations avec ordres, positions, trades et les données de marché.

**Attributs :**

* **`asset_id`** (`UUID`, *Primary Key*): ID unique de cet actif pour l'ensemble du système.
* `ticker` (`string`): Symbole de l'actif (ex: 'AAPL').
* `asset_name` (`string`): Nom lisible (ex: 'Apple Inc.').
* `security_type` (`AssetType`): Type d'instrument.
* `currency` (`string`): Devise de cotation (ex: 'USD').
* `exchange` (`string`): Place boursière principale (ex: 'NYSE').
* `multiplier` (`float`): Facteur de conversion de valeur.
* `lifecycle_status` (`AssetStatus`): Statut de l'actif (actif ou expiré).

**Énumérations :**

* `AssetType` : (`STOCK`, `FUTURE`, `FOREX`, `OPTION`)
* `AssetStatus` : (`ACTIVE`, `EXPIRED`)

**Relations entre entités :**

* `Asset` 1 --- 0..* `Order`
  - Un actif peut être associé à plusieurs ordres.
* `Asset` 1 --- 0..* `Fill`
  - Un actif peut être associé à plusieurs fills.
* `Asset` 1 --- 0..*  `AcquisitionLot`
  - Un actif peut être associé à plusieurs lots d'acquisition.
* `Asset` 1 --- 0..*  `RealizationLot`
  - Un actif peut être associé à plusieurs lots de réalisation.
* `Asset` 1 --- 0..*  `Position`
  - Un actif peut être associé à plusieurs positions.
* `Asset` 1 --- 0..* `Trade`
  - Un actif peut être impliqué dans plusieurs trades.
* `Asset` 1 --- 0..* `TickData`
  - Un actif peut être impliqué dans plusieurs ticks.
 * `Asset` 1 --- 0..* `MarketQuote`
  - Un actif peut être impliqué dans plusieurs cotations de marché.
 

#### 3.2. `StockAsset` (Hérite de `Asset`)

Représente un actif de type action.

**Attributs :**

* `isin` (`string`): Code ISIN

#### 3.3. `CurrencyAsset` (Hérite de `Asset`)

Représente un actif de type paire de devises (Forex).

**Attributs :**

* `currency_base` (`string`): La devise achetée ou vendue (ex: EUR).
* `currency_quote` (`string`): La devise utilisée pour coter la paire (ex: USD).
* `pip_size` (`float`): Le pas de cotation minimum.

---

### 4. Entités d'ordre et d'exécution

#### 4.1. `Order` 

Order représente une instruction d’achat ou de vente d’un actif, définissant son type, sa quantité, son prix et son statut. 
Elle centralise les relations avec l’actif concerné, les exécutions et les événements associés.

**Attributs :**

* **`order_id`** (`UUID`, *Primary Key*): ID interne unique de l'ordre.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `broker_order_id` (`string`): ID de référence de l'ordre interne à IBKR.
* `side` (`OrderSide`): Sens de l'ordre.
* `order_type` (`OrderType`): Type d'ordre.
* `initial_qty` (`float`): Quantité initialement demandée lors de la soumission de l'ordre.
* `filled_qty` (`float`): Quantité cumulative déjà exécutée.
* `remaining_qty` (`float`): Quantité restante à exécuter (`initial_qty` - `filled_qty`).
* `limit_price` (`float`): Prix spécifié pour les ordres `LIMIT` (ex: NULL si type `MARKET`).
* `tif_code` (`TIFType`): Code TIF spécifiant le type de validité.
* `due_date` (`DateTime`): Date/heure d'expiration spécifique (ex: utilisé si `tif_code` est `GTD`).
* `submission_time` (`DateTime`): Date et heure de soumission.
* `completion_time` (`DateTime`): Date et heure où l'ordre atteint un statut TERMINAL. (NULL si l'ordre est toujours WORKING ou PENDING.)
* `status` (`OrderStatus`): État actuel de l'ordre.

**Énumérations :**

* `OrderSide` : (`BUY`, `SELL`)
* `OrderType` : (`MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`, `TRAILING_STOP`)
* `TIFType` :  (`DAY`, `GTC`, `GTD`, `IOC`, `FOK`, `OPG`)
* `OrderStatus` : (`INITIALIZED`, `API_PENDING`, `WORKING`, `PARTIALLY_FILLED`, `FILLED`, `PENDING_CANCEL`, `CANCELLED`, `REJECTED`, `EXPIRED`) 

**Définitions :**

* `DAY`: Valide jusqu’à la fin de la séance du jour.
* `GTC`: Reste actif jusqu’à exécution ou annulation manuelle.
* `GTD`: Valide jusqu’à la date/heure spécifiée par la `due_date`.
* `IOC`: Exécute immédiatement la partie disponible, le reste est immédiatement annulé.
* `FOK`: L'ordre doit être exécuté immédiatement et en totalité, sinon il est annulé.
* `OPG`: L'exécution est uniquement tentée à l’ouverture du marché.

**Relations entre entités :**

* `Order` 1 --- 0..* `Fill`
  - Un ordre peut générer plusieurs exécutions (fills).
* `Order` 0..* --- 1 `TradingSession` 
  - Chaque ordre appartient à une session.
* `Order` 0..* --- 1 `Asset` 
  - Chaque ordre est lié à un actif.
* `Order` 1 --- 0..* `EventLog` 
  - Un ordre peut générer plusieurs événements.


#### 4.2. `Fill`
Fill représente l’exécution effective d’un ordre, précisant la quantité, le prix et le sens de l’opération. 
Elle relie chaque exécution à son ordre, à la session de trading correspondante et aux événements ou lots de position associés.

**Attributs :**

* **`fill_id`** (`UUID`, *Primary Key*): ID unique de cette exécution.
* `order_id_ref` (`UUID`, *Foreign Key*): Vers `Order` qui a généré cette exécution.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `execution_id_broker` (`string`): ID de référence de l'exécution interne à IBKR.
* `fill_timestamp` (`DateTime`): Date et heure de l'exécution.
* `quantity` (`float`): Quantité réellement exécutée.
* `fill_price` (`float`): Prix réel auquel cette quantité a été exécutée.
* `side` (`OrderSide`): Sens de l'exécution (Doit correspondre à Order.side).
* `fee_amount` (`float`): Montant total des frais et commissions (peut être NULL initialement, mis à jour via un événement asynchrone).

**Relations entre entités :**

* `Fill` 1 --- 1 `AcquisitionLot` 
  - Un fill ouvre un lot d'acquisition.
* `Fill` 1 --- 1..* `RealizationLot` 
  - Un fill ouvre un ou plusieurs lots de realization.
* `Fill` 0..* --- 1 `Order` (Composition)
  - Chaque fill appartient à un ordre.
* `Fill` 0..* --- 1 `TradingSession`
  - Chaque fill appartient à une session.
* `Fill` 1 --- 0..* `EventLog` 
  - Un fill peut générer plusieurs événements.
* `Fill` 0..* --- 1 `Asset` 
  - Chaque Fill est lié à un actif.

---

### 5. Entités liées à l’exécution, aux positions et au calcul du PnL

#### 5.1. `AcquisitionLot` 

AcquisitionLot représente un lot d’entrée dans une position, créé à partir d’une exécution et géré selon la méthode comptable FIFO. 
Il décrit un ensemble de quantités acquises avec leur coût ajusté, et sert de base au suivi des opérations de réalisation associées au sein d’une position.

**Attributs :**

* **`acquisition_lot_id`** (`UUID`, *Primary Key*): ID unique de ce lot d'acquisition.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `open_fill_id_ref` (`UUID`, *Foreign Key*): Vers `Fill`, position d'ouverture (Entrée).
* `entry_timestamp` (`DateTime`): Date et heure d'initialisation.
* `side` (`OrderSide`): Sens de la transaction initiale.
* `adjusted_unit_cost` (`float`): Coût unitaire réel incluant les frais (`fee`). 
* `initial_qty` (`float`): Quantité initiale de ce lot.
* `current_qty` (`float`): Quantité restante dans ce lot (doit être $\ge 0$).
* `status` (`LotStatus`): État actuel du lot.

**Énumérations :**

* `LotStatus` : (`OPEN`, `CLOSED`, `PARTIALLY_CLOSED`, `ARCHIVED`)

**Relations entre entités :**


* `AcquisitionLot` 1 --- 1 `Fill` 
  - Chaque lot d'acquisition provient d'un fill
* `AcquisitionLot` 1 --- 0..* `RealizationLot` 
  - Un lot d’acquisition peut être lié à plusieurs lots de réalisation.
* `AcquisitionLot` 1..* --- 1 `Position`
  - Chaque lot d'acquisition appartient à une position.
* `AcquisitionLot` 0..* --- 1 `TradingSession`
  - Chaque lot d'acquisition appartient à une session.
* `AcquisitionLot` 1 --- 0..* `EventLog` 
  - Un lot d'acquisition peut générer plusieurs événements.
* `AcquisitionLot` 0..* --- 1 `Asset` 
  - Chaque AcquisitionLot est lié à un actif.

  

#### 5.2. `RealizationLot` 

RealizationLot représente la portion d’un lot d’acquisition qui est fermée lors d’une sortie, permettant de calculer le PnL réalisé selon l’exécution correspondante. 
Il relie chaque fermeture à son fill, à l’acquisition d’origine et au trade auquel la réalisation contribue.

**Attributs :**

* **`realization_lot_id`** (`UUID`, *Primary Key*): ID unique du lot de réalisation.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `closing_fill_id_ref` (`UUID`, *Foreign Key*): Vers `Fill`, vers le Fill de fermeture (Sortie).
* `acquisition_lot_id_ref` (`UUID`, *Foreign Key*): Vers `AcquisitionLot.acquisition_lot_id`, position de fermeture d'un lot d'acquisition.
* `trade_id_ref` (`UUID`, *Foreign Key*): Vers `Trade.trade_id`, la consolidation finale du Trade.
* `quantity_closed` (`float`): Quantité du lot d'acquisition fermée par ce lot de realization.
* `realized_pnl` (`float`): PnL réalisé.

**Relations entre entités :**

* `RealizationLot` 1..* --- 1 `Fill` 
  - Un ou plusieurs lots de réalisation proviennent d’un fill
* `RealizationLot` 1..* --- 1 `AcquisitionLot` 
  - Un ou plusieurs lots de réalisation sont liés à un lot d’acquisition.
* `RealizationLot` 1..* --- 1 `Trade` 
  - Un ou plusieurs lots de réalisation sont liés à un trade.
* `RealizationLot` 0..* --- 1 `TradingSession`              
  - Chaque lot de réalisation appartient à une session.
* `RealizationLot` 0..* --- 1 `Asset` 
  - Chaque lot de réalisation est lié à un actif.
* `RealizationLot` 1 --- 0..* `EventLog` 
  - Un lot de réalisation peut générer plusieurs événements.



#### 5.3. `Position` 

Position représente l’état consolidé d’un actif détenu dans un portefeuille, en agrégeant l’ensemble des lots d’acquisition qui la composent. 
Elle fournit une vue synthétique des quantités, des coûts et des résultats réalisés ou latents, tout en assurant le lien entre l’actif, la session et le portefeuille auquel elle appartient. 

**Attributs :**

* **`position_id`** (`UUID`, *Primary Key*): ID unique de de la position
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `portfolio_id_ref` (`UUID`, *Foreign Key*): Vers `Portfolio.portfolio_id`
* `current_qty` (`float`): Quantité totale détenue (Somme des `AcquisitionLot.current_qty` ouverts).
* `average_cost` (`float`): Prix moyen pondéré d'acquisition (Moyenne des `AcquisitionLot.adjusted_unit_cost` ouverts).
* `last_market_price` (`float`): Dernier prix de marché connu (pour valorisation).
* `total_realized_pnl` (`float`): PnL Réalisé total (Somme des PnL réalisés de tous les lots). 
* `unrealized_pnl` (`float`): PnL Latent (Calculé sur la base de current_quantity et average_cost).

**Relations entre entités :**

* `Position` 1 --- 1..* `AcquisitionLot` 
  - Une position provient d'un ou plusieurs lots d'acquisition
* `Position` 0..* --- 1 `Portfolio` 
  - Une ou plusieurs positions sont liées à un portefeuille.
* `Position` 0..* --- 1 `Asset` 
  - Chaque position est lié à un actif.
* `Position` 0..* --- 1 `TradingSession`              
  - Une ou plusieurs positions appartient à une session.


#### 5.4 `Trade` 

Trade représente une transaction complète, depuis l’ouverture d’une position jusqu’à sa clôture.
Il est créé lors de la fermeture d’un lot d’acquisition au travers d’un ou plusieurs lots de réalisation, et fournit une vue consolidée du mouvement : sens du trade, prix d’entrée moyen, prix de sortie, quantité clôturée et résultat réalisé.

**Attributs :**

* **`trade_id`** (`UUID`, *Primary Key*): ID unique de cette transaction complète.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`
* `side` (`TradeSide`): Sens du trade (`Long` ou `Short`).
* `closing_timestamp` (`DateTime`): Date et heure de l'exécution qui a clôturé la position.
* `avg_entry_price` (`float`): Prix d'entrée moyen pour le PnL réalisé. Coût moyen pondéré des lots consommés.
* `exit_price` (`float`): PPrix unique du Fill de clôture.
* `closed_qty_total` (`float`): Quantité totale vendue.
* `realized_pnl_gross` (`float`): PnL brut.
* `total_fees` (`float`): Somme de tous les frais d'entrée et de sortie pour ce Trade.

**Énumérations :**

* `TradeSide` : (`LONG`, `SHORT`)

**Relations entre entités :**

* `Trade` 1 --- 1 `Fill` 
  - Un trade proviennent d’un fill
* `Trade` 1 --- 1..* `RealizationLot` 
  - Un trade est lié à un ou plusieurs lots de réalisation.
* `Trade` 0..* --- 1 `Asset` 
  - Chaque trade est lié à un actif.
* `Trade` 1 --- 0..* `EventLog` 
  - Un trade peut générer plusieurs événements.
* `Trade` 0..* --- 1 `TradingSession`              
  - Une ou plusieurs trades appartient à une session.

#### 5.5. `RiskSnapshot`

`RiskSnapshot` représente l'état des **positions actives** et les **limites de risque individuelles** associées à ces positions, au moment du snapshot. Le **Risk Monitor** utilise cette structure pour évaluer si les cotations du marché en temps réel déclenchent un seuil de risque spécifique (Stop-Loss, etc.) sur chaque position active.

**Attributs :**

* **`snapshot_id`** (`UUID`, *Primary Key*): Identifiant unique de cet instantané de risque.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `timestamp` (`DateTime`): Date et heure de la création/mise à jour du snapshot.
* `position_id_ref` (`UUID`, *Foreign Key*): Vers `Position.position_id`, l'ID de la position surveillée.
* `asset_id_ref` (`UUID`, *Foreign Key*): Vers `Asset.asset_id`, l'actif concerné.
* `current_qty` (`float`): Quantité actuelle de la position à l'instant du snapshot.
* `average_cost` (`float`): Coût moyen ajusté de la position.
* `side` (`TradeSide`): Sens du trade (`LONG` ou `SHORT`).
* `stop_loss_price` (`float`): Le prix au marché qui déclenche le Stop-Loss (absolu, NULL si non défini).
* `take_profit_price` (`float`): Le prix au marché qui déclenche le Take-Profit (absolu, NULL si non défini).
* `trailing_stop_offset` (`float`): Valeur du décalage pour un Stop-Loss suiveur (NULL si non appliqué).
* `max_unrealized_loss_pct` (`float`): Pourcentage de perte latent maximal toléré (relatif au prix d'entrée).
* `last_market_price` (`float`): Prix de marché le plus récent connu pour cet actif au moment du snapshot.

**Énumérations :**

* `MarketPhase` : (`OPEN`, `CLOSED`, `PRE_MARKET`, `POST_MARKET`, `HALTED`)

**Relations entre entités :**

* `RiskSnapshot` 0..* --- 1 `TradingSession`
  - Chaque instantané de risque est enregistré dans le contexte d'une session.
* `RiskSnapshot` 0..* --- 1 `Position`
  - Chaque ligne d'instantané est associée à une unique position surveillée.
* `RiskSnapshot` 0..* --- 1 `Asset`
  - Chaque ligne d'instantané est associée à l'actif de la position.

---

### 6. Entités liées au portefeuille, à l’exposition et aux flux de trésorerie

#### 6.1. `Portfolio` 

Portfolio représente un portefeuille d'actifs, centralisant les liquidités, les flux de trésorerie et l’ensemble des positions détenues au sein d’une session.

**Attributs :**

* **`portfolio_id`** (`UUID`, *Primary Key*): ID unique du portefeuille.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`
* `inception_date` (`UUID`, *Foreign Key*): Date inception du portefeuille.
* `cash_balance: float` (`float`): Le solde de trésorerie du portefeuille.
* `initial_capital: float` (`float`): Le montant initial de cash déposé dans le portefeuille.
* `total_cash_flow: float` (`float`): Le total cumulé de tous les dépôts moins tous les retraits.
* `updated_timestamp` (`DateTime`): Dernière date de mise à jour des positions du portefeuille.
* `currency: float` (`string`): Devise de base du portefeuille (ex: USD).


**Relations entre entités :**

* `Portfolio` 1 --- 1 `TradingSession`              
  - Un portefeuille appartient à une session.
* `Portfolio` 1 --- 0..* `CashFlow`              
  - Un portefeuille contient des cashflows.
* `Portfolio` 1 --- 0..* `Position`              
  - Un portefeuille contient des positions.



#### 6.1. `CashFlow` 

CashFlow représente un mouvement de liquidité dans un portefeuille, qu’il s’agisse d’un dépôt ou d’un retrait. Il enregistre le type, le montant et la date de la transaction, et est lié au portefeuille concerné.

**Attributs :**

* **`cashflow_id`** (`UUID`, *Primary Key*): ID unique de la transaction de liqudité
* `portfolio_id_ref` (`UUID`, *Foreign Key*): Vers `Portfolio.portfolio_id`
* `flow_type` (`FlowType`): Type de transaction (DEPOSIT, WITHDRAWAL).
* `timestamp` (`DateTime`): Date et heure de la transaction.
* `amount` (`float`): Montant du mouvement (Positif pour injection, Négatif pour retrait).

**Énumérations :**

* `FlowType` : (`DEPOSIT`, `WITHDRAWAL`)

**Relations entre entités :**

* `CashFlow` 0..* --- 1 `Portfolio`              
  - Les cashflow appartient à un portefeuille.

---

### 7. Journal des Événements

#### 7.1. `EventLog` 
Journal de tous les événements critiques du système.

**Attributs :**

* **`event_id`** (`UUID`, *Primary Key*): ID unique de cet événement.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers la `TradingSession`.
* `timestamp` (`DateTime`): Date et heure de l'enregistrement.
* `entity_type` (`EntityType`): Le type de l'entité affectée.
* `entity_id_ref` (`UUID`, *Foreign Key*): L'ID de l'instance spécifique affectée (ex: `order_id`).
* `envent_type` (`EventType`): Catégorie de l'événement.
* `details` (`JSON`): Contient les données détaillées (statuts, erreurs, montants).

**Énumérations :**

* `EntityType` : (`ORDER`, `FILL`, `POSITION_LOT`, `TRADE`, `SYSTEM`, `TRADING_SESSION`, `SCHEDULED_JOB`)
* `EventType` : (`ORDER_CREATED`, `ORDER_STATUS_UPDATE`, `FILL_CREATED`, `FEE_RECEIVED`, `LOT_OPENED`, `LOT_CLOSED`,`TRADE_CLOSED`, `JOB_STARTED`, `JOB_COMPLETED`, `JOB_FAILED`, `SESSION_STATUS_UPDATE`, `MARKET_PHASE_CHANGE`, `SYSTEM_STATE_CHANGE`, `DATA_INTEGRITY_CHECK`, `CRITICAL_ERROR`)

**Définitions :**

* **Événements d'Ordre et d'Exécution**
    * `ORDER_CREATED`: L'ordre a été créé par le système/stratégie. **[ORDER]**
    * `ORDER_STATUS_UPDATE`: Changement critique du statut de l'ordre. **[ORDER]**
    * `FILL_CREATED`: Nouvelle exécution reçue. **[FILL]**
    * `FEE_RECEIVED`: Mise à jour des frais agrégés. **[FILL]**
* **Événements de Position et PnL**
    * `LOT_OPENED`: Nouveau lot de position créé. **[POSITION\_LOT]**
    * `LOT_CLOSED`: Lot de position complètement fermé. **[POSITION\_LOT]**
    * `TRADE_CLOSED`: Cycle de transaction complet finalisé. **[TRADE]**
* **Événements Système et Tâches Planifiées**
    * `JOB_STARTED` / `JOB_COMPLETED` / `JOB_FAILED`: Statut des tâches planifiées. **[SCHEDULED\_JOB]**
    * `SESSION_STATUS_UPDATE`: Changement de statut interne de la session.
    * `MARKET_PHASE_CHANGE`: Changement de phase du marché. **[SYSTEM]**
    * `SYSTEM_STATE_CHANGE`: Le moteur de trading change d'état. **[SYSTEM]**
    * `DATA_INTEGRITY_CHECK`: Résultat d'une vérification de la cohérence. **[SYSTEM]**
    * `CRITICAL_ERROR`: Erreur majeure du système. **[SYSTEM, ORDER, SCHEDULED\_JOB]**

**Relations entre entités :**  
* `EventLog` 0..* --- 1 `Trade`  
  - Chaque événement peut être généré par un trade.
* `EventLog` 0..* --- 1 `RealizationLot`  
  - Chaque événement peut être généré par un lot de réalisation.  
* `EventLog` 0..* --- 1 `AcquisitionLot`  
  - Chaque événement peut être généré par un lot d'acquisition.  
* `EventLog` 0..* --- 1 `Fill`  
  - Chaque événement peut être généré par un fill.  
* `EventLog` 0..* --- 1 `Order`  
  - Chaque événement peut être généré par un ordre.  
* `EventLog` 1..* --- 1 `JobExecution`  
  - Chaque événement appartient à une exécution.  
* `EventLog` 0..* --- 1 `TradingSession`
  - Chaque événement peut appartenir à une session.

#### 7.2. `SystemMetric`

`SystemMetric` représente une mesure unique et atomique de performance ou de santé d'un composant du système (latence, utilisation mémoire, taux de succès). Ces métriques sont collectées de manière asynchrone (Fire-and-Forget).

**Attributs :**

* **`metric_id`** (`UUID`, *Primary Key*): Identifiant unique de cette mesure.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`.
* `timestamp` (`DateTime`): Date et heure précises de la mesure.
* `component_name` (`string`): Nom du module émetteur (ex: 'OrderManager', 'LiveDataHub', 'JobExecutor').
* `metric_name` (`MetricName`): Type de la métrique mesurée (ex: 'ORDER_EXECUTION_LATENCY', 'PRICE_FETCH_TIME').
* `metric_type` (`MetricType`): Catégorie de la métrique (Latence, Compteur, ...).
* `value` (`float`): La valeur numérique de la mesure.
* `unit` (`string`): Unité de la mesure (ex: 'ms', 'count', 'bytes').
* `tags` (`JSON`): Contient des informations contextuelles pour la jointure logique et l'analyse (ex: `{"execution_id": "UUID"}`).

**Énumérations :**

* `MetricName` : (`ORDER_EXECUTION_LATENCY`, `PRICE_FETCH_TIME`, `JOB_RUN_TIME`, `SIMULATED_FILL_RATE`, `DB_QUERY_TIME`, `MEMORY_USAGE`)
* `MetricType` : (`LATENCY`, `COUNTER`, `GAUGE`, `RATE`)

**Relations entre entités :**

* `SystemMetric` 0..* --- 1 `TradingSession`
    * Chaque mesure de performance est liée à une session.
* `SystemMetric` 0..* --- 1 `MetricSnapshot` (Relation logique/Agrégation)
    * Plusieurs mesures individuelles sont agrégées dans un seul instantané. La liaison est basée sur le temps et les tags sans clé étrangère physique.

#### 7.3. `MetricSnapshot`

`MetricSnapshot` représente le conteneur agrégé de plusieurs `SystemMetric` sur une période définie (ex: 1 minute). Il est utilisé par le Monitoring Module pour consolider les données brutes en indicateurs clés pour l'analyse hors ligne ou l'affichage sur le tableau de bord.

**Attributs :**

* **`snapshot_id`** (`UUID`, *Primary Key*): ID unique de cet instantané agrégé.
* `session_id_ref` (`UUID`, *Foreign Key*): Vers `TradingSession.session_id`.
* `start_timestamp` (`DateTime`): Début de la période d'agrégation.
* `end_timestamp` (`DateTime`): Fin de la période d'agrégation.
* `interval` (`string`): Intervalle de temps de l'agrégation (ex: '1m', '5m').
* `metric_name` (`MetricName`): Le type de métrique agrégée.
* `component_name` (`string`): Nom du module concerné par l'agrégation.
* `count` (`integer`): Nombre de `SystemMetric` agrégées dans ce snapshot.
* `average_value` (`float`): La valeur moyenne sur l'intervalle.
* `min_value` (`float`): La valeur minimale enregistrée.
* `max_value` (`float`): La valeur maximale enregistrée.
* `p95_value` (`float`): Le 1er percentile de la valeur.
* `p99_value` (`float`): Le 99ème percentile de la valeur.
* `aggregated_tags` (`JSON`): Agrégation ou échantillonnage des tags contextuels pertinents.

**Relations entre entités :**

* `MetricSnapshot` 0..* --- 1 `TradingSession`
    * Chaque instantané agrégé est lié à une session.
* `MetricSnapshot` 1 --- 0..* `SystemMetric` (Composition/Agrégation)
    * Un instantané agrège l'ensemble des mesures brutes (`SystemMetric`) qui tombent dans son intervalle de temps.
---












