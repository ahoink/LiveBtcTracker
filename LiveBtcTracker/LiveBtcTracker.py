import time
import threading
import argparse
import os
import ctypes
from datetime import datetime, timedelta

from CandlestickChart import CandlestickChart
from Configuration import DefaultConfig
import BTC_API as api

def retrieveData():
    global lastBfx
    global cbpPrice
    global exchanges
    global numEx
    global candleData
    global useCBP
    global rdy

    failures = [0]*numEx
    if run: print("success")
    else: print("failed")
    
    while run:
        ti = time.time()

        # Get CoinbasePro live ticker price
        if useCBP:
            cbpPrice = api.liveTicker("coinbasepro", SYMBOL)
            if cbpPrice == None:
                cbpPrice = {"price":0}
                failures[-1] += 1
                
        # Get candle data from each exchange        
        for i in range(numEx):
            # bitfinex api is rate limited to every 3 seconds
            if (exchanges[i] == "bitfinex" and time.time() - lastBfx < 3):
                continue

            temp = api.getCandle(exchanges[i], INTERVAL, SYMBOL)
            if exchanges[i] == "bitfinex": lastBfx = time.time()
            
            # Check if latest data was retrievable
            if not isCandleUpdated(exchanges[i], temp):
                failures[i] += 1
                if failures[i] == 3:
                    ts_fail = time.strftime("%m/%d %H:%M:%S", time.localtime(ti))
                    print("%s - Stopping requests to %s (Restart to try again)" % (ts_fail, exchanges[i]))
                temp = [0]*6
            else:
                failures[i] = 0
                if exchanges[i] == "coinbasepro":
                    candleData[i][0][1] = temp[0][1]
                    candleData[i][0][2] = max(candleData[i][0][2], float(cbpPrice["price"]))
                    if cbpPrice["price"] != 0: candleData[i][0][3] = min(candleData[i][0][3], float(cbpPrice["price"]))
                    if cbpPrice["price"] != 0: candleData[i][0][4] = float(cbpPrice["price"])
                else:
                    candleData[i] = temp
                             
        # Check if any exchange failed three times in a row
        if 3 in failures:
            exchanges = [ex for ex,f in zip(exchanges, failures) if f < 3]
            candleData = [d for d,f in zip(candleData, failures) if f < 3]
            failures = [f for f in failures if f < 3]  
            numEx = len(exchanges)
            useCBP = ("coinbasepro" in exchanges)

        rdy = True
        tf = time.time()
        time.sleep(max(0.01, 1-(tf-ti)))
    print("ended")

def secondsToString(time_s):
    timeStr = ""
    if time_s >= 86400:
        dys = time_s/86400
        hrs = (dys-int(dys))*24
        mns = (hrs-int(hrs))*60
        scs = (mns-int(mns))*60
        timeStr = "%d:%02d:%02d:%02d" % (dys, hrs, mns, scs)
    elif time_s >= 3600:
        hrs = time_s/3600
        mns = (hrs-int(hrs))*60
        scs = (mns-int(mns))*60
        timeStr = "%02d:%02d:%02d" % (hrs, mns, scs)
    else:
        mns = time_s/60
        scs = time_s if mns == 0 else (mns-int(mns))*60
        timeStr = "%02d:%02d" % (mns, scs)
    return timeStr

def adjustCBPdata(candleData, chart, t):
    # Coinbase doesn't update in realtime (every 3-5 minutes)
    if candleData[-1][0][0] < t:
        candleData[-1][0][5] = 0
        # Update (up to) last 5 candles that may not have been updated
        past = int(300 / granularity) + 1
        if len(candleData[-1]) >= past:
            for i in range(past):
                # calculate the difference in time intervals
                diff = int((t - candleData[-1][i][0]) / granularity)
                if chart.currInt >= diff: # must check in case candleData time is 0
                    idx = chart.currInt - diff
                    # for each candle, subtract the old vol and add the updated value
                    for j in range(numEx-1):
                        vol0,temp = chart.volumeChart.getVolBar(idx,ex=j)
                        vol1,temp = chart.volumeChart.getVolBar(idx,ex=-1)
                        chart.volumeChart.setVol(j, idx, vol0 - vol1 + candleData[-1][i][5])
                    chart.volumeChart.setVol(-1,idx,candleData[-1][i][5])

def checkTimeInterval(t):
    t1 = time.time()
    if t1 - (t1%granularity) > t:
        if granularity == 604800:
            if t1 - (t%granularity) - 3*86400 > t:
                t1 += 86400*3
                t = t1 - (t1%granularity)- 3*86400
                #chart.incCurrIntvl()
        else:    
            t = t1 - (t1%granularity)
            #chart.incCurrIntvl()
    return t

