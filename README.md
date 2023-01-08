# crypto / bot example and EDA example

mod_a.py is a production bot for Binance Futures (both test and prod environment)

crypto assets are extremely volatile, 
normally we have 10-50 thousands of cases (per month!) when close price (on 120 seconds timeframe) higher than open price more than 0.5%  
as we have extremely low comission (0.04% for taker position for each trade)

bot is able to predict 0.5% of price change in next 120 seconds for top 10 crypto and place orders accordingly
production accuracy about 60-80% for july-october 2022, then 55-65% for november-december  


bot is doing the following
- listening a websocket events (ETHUSDT for this example)
- running prediction based on pretrained tensorflow model
- execute set of orders (MARKET, STOP_MARKET, TAKE_PROFIT_MARKET)


simple EDA based on CNN.ipynb

example of training for 0.5% price increase for ETH 
we have quite interesting confusion matrix (see below)


                             Pred 0                 Pred 1
True 0  TN = 169424 (TNR = 100.00%)   FP = 4 (FPR = 0.00%)
True 1     FN = 7527 (FNR = 99.79%)  TP = 16 (TPR = 0.21%)
