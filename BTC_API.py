import requests
import json
from datetime import datetime

def getDailyVol(ex):
    url = ""
    params=None
    resp = {}
    
    if ex == "binance":
        url = "https://api.binance.com/api/v1/ticker/24hr"
        params = params={"symbol":"BTCUSDT"}
        
    elif ex == "bitfinex":
        url = "https://api.bitfinex.com/v1/stats/btcusd"
        params = {"period":1}
        
    elif ex == "bitstamp":
        url = "https://www.bitstamp.net/api/ticker"
        
    elif ex == "coinbasepro":
        url = "https://api.pro.coinbase.com/products/BTC-USD/stats"

    elif ex == "gemini":
        url = "https://api.gemini.com/v1/pubticker/BTCUSD"

    elif ex == "okex":
        url = "https://www.okex.com/api/spot/v3/instruments/BTC-USDT/ticker"

    try:
        resp = requests.get(url, params=params)
    except:
        print("An error occured while try to communicate with %s" % ex)
        return None

    if resp.status_code != 200:
        print("Unable to retrieve data from %s (%d)" % (ex, resp.status_code))
        return None
        
    return resp.json()

def getCandle(ex, tint, lim=1):
    url = ""
    params=None
    ret = None

    ex = ex.lower()

    if not validInterval(ex, tint):
        print("%s is not a valid interval for the %s api" % (tint, ex))
        return ret
    
    if ex == "binance":
        url = "https://api.binance.com/api/v1/klines"
        params ={"symbol":"BTCUSDT", "interval":tint, "limit":lim}
        
    elif ex == "bitfinex":
        # because finex is dumb
        if tint == "1d": tint = "1D"
        elif tint == "1w": tint = "7D"
        url = "https://api-pub.bitfinex.com/v2/candles/trade:%s:tBTCUSD/hist" % tint
        params={"limit":lim}

    elif ex == "coinbasepro":
        url = "https://api.pro.coinbase.com/products/BTC-USD/candles"
        params = {"granularity":granFromInterv(tint)}

    elif ex == "gemini":
        url = "https://api.gemini.com/v2/candles/BTCUSD/%s"
        # because gemini is dumb
        tint = tint.replace("h","hr").replace("d","day")
        url = url % tint
    
    elif ex == "okex":
        url = "https://www.okex.com/api/spot/v3/instruments/BTC-USDT/candles"
        params = {"granularity":str(granFromInterv(tint))}
 
    else:
        print("No API for exchange %s" % ex)
        return ret
               
    try:
        resp = requests.get(url, params=params)
    except:
        print("An error occured while try to communicate with %s" % ex)
        return ret

    if resp.status_code != 200:
        print("Unable to retrieve data from %s (%d)" % (ex, resp.status_code))
        return ret
    
    # normalize to consistent timestamps
    resp = resp.json()
    for entry in resp:
        if isinstance(entry[0], str):
            dt = datetime.strptime(entry[0], "%Y-%m-%dT%H:%M:%S.%fZ")
            entry[0] = int((dt - datetime(1970,1,1)).total_seconds())
        else:
            if entry[0] > 9999999999:
                entry[0] = int(entry[0] / 1000)
      
    if ex == "bitfinex":
        # reorder to put close after low [t ochl v] -> [t ohlc v]
        temp = resp    
        ret = []
        for x in temp:
            ret.append([x[0], x[1], x[3], x[4], x[2], x[5]])
        return ret
    elif ex == "coinbasepro":
        # reorder from [tlhocv] -> [tohlcv]
        temp = resp
        ret = []
        for x in temp:
            ret.append([x[0], x[3], x[2], x[1], x[4], x[5]])
        return ret
    
    return resp

def liveTicker(ex):
    url = ""
    params=None
    
    if ex == "coinbasepro":
        url = "https://api.pro.coinbase.com/products/BTC-USD/ticker"

    try:
        resp = requests.get(url, params=params)
    except:
        print("An error occured while try to communicate with %s" % ex)
        return None

    if resp.status_code != 200:
        print("Unable to retrieve data from %s (%d)" % (ex, resp.status_code))
        return None
    
    return resp.json()

def validInterval(ex, interval):
    intervals = []
    
    if ex == "binance":
        intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "6h", "12h", "1d", "1w"]
        
    elif ex == "bitfinex":
        intervals = ["1m", "5m", "15m", "30m", "1h", "3h", "6h", "12h", "1d", "1w"]

    elif ex == "coinbasepro":
        intervals = ["1m", "5m", "15m", "1h", "6h", "1d"]
        #grans = [60, 300, 900, 3600, 14400, 86400]

    elif ex == "gemini":
        intervals = ["1m", "5m", "15m", "30m", "1h", "6h", "1d"]
        
    elif ex == "okex":
        intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "6h", "12h", "1d"]
        #grans = [60, 180, 300, 900, 1800, 3600, 7200, 14400, 43200, 86400]

    else:
        return False

    return interval in intervals

def granFromInterv(tint):
    num = int(tint[:-1])
    unit = tint[-1]
    if unit == "m":
        return num * 60
    elif unit == "h":
        return num * 3600
    elif unit == "d":
        return num * 86400
    elif unit == "w":
        return num * 604800
    else:
        print("Invalid interval unit")
        return 0