def isCandleUpdated(ex, data):
    tnow = time.time()
    if data == None or\
        (ex != "coinbasepro" and\
        data[0][0] < (tnow - granularity) and\
        (tnow % granularity) > 30):
        return False
    else:
        return True

# ----- These functions are generally only run once ----- #
def filterDupes(data):
    filtered = []
    lastT = 0
    for d in data:
        if lastT == d[0]:
            continue
        lastT = d[0]
        filtered.append(d)
    return filtered

def adjustTimestamps(data, amt):
    for d in data:
        d[0] += amt
    return data

def correctData(data, ex, tnow):
    
    if ex == "binance":
        data = data[::-1] # binance returns old->new, so reverse it

    elif ex == "coinbasepro":
        # shift coinbasepro data until it's "up-to-date"
        while data[0][0] != tnow:
            data = [[data[0][0] + granularity, data[0][4], data[0][4], data[0][4], data[0][4], 0]] + data
        
    elif ex == "gemini":
        # gemini duplicates timestamps during downtime
        data = filterDupes(data)
        # gemini is based on EST
        if INTERVAL == "6h":
            dt = datetime.fromtimestamp(data[-1][0])
            if dt.hour == 6 or dt.hour == 18:
                data = adjustTimestamps(data,7200)
            else:
                data = adjustTimestamps(data,-14400)
        elif INTERVAL == "1d":
            data = adjustTimestamps(data, -14400)
            
    # okex is based on Hong Kong time
    elif ex == "okex":
        isdst = time.localtime().tm_isdst > 0
        if INTERVAL == "6h":
            dt = datetime.fromtimestamp(data[-1][0])
            if not isdst:
                dt += timedelta(hours=1)
            if dt.hour == 6 or dt.hour == 18:
                data = adjustTimestamps(data,7200)
            else:
                data = adjustTimestamps(data,-14400)
        elif INTERVAL == "12h":
            data = adjustTimestamps(data, -14400)
        elif INTERVAL == "1d":
            dt = datetime.today()
            if not isdst:
                dt += timedelta(hours=1)
            if dt.hour < 12:
                data = adjustTimestamps(data, 28800)
            else:
                data = adjustTimestamps(data, -57600)
                
    # shift data in case application was launched soon after new interval start
    if tnow - granularity <= data[0][0] < tnow:
        data = [[data[0][0] + granularity, data[0][4], data[0][4], data[0][4], data[0][4], 0]] + data
    return data

def loadInitData(chart, HISTORY, t):
    global candleData
    global numEx
    global exchanges
    global useCBP

    candleData = []
    failed = []
    histPlusEMAPd = HISTORY + chart.historyNeeded()#26 + 9 # account for EMA26 and SMA9 of the EMA26 and EMA12 for MACD
    for i in range(numEx):
        # retrieve history of candle data
        temp = api.getCandle(exchanges[i], INTERVAL, SYMBOL, histPlusEMAPd)

        # failed to retrieve data from a specific exchange
        if temp is None:
            failed.append(exchanges[i])
            continue

        # could not retrieve as much data as requested
        if len(temp) < histPlusEMAPd:
            print("WARNING: could only retrieve %d intervals of history for %s" % (len(temp), exchanges[i]))
            HISTORY -= histPlusEMAPd - len(temp)
            histPlusEMAPd = HISTORY + 26 + 9

        # Correct the retrieved data (typically timestamps) and add it to the candleData
        temp = correctData(temp, exchanges[i], t)     
        candleData.append(temp)
       
    lastBfx = time.time()

    # Remove any exchanges that we failed to retrieve data from
    for f in failed:
        exchanges.remove(f)
    useCBP = ("coinbasepro" in exchanges)
    numEx = len(exchanges)
       
    # Load history
    exDown = chart.loadHistory(candleData, HISTORY)
    if any(exDown):
        print("WARNING: The following exchanges were down for a period of time")
        for wasDown,ex in zip(exDown, exchanges):
            if wasDown:
                print("\t%s (%d)" % (ex, len(wasDown)))

def saveDefaultConfig(conf):
    writeout = ""
    for key in conf:
        value = conf[key]
        if isinstance(value, list):
            value = ",".join(value)
        if isinstance(value, bool):
            value = int(value)
        writeout += "%s=%s\n" % (key, str(value))
    writeout = writeout[:-1]
    with open("..\\Configs\\default.conf", 'w') as f:
        f.write(writeout)
            
