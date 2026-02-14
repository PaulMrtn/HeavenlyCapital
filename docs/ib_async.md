## Documentation des Méthodes `ib_async`

## Table des matières

- [Class IB](#class-ib)
- [Class Client](#class-client)
- [Class Contract](#class-contract)
- [Class Ticker](#class-ticker)
- [Class Object](#class-objects)

---

## Class IB

Pour chaque methode, il existe une version asynchrone, à adapter selon l’usage.

### Connexion et récupération initiale

- **fetchFields** : lors de la connexion (`connect()`), tu peux définir quelles données récupérer automatiquement :


    fetchFields = StartupFetch.POSITIONS | ORDERS_OPEN | ORDERS_COMPLETE | ACCOUNT_UPDATES | SUB_ACCOUNT_UPDATES | EXECUTIONS


- **TimezoneTWS**: paramètre pour adapter le fuseau horaire à celui de TWS/IB Gateway :


    TimezoneTWS = 'Europe/Paris'


### Event loop et scheduling

- **`run(*, timeout=None)`**  
  Lance la boucle d’événements.  
  - Si des awaitables sont fournis, attend leur complétion et retourne leurs résultats.  
  - `timeout` optionnel pour limiter l’attente.  


- **`schedule(callback, *args)`**  
  Planifie un callback à exécuter à un moment donné.  
  - Paramètres : `time` (time | datetime), `callback` (Callable), `args` (arguments pour le callback)  
  - _Retour_ : Event Handle  


- **`sleep(secs: float)`**  
  Attend un nombre de secondes tout en laissant le framework traiter les événements en arrière-plan.  
  - Ne jamais utiliser `time.sleep()`  
  - _Retour_ : `bool`  


- **`timeRange(start, end, step)`**  
  Itérateur qui attend périodiquement jusqu’aux points temporels spécifiés, en les renvoyant.  
  - Paramètres : `start` (time | datetime), `end` (time | datetime), `step` (float en secondes)  
  - _Retour_ : `Iterator[datetime]`
  - 

* **`timeRangeAsync()`**
  * Version **asynchrone** de `timeRange()`.
  * Permet d’itérer sur des points temporels tout en utilisant `async/await`.
  * *Retour* : `AsyncIterator[datetime]`


* **`waitUntil(t)`**
  * Attend jusqu’au moment `t` spécifié.
  * Paramètre : `t` (time | datetime)
  * *Retour* : `bool` (True si atteint)


* **`waitOnUpdate(timeout=0)`**
  * Attend qu’une **nouvelle mise à jour réseau** arrive.
  * Paramètre : `timeout` (float, secondes) – 0 = pas de timeout.
  * *Retour* : `bool` (True si pas de timeout, False sinon)
  * **Note** : à utiliser uniquement pour attendre des updates, pas pour récupérer des ticks, car des ticks peuvent être perdus.


* **`loopUntil(condition=None, timeout=0)`**

  * Itère jusqu’à ce qu’une **condition soit remplie**, avec un timeout optionnel.
  * Paramètres :

    * `condition` : fonction prédicat testée après chaque update réseau
    * `timeout` : temps maximum d’attente en secondes (0 = infini)
  * *Retour* : Iterator[object] (valeur de la condition ou False si timeout)


* **`setTimeout(timeout=60)`**
  * Définit un timeout pour la réception des messages TWS/IB Gateway.
  * Émet `timeoutEvent` si aucune donnée reçue pendant trop longtemps.
  * Paramètre : `timeout` (float, secondes)


### Comptes, positions et portefeuilles

- **`managedAccounts()`**  
  Liste les comptes gérés par le client IB.  
  _Retour_ : `list[str]`  
  > Utile pour itérer sur plusieurs comptes ou filtrer les données.

- **`accountSummary(account='')`**  
  Retourne un résumé des valeurs du compte (blocage à la première exécution).  
  Paramètre : `account` (str, optionnel)  
  _Retour_ : `list[AccountValue]`  
  > Pratique pour obtenir un snapshot complet d’un compte ou pour dashboards/logs.

- **`portfolio(account='')`**  
  Liste les positions du portefeuille pour un compte ou tous les comptes.  
  Paramètre : `account` (str, optionnel)  
  _Retour_ : `list[PortfolioItem]`  
  > Indispensable pour suivre la composition du portefeuille et la valeur des positions.

- **`positions(account='')`**  
  Liste les positions individuelles pour un compte ou tous comptes.  
  Paramètre : `account` (str, optionnel)  
  _Retour_ : `list[Position]`  
  > Utile pour obtenir les détails des positions (contrats, tailles, prix d’entrée) et gérer les ordres/PnL.


### Trades et Ordres (pour la reconciliation ou le suivi)

- **`trades()`**  
  Liste tous les trades de la session en cours.  
  _Retour_ : `list[Trade]`  
  > Utile pour obtenir l’historique complet des trades de la session.

- **`orders()`**  
 Liste tous les ordres passés dans la session.  
 _Retour_ : `list[Order]`  
 > Historique complet des ordres soumis.

- **`fills()`**  
  Liste tous les fills (exécutions partielles ou complètes d’ordres) de la session.  
  _Retour_ : `list[Fill]`  
  > Utile pour suivre exactement ce qui a été exécuté pour chaque ordre.

- **`executions()`**  
  Liste toutes les exécutions de la session.  
  _Retour_ : `list[Execution]`  
  > Permet d’analyser le détail des exécutions pour reporting ou suivi précis des trades.
  
- **`openTrades()`**  
  Liste tous les trades ouverts (non clôturés).  
  _Retour_ : `list[Trade]`  
  > Permet de suivre les trades encore actifs sur le marché.
  
- **`openOrders()`**  
  Liste tous les ordres ouverts (non exécutés ou partiellement remplis).  
  _Retour_ : `list[Order]`  
  > Permet de suivre les ordres encore actifs ou en attente sur le marché.
  

### Placement et gestion d’ordres

- **`bracketOrder(action, quantity, limitPrice, takeProfitPrice, stopLossPrice, **kwargs)`**  
  Crée un ordre limit automatiquement encadré par :
  - un take-profit
  - un stop-loss  
  > Permet de gérer le risque et l’objectif de gain dès l’entrée en position.  
  > À envoyer ensuite avec `placeOrder()` pour chaque ordre du bracket.

- **`placeOrder(contract, order)`**  
  Place un nouvel ordre ou modifie un ordre existant.  
  _Retour_ : `Trade` (mis à jour en temps réel : status, fills, etc.)  
  > Fonction centrale pour envoyer des ordres à IB.

- **`cancelOrder(order, manualCancelOrderTime='')`**  
  Annule un ordre ouvert.  
  _Retour_ : `Trade | None`  
  > Permet de gérer proprement l’annulation d’ordres en attente ou partiellement exécutés.

### Méthodes `req*` réellement utiles

- **`reqCurrentTime()`**  
  Demande l’heure actuelle de TWS/IB Gateway.  
  _Retour_ : `datetime`  
  > Permet de synchroniser ton algo sur l’heure officielle IB plutôt que l’heure machine.

- **`reqCompletedOrders(apiOnly)`**  
  Retourne la liste des trades complétés.  
  Paramètre : `apiOnly` (bool) – True pour uniquement les ordres passés via l’API.  
  _Retour_ : `list[Trade]`  
  > Très utile après un redémarrage pour reconstruire l’historique réel des trades, contrairement à `trades()` qui ne contient que la session en cours.

### Méthodes Contrats et Tick Size

- **`reqContractDetails(contract)`**  
  Récupère la liste des détails pour le contrat donné.  
  _Retour_ : `list[ContractDetails]`  
  > Permet de vérifier qu’un contrat est valide et pleinement qualifié, et d’obtenir toutes les infos essentielles : exchange réel, trading hours, marketRuleIds, minTick, etc.  
  > À utiliser avant de placer un ordre pour connaître les règles exactes du produit.

- **`reqMarketRule(marketRuleId)`**  
  Récupère les règles d’incréments de prix (tick size) pour un marché ou contrat donné.  
  _Paramètre_ : `marketRuleId` (int)  
  _Retour_ : `PriceIncrement`  
  > Critique pour déterminer les prix valides pour les ordres limit.  
  > Indispensable si tu calcules des limitPrice, stopLossPrice ou takeProfitPrice afin que les ordres ne soient jamais rejetés.


### Méthodes Historiques

- **`reqHistoricalData(contract, endDateTime, durationStr, barSizeSetting, whatToShow, useRTH, formatDate=1, keepUpToDate=False, chartOptions=[], timeout=60)`**  
  Récupère des barres historiques pour un contrat, intraday ou multi-jours.  
  _Retour_ : `BarDataList`  
  > Très utile pour backtest ou analyse de séries historiques.  
  > `keepUpToDate=True` permet un flux quasi temps réel.  
  > Pour de longues périodes ou barres très fines, il est possible de faire des requêtes “chunkées” en boucle pour reconstituer l’historique complet, sans consommer de slots ou snapshots IB.  
  > Paramètres clés à connaître : `durationStr` (durée totale), `barSizeSetting` (taille d’une barre), `whatToShow` (TRADES/BID/ASK), `useRTH` (heures normales).


### Méthodes Market Data

- **`reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False, mktDataOptions=[])`**  
  Abonne ou demande un snapshot de ticks pour un contrat.  
  _Retour_ : `Ticker`  
  > Permet d’obtenir un flux continu de données de marché ou un état instantané. Idéal pour algo intraday, suivi prix/volume, ou vérification ponctuelle du marché.

- **`cancelMktData(contract)`**  
  Annule un abonnement à un flux de ticks de marché.  
  _Retour_ : `bool`  
  > Libère les ressources API lorsque le flux n’est plus nécessaire. Retour True si annulation réussie.

- **`reqSmartComponents(bboExchange)`**  
  Récupère la correspondance entre les codes d’exchanges SmartRouting et leurs noms complets.  
  _Retour_ : `list[SmartComponent]`  
  > Utile pour connaître les exchanges disponibles et leurs codes si tu veux passer un ordre sur un exchange spécifique au lieu de laisser SMART router automatiquement. Pour actions S&P500/Nasdaq 100,

---

## Class Client

### Client - Connexion

- **`connectionStats()`**  
  Retourne des statistiques sur la connexion IB active.  
  _Retour_ : `ConnectionStats`  
  > Permet de surveiller et diagnostiquer la qualité et la stabilité de la connexion avec TWS ou IB Gateway.


### Temps et Synchronisation

- **`reqCurrentTime()`**  
  Demande l’heure actuelle de TWS/IB Gateway.  
  _Retour_ : `datetime`  
  > Permet de synchroniser tes algos avec l’heure officielle IB plutôt que l’heure machine locale.

## Class Contract

- **`Stock(symbol, exchange, currency, primaryExchange=...)`**  
  Constructeur spécialisé pour créer un `Contract` de type **STK** correctement formé pour IBKR.  
  _Retour_ : `Contract` (secType='STK')  
  > Utiliser systématiquement `primaryExchange` pour lever toute ambiguïté d’identification du titre chez IB.
  > Pattern robuste : `Stock('AAPL', 'SMART', 'USD', primaryExchange='NASDAQ')`.

- **`Forex(pair: str, exchange='IDEALPRO')`**  
  Crée un contrat Forex (`secType='CASH'`) à partir d’une paire type `EURUSD`.  
  _Retour_ : `Contract` (spécialisé Forex)  
  > Raccourci sûr pour définir un spot FX IB correct. Garantit le bon mapping `symbol/currency` et évite les erreurs de routing (CFD, data absente) si `exchange='IDEALPRO'` est respecté.

- **`Contract.update(*srcObjs, **kwargs)`**  
  Met à jour dynamiquement les champs du contrat.  
  _Retour_ : `Contract`  
  > Permet de réutiliser un contrat existant et de modifier certains paramètres sans le recréer.

- **`ContractDetails(contract=None, marketName='', minTick=0.0, orderTypes='', validExchanges='', ...)`**  
  Contient toutes les informations détaillées d’un instrument financier au-delà du simple contrat.  
  _Retour_ : ContractDetails  
  > Permet d’accéder aux heures de trading, types d’ordres, taille minimale, données obligataires/options, et autres métadonnées nécessaires pour configurer correctement les requêtes de marché et algos de trading.

- **`tradingSessions()`**  
  Retourne les sessions de trading pour ce contrat.  
  _Retour_ : list[TradingSession]  
  > Utile pour déterminer quand le produit peut être échangé et planifier des actions ou analyses selon les horaires de marché.

- **`liquidSessions()`**  
  Retourne les sessions où le marché est considéré liquide.  
  _Retour_ : list[TradingSession]  
  > Permet de savoir quand le marché est suffisamment actif pour exécuter des stratégies ou ordres avec un impact minimal.

- **`ContractDescription(contract, derivativeSecTypes)`**  
  Contient la description d’un contrat et les types de dérivés disponibles.  
  _Retour_ : ContractDescription  
  > Permet de connaître rapidement les dérivés liés à un sous-jacent, utile pour scanner ou lister options/futures sans récupérer tous les détails complets d’un contrat.

## Class Ticker

La classe `Ticker` représente un flux de données de marché pour une action (niveau 1).  
Elle stocke les prix bid, ask, last, volumes et fournit des méthodes pour accéder à un prix de marché fiable et pour gérer facilement les données reçues en streaming.

- **`dividends`**  
  Contient les informations de dividendes liées à l’action.  
  _Retour_ : `Dividends | None`  
  > Permet de récupérer les dates et montants de dividendes pour ajuster des calculs ou stratégies.

- **`hasBidAsk()`**  
  Vérifie si le ticker possède un bid et ask valides.  
  _Retour_ : bool  
  > Permet de savoir si les prix de niveau 1 sont exploitables pour les calculs ou décisions de trading.

- **`midpoint()`**  
  Retourne la moyenne du bid et de l’ask, ou unset si non disponible.  
  _Retour_ : float  
  > Utile pour obtenir un prix de référence intermédiaire quand last n’est pas fiable ou indisponible.

- **`marketPrice()`**  
  Retourne le prix de marché principal : last si disponible et cohérent, sinon midpoint.  
  _Retour_ : float  
  > Fournit un prix unique à utiliser dans les algos intraday ou indicateurs, simplifiant la logique.

- **`update(*srcObjs, **kwargs)`**  
  Met à jour les champs du ticker à partir d’autres objets ou arguments.  
  _Retour_ : object  
  > Permet d’actualiser un ticker existant sans recréer un nouvel objet, utile pour le streaming continu.

### TickerUpdateEvent

Permet un pipeline Tickfilter/TickerUpdateEvent qui propage des prix pre-traitée.

- **`trades()`**  
  Émet uniquement les ticks correspondant aux derniers trades.  
  _Retour_ : Tickfilter  
  > Permet de réagir aux transactions réalisées, utile pour calculs intraday ou VWAP.

- **`bids()`**  
  Émet uniquement les ticks correspondant aux bids.  
  _Retour_ : Tickfilter  
  > Permet de suivre l’évolution du prix acheteur dans le carnet.

- **`asks()`**  
  Émet uniquement les ticks correspondant aux asks.  
  _Retour_ : Tickfilter  
  > Permet de suivre l’évolution du prix vendeur dans le carnet.

- **`bidasks()`**  
  Émet les ticks des bids et asks combinés.  
  _Retour_ : Tickfilter  
  > Utile pour calculer les spreads ou surveiller globalement le carnet de marché.

- **`midpoints()`**  
  Émet les ticks correspondant aux midpoints (moyenne bid/ask).  
  _Retour_ : Tickfilter  
  > Utile pour stratégies utilisant des prix “de marché” normalisés plutôt que bid/ask individuels.

### Tickfilter

Permet un pipeline Tickfilter/TickerUpdateEvent qui propage des prix pre-traitée.

- **`on_source(ticker)`**  
  Émet un tick à tous les abonnés du filtre.  
  _Retour_ : None  
  > Permet de propager les ticks filtrés depuis un Ticker vers ton code ou des modules d’analyse.

- **`timebars(timer)`**  
  Agrège les ticks en barres temporelles basées sur un événement timer.  
  _Retour_ : TimeBars  
  > Génère des bougies intraday pour analyse ou visualisation en fonction d’intervalles temporels.

- **`tickbars(count)`**  
  Agrège les ticks en barres contenant un nombre fixe de ticks.  
  _Retour_ : TickBars  
  > Crée des barres uniformes basées sur le flux d’exécution plutôt que le temps.

- **`volumebars(volume)`**  
  Agrège les ticks en barres basées sur un volume fixe.  
  _Retour_ : VolumeBars  
  > Suit la dynamique réelle du marché et produit plus de barres lors de volumes élevés.


### Tick & Bar Classes

- **`classib_async.ticker.Bar(time, open=nan, high=nan, low=nan, close=nan, volume=0, count=0)`**  
  Représente une barre de prix/volume unique.  
  _Retour_ : Bar  
  > Utilisé pour stocker les données agrégées d’un intervalle de ticks ou de temps.

- **`classib_async.ticker.BarList(*args)`**  
  Conteneur de plusieurs objets `Bar`.  
  _Retour_ : BarList  
  > Permet de gérer et parcourir facilement une série de barres.

- **`classib_async.ticker.TimeBars(timer, source=None)`**  
  Agrège les ticks en barres basées sur un événement de temps.  
  _Retour_ : TimeBars avec `bars: BarList`  
  > Idéal pour créer des barres temporelles (ex. 1 min, 5 min) à partir d’un flux de ticks.

- **`classib_async.ticker.TickBars(count, source=None)`**  
  Agrège les ticks en barres contenant un nombre fixe de ticks.  
  _Retour_ : TickBars avec `bars: BarList`  
  > Pratique pour analyser des mouvements de marché basés sur un nombre constant de transactions.

- **`classib_async.ticker.VolumeBars(volume, source=None)`**  
  Agrège les ticks en barres atteignant un volume total spécifique.  
  _Retour_ : VolumeBars avec `bars: BarList`  
  > Utile pour suivre l’activité du marché où le volume est plus significatif que le temps ou le nombre de ticks.

- **`on_source(time, price, size)`**  
  Émet un nouveau tick ou valeur vers tous les listeners connectés.  
  _Retour_ : None  
  > Méthode centrale pour injecter les ticks dans les objets `TimeBars`, `TickBars` ou `VolumeBars`.


---

## Class Objects

### Objets Fills, Exécutions & Rattrapage

- **`Execution`**  
  Représente une exécution réelle d’ordre sur le marché (un fill). Chaque match partiel ou total d’un ordre génère un objet `Execution`.  
  _Retour_ : Objet `Execution` (via `fills()` ou `executions()`)  
  > C’est la source de vérité absolue de ton trading : prix réellement exécuté, taille exécutée, timestamp exact, exchange utilisé. Indispensable pour reconstruire ton historique, calculer ton slippage réel, analyser la qualité d’exécution et rejouer fidèlement tes trades après un redémarrage.

- **`CommissionReport(execId, commission, currency, realizedPNL, ...)`**  
  Rapport de commission associé à une exécution (`Execution`) via `execId`.  
  _Retour_ : `CommissionReport` (dataclass)  
  > Indispensable pour connaître le coût réel du fill et le PnL officiel calculé par IB. Permet une reconstruction exacte de la performance, du slippage réel et des frais après redémarrage, en complément de `Execution`.
  
- **`Fill(contract, execution, commissionReport, time)`**  
  Représente l’exécution complète d’un ordre avec détails du contrat, exécution, commission et timestamp.  
  _Retour_ : Fill  
  > Utile pour suivre toutes les exécutions d’ordres, calculer le PnL net, et mettre à jour automatiquement les positions ou portefeuilles.
  
- **`ExecutionFilter(time, symbol, side, acctCode, clientId, secType, exchange)`**  
  Définit des critères pour filtrer les exécutions retournées par `reqExecutions()`.  
  _Retour_ : `ExecutionFilter`  
  > Utile uniquement lors d’une période de redémarrage pour récupérer proprement les exécutions manquées depuis un instant précis, sans rescanner tout l’historique IB.

- **`TradeLogEntry(time, status='', message='', errorCode=0)`**  
  Représente une entrée de journal d’un événement ou d’une action de trading.  
  _Retour_ : TradeLogEntry  
  > Permet de suivre, tracer et analyser les opérations et erreurs de trading. Utile pour l’audit, le débogage ou la génération de logs automatisés.

- **`AccountValue(account, tag, value, currency, modelCode)`**  
  Représente une valeur spécifique d’un compte IBKR.  
  _Retour_ : `AccountValue`  
  > Utile pour suivre dynamiquement le solde, le PnL, la marge ou tout indicateur de compte, et pour construire des DataFrames ou logs de l’état du compte.

- **`PriceIncrement(lowEdge, increment)`**  
  Crée un objet représentant l’incrément de prix pour un instrument selon sa plage de prix.  
  _Retour_ : PriceIncrement  
  > Permet de calculer ou valider les prix d’ordres pour qu’ils respectent le tick minimum autorisé par IBKR, utile pour automatiser la gestion des prix et éviter les erreurs d’ordre.

- **`PortfolioItem(contract, position, marketPrice, marketValue, averageCost, unrealizedPNL, realizedPNL, account)`**  
  Représente une position individuelle dans un compte IBKR.  
  _Retour_ : `PortfolioItem`  
  > Permet de suivre et gérer les positions avec PnL, valeur de marché et quantité pour chaque contrat. Idéal pour dashboards, calculs de portefeuille ou stratégie.

- **`Position(account, contract, position, avgCost)`**  
  Crée une position ouverte dans un compte IBKR.  
  _Retour_ : `Position`  
  > Utile pour suivre rapidement la quantité et le prix moyen d’une position sans inclure le prix de marché ou le PnL. Idéal comme base pour calculer PnL ou marketValue plus tard.

- **`Dividends(past12Months, next12Months, nextDate, nextAmount)`**  
  Représente les dividendes passés et prévus d’un instrument.  
  _Retour_ : `Dividends`  
  > Permet de suivre le flux de dividendes pour calculer l’impact sur le PnL et générer des rapports financiers.

- **`connectionStats()`**  
  Récupère les statistiques détaillées de la connexion IB (octets, messages, durée).  
  _Retour_ : ConnectionStats  
  > Permet de monitorer l’activité réseau et la performance de la connexion, utile pour le debug ou l’audit des sessions IB.

- **`RequestError(reqId, code, message)`**  
  Exception levée pour une erreur liée à une requête spécifique.  
  _Retour_ : Exception  
  > Permet de capturer et gérer précisément les erreurs retournées par l’API pour une requête donnée, utile pour le debug, le logging détaillé et la logique de retry ciblée.

  
### Objets tick Attribution

- **`TickAttrib(canAutoExecute=False, pastLimit=False, preOpen=False)`**  
Objet décrivant le contexte d’un tick reçu via `reqMktData` ou `reqTickByTickData`.  
_Retour_ : TickAttrib  
> Indique si le tick est potentiellement tradable (`canAutoExecute`), si le prix est hors limites IB (`pastLimit`), ou si le tick provient d’une pré-ouverture (`preOpen`). Très utile pour filtrer les ticks non exécutables et éviter de baser des décisions de trading sur des prix fictifs ou inaccessibles.

- **`TickAttribBidAsk(bidPastLow=False, askPastHigh=False)`**  
  Indique si le bid ou l’ask a dépassé les limites récentes.  
  _Retour_ : TickAttribBidAsk  
  > Permet de détecter les ticks bid/ask extrêmes ou anormaux pour filtrer les données ou sécuriser les décisions dans un algo intraday.

- **`TickAttribLast(pastLimit=False, unreported=False)`**  
  Informations sur le tick “last” (dernière transaction).  
  _Retour_ : TickAttribLast  
  > Permet de savoir si le dernier tick est au-delà du prix limite (`pastLimit`) ou non encore reporté par la bourse (`unreported`). Utile pour filtrer les ticks exploitables dans un algo intraday ou scalping.

## AlgoParams / TagValue (Adaptive)

- **`TagValue(tag, value)`**  
  Objet clé/valeur utilisé par IB pour configurer les paramètres des algorithmes d’ordres (`order.algoParams`).  
  _Retour_ : `TagValue`  
  > Sert de conteneur standard pour transmettre à TWS les réglages fins d’un algo (ici **Adaptive**).

- **`order.algoStrategy = 'Adaptive'`**  
  Active le smart-routing microstructure **Adaptive** d’IBKR sur l’ordre.  
  _Retour_ : `str` (affectation)  
  > Délègue à IB l’optimisation dynamique make/take, déplacement dans le spread et routage multi-venues.

- **`order.algoParams = [TagValue('adaptivePriority', value)]`**  
  Définit le niveau d’agressivité de l’algo Adaptive.  
  _Retour_ : `list[TagValue]`  
  > Paramètre **clé** qui change le comportement réel du smart-router.

- **`TagValue('adaptivePriority', 'Urgent')`**  
  Mode très agressif, traverse souvent le spread pour exécuter vite.  
  _Retour_ : `TagValue`  
  > Équivalent d’un market order intelligent, priorise la vitesse au prix.

- **`TagValue('adaptivePriority', 'Normal')`**  
  Mode équilibré, travaille majoritairement au midpoint et alterne make/take.  
  _Retour_ : `TagValue`  
  > Réglage par défaut recommandé pour un fill propre avec peu de slippage.

- **`TagValue('adaptivePriority', 'Patient')`**  
  Mode passif, poste dans le book et attend d’être exécuté.  
  _Retour_ : `TagValue`  
  > Idéal pour grosses tailles et réduction maximale du slippage/frais maker.

- **`LimitOrder + Adaptive`**  
  Compatible avec les ordres LIMIT sans modifier ton prix max.  
  _Retour_ : Comportement interne IB  
  > IB déplace le limit **en interne** dans la fourchette autorisée pour optimiser l’exécution sans changer ta contrainte prix.
