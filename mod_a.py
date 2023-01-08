


import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
print ('importing libraries,models,coeff', end="", flush=True)
import tensorflow
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
import time
import typing
from urllib.parse import urlencode
import hmac
import hashlib
import websocket
import json
import threading
import sqlite3
import talib
import pickle
import sys
import gc


model= tensorflow.keras.models.load_model('session_1001.h5')
print ('..done')



'''
https://dev.binance.vision/t/how-to-implement-otoco-tp-sl-orders-using-api/1622/18
https://testnet.binancefuture.com/en/login
trade_paint@mail.ru
XSW****2
'''

class meta:
    def __init__(self, public_key: str, secret_key: str, testnet: bool, futures: bool):

        self.futures = futures
        self._headers = {'X-MBX-APIKEY': public_key}

        if self.futures:
            self.platform = "binance_futures"
            if testnet:
                self._base_url = "https://testnet.binancefuture.com"
                self._wss_url = "wss://stream.binancefuture.com/ws"
            else:
                self._base_url = "https://fapi.binance.com"
                self._wss_url = "wss://fstream.binance.com/ws"
        else:
            self.platform = "binance_spot"
            if testnet:
                self._base_url = "https://testnet.binance.vision"
                self._wss_url = "wss://testnet.binance.vision/ws"
            else:
                self._base_url = "https://api.binance.com"
                self._wss_url = "wss://stream.binance.com:9443/ws"


        self.leverage = 5   # leverage level should be turned on  (Binance)
        self.deposit = 100 # current deposit USDT
        self.ongoing_position = False

        params = pickle.load(open("ML_params.pkl", "rb"))
        self.mu = params["mu"]
        self.std = params["std"]

        self.a = []
        self.tracking_mode = 0
        self.telegram_api = 'http://api.telegram.org/bot1434154647:AAGf-SNF84zR7jQ7sGShQtJX9Jq5UurTKJI/sendMessage?chat_id=-379051501&text='
        self.lastorder_time = time.time()
        self.lastorder_price = 0
        self.iteration = 0
        self._public_key = public_key
        self._secret_key = secret_key
        self._ws_id = 1
        self.ws: websocket.WebSocketApp
        self.reconnect = True
        self.ws_connected = False
        self.ws_subscriptions = {"bookTicker": [], "aggTrade": []}
        t = threading.Thread(target=self._start_ws)
        t.start()
        print("Binance Futures Client successfully initialized...", end="", flush=True)


    def _start_ws(self):
        self.ws = websocket.WebSocketApp(self._wss_url, on_open=self._on_open, on_close=self._on_close,
                                         on_error=self._on_error, on_message=self._on_message)
        while True:
            try:
                if self.reconnect:  # Reconnect unless the interface is closed by the user
                    self.ws.run_forever(ping_interval=24,ping_timeout=22)  # Blocking method that ends only if the websocket connection drops
                else:
                    break
            except Exception as e:
                print("Binance error in run_forever() method: %s", e)
            time.sleep(2)

    def subscribe_channel(self, contracts: str, channel: str):
        data = dict()
        data['method'] = "SUBSCRIBE"
        data['params'] = []
        data['params'].append(contracts.lower() + "@" + channel)
        data['id'] = self._ws_id
        try:
            self.ws.send(json.dumps(data))  # Converts the JSON object (dictionary) to a JSON string
            print("Binance: subscribing to:",data['params'])
        except Exception as e:
            print("Websocket error while subscribing to @bookTicker and @aggTrade: %s", e)
        self._ws_id += 1

    def _on_open(self, ws):
        print("Binance connection opened...", end="", flush=True)
        self.ws_connected = True
        self.subscribe_channel('ETHUSDT', "aggTrade")

    def _on_close(self, ws,close_status_code, close_msg):
        print("Binance Websocket connection closed",close_msg)
        self.ws_connected = False

    def _on_error(self, ws, msg: str):
        print("Binance connection error: %s", msg)

    def get_deposit(self) -> float:
        data = dict()
        data['timestamp'] = int(time.time() * 1000)
        data['signature'] = self._generate_signature(data)
        if self.futures:
            raw_data = self._make_request("GET", "/fapi/v2/account", data)
        available_deposit_float = 0
        if raw_data is not None:
            available_deposit = raw_data['availableBalance']
            available_deposit_float = float(available_deposit) * 1

        return available_deposit_float

    def _generate_signature(self, data: typing.Dict) -> str:
        return hmac.new(self._secret_key.encode(), urlencode(data).encode(), hashlib.sha256).hexdigest()

    def _make_request(self, method: str, endpoint: str, data: typing.Dict):
        if method == "GET":
            try:
                response = requests.get(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:  # Takes into account any possible error, most likely network errors
                print("Connection error while making %s request to %s: %s", method, endpoint, e)
                return None

        elif method == "POST":
            try:
                response = requests.post(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:
                print("Connection error while making %s request to %s: %s", method, endpoint, e)
                return None

        elif method == "DELETE":
            try:
                response = requests.delete(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:
                print("Connection error while making %s request to %s: %s", method, endpoint, e)
                return None
        else:
            raise ValueError()

        if response.status_code == 200:  # 200 is the response code of successful requests
            return response.json()
        else:
            print("Error while making %s request to %s: %s (error code %s)",
                  method, endpoint, response.json(), response.status_code)
            return None

    def place_order(self, contract: str, type: str, quantity: float, side: str,
                    positionside:str,reduceonly:bool, timeinforce:str, stopprice:float,workingtype:str) -> str:
        data = dict()
        data['symbol'] = contract
        data['side'] = side.upper()
        data['positionSide']= positionside.upper()
        data['quantity'] = quantity  # int() to round down
        data['type'] = type.upper()  # Makes sure the order type is in uppercase
        data['reduceOnly'] = reduceonly
        if type.upper() != 'MARKET':
            data['timeInForce'] = timeinforce.upper()
            data['stopPrice'] = stopprice
            data['workingType'] = workingtype
        data['timestamp'] = int(time.time() * 1000)
        data['signature'] = self._generate_signature(data)

        connected = False
        try_num = 0
        while (not connected) and (try_num < 3):
            try:
                order_status = self._make_request("POST", "/fapi/v1/order", data)
                if order_status is None: raise Exception('failed order')
                connected = True
            except:
                try_num = try_num + 1
                time.sleep(1)
                message = f' failed {try_num}'
                x = requests.post(
                    f'http://api.telegram.org/bot1434154647:AAGf-SNF84zR7jQ7sGShQtJX9Jq5UurTKJI/sendMessage?chat_id=-379051501&text={message}')
                print(message)
                #logger.info(message)
                data = dict()
                data['symbol'] = contract
                data['side'] = side.upper()
                data['positionSide'] = positionside.upper()
                data['quantity'] = quantity  # int() to round down
                data['type'] = type.upper()  # Makes sure the order type is in uppercase
                data['reduceOnly'] = reduceonly
                if type.upper() != 'MARKET':
                    data['timeInForce'] = timeinforce.upper()
                    data['stopPrice'] = stopprice
                    data['workingType'] = workingtype
                data['timestamp'] = int(time.time() * 1000)
                data['signature'] = self._generate_signature(data)

        return order_status


    def _on_message(self, ws, msg: str):
        start_time = time.time()
        data = json.loads(msg)
        if "e" in data:
            symbol = data['s']
            if symbol == "ETHUSDT":
                self.iteration = self.iteration + 1
                self.a.append([float(data['p']), float(data['q']), data['T']])
                if len(self.a)>=25000:
                    self.a.pop(0)
                if self.iteration % 10000 == 0: # update mu, std
                    params = pickle.load(open("ML_params.pkl", "rb"))
                    self.mu = params["mu"]
                    self.std = params["std"]
                    print ('mu,std uploaded')
                df_ini = pd.DataFrame(self.a, columns =['price', 'volume', 'Timestamp'])
                df_ini['Timestamp'] = df_ini['Timestamp'] // 1000
                df_ini = df_ini.assign(Timestamp=pd.to_datetime(df_ini['Timestamp'], unit='s')).set_index('Timestamp')
                df_ohlc = df_ini.resample('1S')['price'].ohlc()  # 1S-1min
                df_vol = df_ini.resample('1S')['volume'].sum()
                df = pd.concat([df_ohlc, df_vol], axis=1)
                df = df.fillna(method='ffill')
                df['rsi'] = talib.RSI(df.close, timeperiod=100)
                df = df.iloc[-301:].copy()              # now take only  301 records
                now = datetime.now()
                if self.iteration % 10 == 0 : print ('A0 buf-len',len(df.index),'//',len(self.a),'time', now, end="", flush=True)
                current_price = df['close'].iloc[-1]
                current_volume = df['volume'].iloc[-1]


                if self.tracking_mode==1 and (time.time()-self.lastorder_time)>600:
                    self.tracking_mode = 0
                    x = requests.post(self.telegram_api + 'tracking_mode_OFF_due_to_FAILURE')
                if self.tracking_mode==1 and current_price > (self.lastorder_price + self.lastorder_price  * 0.4 / 100):
                    self.tracking_mode = 0
                    x = requests.post(self.telegram_api + 'tracking_mode_OFF_due_to_SUCCESS')

                # 400 - 4, 0.75 - 0 - update before production !!!
                if len(df.index) == 301 and current_volume > 400:
                    df = (df - self.mu) / self.std # standartization by loaded mu,std
                    element = df.to_numpy()
                    element = element.reshape(1, 301, 6)  # it's numpy array
                    predictions = model.predict(element, verbose=1)
                    tensorflow.keras.backend.clear_session()
                    gc.collect()
                    if predictions[0] >= 0.75 and (time.time()-self.lastorder_time)>100:
                        self.lastorder_time = time.time()
                        self.lastorder_price = current_price
                        quantity_order = 0.02    # DO NOT FORGET SET LEVERAGE
                        stopprice_sm = round(current_price - current_price * 0.48 / 100,2)
                        stopprice_tp = round(current_price + current_price * 0.48 / 100,2)


                        self.tracking_mode = 1
                        x = requests.post(self.telegram_api+'tracking_mode_ON')
                        order_status = self.place_order(contract='ETHUSDT', type='MARKET', quantity=quantity_order, side='BUY',
                                         positionside='BOTH', reduceonly=False,
                                         timeinforce='', stopprice=0, workingtype='')
                        if order_status is not None:
                            self.place_order(contract='ETHUSDT', type='STOP_MARKET', quantity=quantity_order, side='SELL',
                                             positionside='BOTH', reduceonly=True,
                                             timeinforce='GTE_GTC', stopprice=stopprice_sm, workingtype='MARK_PRICE')
                            self.place_order(contract='ETHUSDT', type='TAKE_PROFIT_MARKET', quantity=quantity_order, side='SELL',
                                             positionside='BOTH', reduceonly=True,
                                             timeinforce='GTE_GTC', stopprice=stopprice_tp, workingtype='MARK_PRICE')
                        else:
                            x = requests.post(f'http://api.telegram.org/bot1434154647:AAGf-SNF84zR7jQ7sGShQtJX9Jq5UurTKJI/sendMessage?chat_id=-379051501&text=E200!')

                if self.iteration % 10 == 0:print (' -- timeproc',round(time.time()- start_time,3))  # make candles and  evaluate model



#meta = meta("************************", "************************",testnet=True, futures=True)

meta=meta("************************","************************",testnet=False, futures=True)