def getDefaultConfig():
    conf = {}
    conflines = []
    defConf = DefaultConfig.params
    
    # check if config directory and default config exist, otherwise create them
    if not os.path.isdir("..\\Configs"):
        os.mkdir("..\\Configs")
    if not os.path.isfile("..\\Configs\\default.conf"):
        saveDefaultConfig(defConf)
        return defConf
            
    # read default config file
    with open("..\\Configs\\default.conf", 'r') as f:
        conflines = f.readlines()
    conflines = [x.replace("\n", "") for x in conflines]

    # load settings by key-value pairs
    for line in conflines:
        splitted = line.split('=')
        key = splitted[0]
        value = splitted[1] 
        if len(value) > 1:
            if value.isdigit(): value = int(value)
            elif ',' in value: value = value.split(',')
            conf[key] = value
        else:
            conf[key] = value == "1"

    # config file is old and may be out-of-date
    if "version" not in conf or conf["version"] != defConf["version"]:
        old = False
        conf["version"] = defConf["version"]
        for key in defConf:
            if key not in conf:
                old = True
                conf[key] = defConf[key]
        if old:
            print("WARNING: Config file does not match current version, auto-updating")
            saveDefaultConfig(conf)

    return conf

def main():
    global run
    global lastBfx
    global candleData
    global exchanges
    global numEx
    global HISTORY
    global rdy

    # ---------- PREPARE TRACKER ---------- #
    # Create chart object that controls all matplotlib related functionality
    chart = CandlestickChart(SYMBOL, CONF)
    chart.show(IS_FULLSCREEN, FIG_POS)

    # Most recent interval start time
    t = time.time()
    if granularity == 604800:   # weeks technically start/end on Thurs 00:00:00 UTC
        t += 86400*3            # add three days
    t -= (t%granularity)        # round down to the nearest interval start
    if granularity == 604800:
        t -= 86400*3            # subtract three days to get the nearest past Mon 00:00:00 UTC

    # Get some history and current candle to start
    loadInitData(chart, HISTORY, t)

    # Start separate thread for API calls (they're slow)
    print("Starting data retrieval thread...", end='')
    thrd = threading.Thread(target=retrieveData, args=())
    thrd.start()

    # ---------- START TRACKER ---------- #
    # Loop to constantly update the current time interval candle and volume bar
    while True:

        if chart.enableIdle and not rdy and not chart.active:
            time.sleep(0.01)
            continue
        else:
            rdy = False

        # check for new interval
        t1 = checkTimeInterval(t)
        if t != t1:
            t = t1
            chart.incCurrIntvl()

        if numEx == 0:
            print("No exchanges are available to communicate with. Quitting...")
            break

        # Adjust for CBP as needed
        if useCBP: adjustCBPdata(candleData, chart, t)

        # average price from all exchanges (should weight by volume?)
        price = sum([float(x[0][4]) for x in candleData]) / numEx

        # set chart title as "<Current Price> <Time interval> <Time left in candle>"
        timeLeft = secondsToString(t+granularity-time.time())
        chart.setTitle("$%.2f (%s - %s)" % (price, INTERVAL, timeLeft))

        # update all charts with the newest data
        chart.update(candleData)

        try:
            chart.refresh()
        except Exception as ex:
            if str(ex) != "Figure closed": print(ex)
            break

    # End data thread and join with main
    print("Ending data retrieval thread...", end='')
    run = False
    thrd.join()


