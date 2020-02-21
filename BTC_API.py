import requests
import json
from datetime import datetime
import time

def getDailyVol(ex, COIN="BTC"):
    url = ""
    params=None
    resp = {}
    
    if ex == "binance":
        url = "https://api.binance.com/api/v1/ticker/24hr"
        params = params={"symbol":COIN+"USDT"}
        
    elif ex == "bitfinex":
        url = "https://api.bitfinex.com/v1/stats/%susd" % COIN.lower()
        params = {"period":1}
        
    elif ex == "bitstamp":
        url = "https://www.bitstamp.net/api/ticker"
        
    elif ex == "coinbasepro":
        url = "https://api.pro.coinbase.com/products/%s-USD/stats" % COIN

    elif ex == "gemini":
        url = "https://api.gemini.com/v1/pubticker/%sUSD" % COIN

    elif ex == "okex":
        url = "https://www.okex.com/api/spot/v3/instruments/%s-USDT/ticker" % COIN

    try:
        resp = requests.get(url, params=params)
    except:
        print("An error occured while try to communicate with %s" % ex)
        return None

    if resp.status_code != 200:
        print("Unable to retrieve data from %s (%d)" % (ex, resp.status_code))
        return None
        
    return resp.json()

def getCandle(ex, tint, COIN="BTC", lim=1, start=None, end=None):
    url = ""
    params=None
    ret = None

    ex = ex.lower()

    if not validInterval(ex, tint):
        print("%s is not a valid interval for the %s api" % (tint, ex))
        return ret
    
    if ex == "binance":
        url = "https://api.binance.com/api/v1/klines"
        params ={"symbol":COIN+"USDT", "interval":tint, "limit":lim}
        if start != None and end != None:
            params["startTime"] = start
            params["endTime"] = end
        
    elif ex == "bitfinex":
        # because finex is dumb
        if tint == "1d": tint = "1D"
        elif tint == "1w": tint = "7D"
        url = "https://api-pub.bitfinex.com/v2/candles/trade:%s:t%sUSD/hist" % (tint, COIN)
        params={"limit":lim}

    elif ex == "coinbasepro":
        url = "https://api.pro.coinbase.com/products/%s-USD/candles" % COIN
        params = {"granularity":granFromInterv(tint)}
        if start != None and end != None:
            params["start"] = start
            params["end"] = end

    elif ex == "gemini":
        url = "https://api.gemini.com/v2/candles/%sUSD/%s"
        # because gemini is dumb
        tint = tint.replace("h","hr").replace("d","day")
        url = url % (COIN, tint)
    
    elif ex == "okex":
        url = "https://www.okex.com/api/spot/v3/instruments/%s-USDT/candles" % COIN
        params = {"granularity":str(granFromInterv(tint))}
        if start != None and end != None:
            params["start"] = start
            params["end"] = end
 
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
    oldestTS = resp[-1][0] if ex != "binance" else resp[0][0]
    for entry in resp:
        if isinstance(entry[0], str): # ISO format
            dt = datetime.strptime(entry[0], "%Y-%m-%dT%H:%M:%S.%fZ")
            entry[0] = int((dt - datetime(1970,1,1)).total_seconds())
        elif entry[0] > 9999999999: # millisecond epoch
                entry[0] = int(entry[0] / 1000)


    # normalize all response data to the same order
    # also paginate exchanges that provide limited data per request
    if ex == "bitfinex":
        # reorder to put close after low [t ochl v] -> [t ohlc v]
        temp = resp    
        ret = []
        for x in temp:
            ret.append([x[0], x[1], x[3], x[4], x[2], x[5]])
        return ret
    elif ex == "binance" and lim > 1000:
        startT = oldestTS - granFromInterv(tint)*min((lim-999),1001)*1000
        resp2 = getCandle(ex, tint, lim=lim-1000, start=startT, end=oldestTS)
        resp = resp2 + resp # binance is in reverse order, so resp comes first
    elif ex == "coinbasepro":
        # reorder from [t lhoc v] -> [t ohlc v]
        temp = resp
        ret = []
        for x in temp:
            ret.append([x[0], x[3], x[2], x[1], x[4], x[5]])
        if lim > 300:
            # cbp rejects if start/end result in more than 300 candles
            # calculate time range in ISO format
            startT = datetime.utcfromtimestamp(oldestTS - granFromInterv(tint) * min(lim-299,301)).isoformat()
            endT = datetime.utcfromtimestamp(oldestTS - granFromInterv(tint)).isoformat()
            time.sleep(0.3) # make sure we don't get rate lmiited
            resp2 = getCandle(ex, tint, lim=lim-300, start=startT, end=endT)
            ret += resp2
        return ret
    elif ex == "okex" and lim > 200:
        time.sleep(0.1) # make sure we don't get rate limited
        resp2 = getCandle(ex, tint, lim=lim-200, start="2014-01-01T00:00:00.000Z", end=oldestTS)
        resp += resp2
        
    return resp

def liveTicker(ex, COIN="BTC"):
    url = ""
    params=None
    
    if ex == "coinbasepro":
        url = "https://api.pro.coinbase.com/products/%s-USD/ticker" % COIN

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

    elif ex == "gemini":
        intervals = ["1m", "5m", "15m", "30m", "1h", "6h", "1d"]
        
    elif ex == "okex":
        intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "12h", "1d"]
        # 6h and 1w are valid
    else:
        return False

    return interval in intervals

def isValidSymbol(ex, symbol):
    url = ""
    params = None

    if ex == "binance":
        url = "https://www.binance.com/api/v3/exchangeInfo"
    elif ex == "bitfinex":
        url = "https://api.bitfinex.com/v1/symbols"
    elif ex == "coinbasepro":
        url = "https://api.pro.coinbase.com/products"
    elif ex == "gemini":
        url = "https://api.gemini.com/v1/symbols"
    elif ex == "okex":
        url = "https://www.okex.com/api/spot/v3/instruments"

    try:
        resp = requests.get(url, params=params)
    except:
        print("An error occured while try to communicate with %s" % ex)
        return False

    resp = resp.json()
    if ex == "binance":
        temp = [x for x in resp["symbols"] if x["symbol"] == (symbol + "USDT")]
        return len(temp) > 0
    elif ex == "bitfinex":
        return (symbol.lower() + "usd") in resp
    elif ex == "coinbasepro":
        temp = [x for x in resp if x["id"] == (symbol + "-USD")]
        return len(temp) > 0
    elif ex == "gemini":
        return (symbol.lower() + "usd") in resp
    elif ex == "okex":
        temp = [x for x in resp if x["instrument_id"] == (symbol + "-USDT")]
        return len(temp) > 0
    

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