if __name__ == "__main__":
    # ---------- Parse CL Args ---------- #
    print("Initializing...\n")
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interval", help="Time interval to track (exchange APIs only allow specific intervals)", required=False, default="NONE")
    parser.add_argument("-V", "--vol_breakdown", help="Use if volume bars should be broken down by exchange", action="store_true")
    parser.add_argument("-y", "--history", help="How many time intervals of history to load at start", required=False, type=int, default=100)
    parser.add_argument("-s", "--symbol", help="The ticker symbol of the coin you want to watch (defaults to BTC)", required=False, default="BTC")
    parser.add_argument("--idle", help="Update the chart much less often", action="store_true")
    parser.add_argument("--fullscreen", help="Launch the application in fullscreen mode", action="store_true")
    args = vars(parser.parse_args())


    # CONTROL PARAMETERS
    VOL_BREAK_DOWN = args["vol_breakdown"]  # Breakdown volume by exchange
    INTERVAL = args["interval"]             # Time interval to watch
    HISTORY = args["history"]               # amount of history to load at start
    SYMBOL = args["symbol"].upper()         # the ticker symbol of the asset being tracked
    IS_IDLE = args["idle"]                  # chart only updates when get new data for all exchanges OR user is active on the GUI
    IS_FULLSCREEN = args["fullscreen"]
    
    # Load default parameters
    CONF = getDefaultConfig()
    if INTERVAL == "NONE":
        INTERVAL = CONF["timeFrame"]
    else:
        CONF["timeFrame"] = INTERVAL
    if not VOL_BREAK_DOWN:
        VOL_BREAK_DOWN = CONF["showVolBreakdown"]
    else:
        CONF["showVolBreakdown"] = True
    if not IS_IDLE:
        IS_IDLE = CONF["enableIdle"]
    else:
        CONF["enableIdle"] = True
    
    exchanges = ["binance", "okex", "bitfinex", "gemini", "coinbasepro"] # Binance must be first, CBP must be last
    numEx = len(exchanges)
    granularity = api.granFromInterv(INTERVAL)
    CONF["legend"] = ["Binance", "OKEx", "Bitfinex", "Gemini", "CoinbasePro"]   
    
    # --- arg checks --- #
    if IS_FULLSCREEN:
        user32 = ctypes.windll.user32
        if user32.GetSystemMetrics(78) > user32.GetSystemMetrics(0):
            FIG_POS = user32.GetSystemMetrics(0)+1
        else:
            FIG_POS = 0
    else:
        FIG_POS = 0
    if (HISTORY > 1405):
        print("WARNING: Cannot retrieve more than 1405 intervals of history")
        HISTORY = 1405

    if not api.validInterval("binance", INTERVAL):
        print("WARNING: %s is not a valid interval" % INTERVAL)
        print("\tDefaulting to %s" % CONF["timeFrame"])
        INTERVAL = CONF["timeFrame"]
        granularity = api.granFromInterv(INTERVAL)
        
    tempEx = exchanges[:]
    for ex in tempEx:
        if not api.validInterval(ex, INTERVAL):
            print("WARNING: %s is not a valid interval for the exchange %s" % (INTERVAL, ex))
            print("\tThis exchange will not be included in tracking")
            del CONF["legend"][exchanges.index(ex)]
            exchanges.remove(ex)
            numEx -= 1
        elif not api.isValidSymbol(ex, SYMBOL):
            print("WARNING: %s cannot be traded for USD or USDT on %s" % (SYMBOL, ex))
            print("\tThis exchange will not be included in tracking")
            del CONF["legend"][exchanges.index(ex)]
            exchanges.remove(ex)
            numEx -= 1
            
    useCBP = ("coinbasepro" in exchanges)
    if numEx == 0:
        print("ERROR: No exchanges are available to communicate with. Quitting...")
        exit()


    # ---------- 24hr ---------- #
    bfxStats = api.getDailyVol("bitfinex",SYMBOL)
    #stampStats = api.getDailyVol("bitstamp")
    binStats = api.getDailyVol("binance", SYMBOL)
    cbpStats = api.getDailyVol("coinbasepro", SYMBOL)
    gemStats = api.getDailyVol("gemini", SYMBOL)
    okStats = api.getDailyVol("okex", SYMBOL)

    totVol = 0
    if bfxStats != None:
        bfxVol = float(bfxStats[0]["volume"])
        totVol += bfxVol
    #totVol += float(stampStats["volume"])
    if binStats != None:
        binVol = float(binStats["volume"])
        totVol += binVol
    if cbpStats != None:
        cbpVol = float(cbpStats["volume"])
        totVol += cbpVol
    if gemStats != None:
        gemVol = float(gemStats["volume"][SYMBOL])
        totVol += gemVol
    if okStats != None:
        okVol = float(okStats["base_volume_24h"])
        totVol += okVol

    # ---------- Print info ---------- #
    print("\nTracking %sUSD on %d exchanges on the %s interval" % (SYMBOL, numEx, INTERVAL))
    print("Data sources: ", exchanges)
    print("Break down volume bars by exchange: %s" % str(VOL_BREAK_DOWN))
    print("24 hour volume: %f %s" % (totVol, SYMBOL))
    if bfxStats != None: print("\tBitfinex: %d (%.1f%%)" % (bfxVol, bfxVol / totVol * 100))
    if binStats != None: print("\tBinance: %d (%.1f%%)" % (binVol, binVol / totVol * 100))
    if cbpStats != None: print("\tCoinbasePro: %d (%.1f%%)" % (cbpVol, cbpVol / totVol * 100))
    if gemStats != None: print("\tGemini: %d (%.1f%%)" % (gemVol, gemVol / totVol * 100))
    if okStats != None: print("\tOKEx: %d (%.1f%%)" % (okVol, okVol / totVol * 100))

    # global variable used between threads
    run = True              # flag for running data retreival thread
    lastBfx = 0             # finex has a lower rate limit, keep track of last call
    candleData = []         # TOHLCV candlestick data for each exchange
    cbpPrice = {"price":0}  # keep track of real-time CBP price - candlestick API doesn't update as often
    rdy = False
    
    main()
