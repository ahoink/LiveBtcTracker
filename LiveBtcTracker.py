import time
import threading
import argparse
from datetime import datetime, timedelta

from CandlestickChart import CandlestickChart
import BTC_API as api

def retrieveData():
    global lastBfx
    global cbpPrice
    global exchanges
    global numEx
    global candleData
    global useCBP

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
            if temp == None or (exchanges[i] != "coinbasepro" and temp[0][0] < (time.time() - granularity) and (time.time() % granularity) > 10):
                failures[i] += 1
                if failures[i] == 3:
                    print("Stopping requests to %s (Restart to try again)" % exchanges[i])
                temp = [0]*6
            else:
                failures[i] = 0
                if exchanges[i] == "coinbasepro":
                    candleData[i][0][2] = max(candleData[i][0][2], float(cbpPrice["price"]))
                    candleData[i][0][3] = min(candleData[i][0][3], float(cbpPrice["price"]))
                    candleData[i][0][4] = float(cbpPrice["price"])
                else:
                    candleData[i] = temp
                             
        # Check if any exchange failed three times in a row
        if 3 in failures:
            exchanges = [ex for ex,f in zip(exchanges, failures) if f < 3]
            candleData = [d for d,f in zip(candleData, failures) if f < 3]
            failures = [f for f in failures if f < 3]  
            numEx = len(exchanges)
            useCBP = ("coinbasepro" in exchanges)

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
                        chart.setVol(j, idx, chart.getVol(j,idx) - chart.getVol(-1,idx) + candleData[-1][i][5])
                    chart.setVol(-1,idx,candleData[-1][i][5])

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
    histPlusEMAPd = HISTORY + 26 + 9 # account for EMA26 and SMA9 of the EMA26 and EMA12 for MACD
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

def main():
    global run
    global lastBfx
    global candleData
    global exchanges
    global numEx
    global HISTORY

    # ---------- PREPARE TRACKER ---------- #
    # Create chart object that controls all matplotlib related functionality
    chart = CandlestickChart(useCBP, SYMBOL, "MACD", "RSI", "OBV")
    chart.setVolBreakdown(VOL_BREAK_DOWN)
    chart.show()

    # Most recent interval start time
    t = time.time()
    if granularity == 604800:   # weeks technically start/end on Thurs 00:00:00 UTC
        t += 86400*3            # add three days
    t -= (t%granularity)        # round down to the nearest interval start
    if granularity == 604800:
        t -= 86400*3            # subtract three days to get the nearest past Mon 00:00:00 UTC

    # Get some history and current candle to start
    loadInitData(chart, HISTORY, t)

    # For some reason, can only show legend AFTER plotting something
    chart.setVolumeLegend(legend)

    # Start separate thread for API calls (they're slow)
    print("Starting data retrieval thread...", end='')
    thrd = threading.Thread(target=retrieveData, args=())
    thrd.start()

    # ---------- START TRACKER ---------- #
    # Loop to constantly update the current time interval candle and volume bar
    while True:

        # check for new interval
        t1 = checkTimeInterval(t)
        if t != t1:
            t = t1
            chart.incCurrIntvl()

        # Adjust for CBP as needed
        if useCBP: adjustCBPdata(candleData, chart, t)
        elif chart.useCBP: chart.useCBP = False

        # average price from all exchanges (should weight by volume?)
        price = sum([float(x[0][4]) for x in candleData]) / numEx

        # set chart title as "<Current Price> <Time interval> <Time left in candle>"
        timeLeft = secondsToString(t+granularity-time.time())
        chart.setTitle("$%.2f (%s - %s)" % (price, INTERVAL, timeLeft))

        # update all charts with the newest data
        chart.update(candleData)

        try:
            chart.refresh()
        except:
            break

    # End data thread and join with main
    print("Ending data retrieval thread...", end='')
    run = False
    thrd.join()


if __name__ == "__main__":
    # ---------- Parse CL Args ---------- #
    print("Initializing...\n")
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interval", help="Time interval to track (exchange APIs only allow specific intervals)", required=False, default="1h")
    parser.add_argument("-V", "--vol_breakdown", help="Use if volume bars should be broken down by exchange", action="store_true")
    parser.add_argument("-y", "--history", help="How many time intervals of history to load at start", required=False, type=int, default=100)
    parser.add_argument("-s", "--symbol", help="The ticker symbol of the coin you want to watch (defaults to BTC)", required=False, default="BTC")
    #parser.add_argument("--idle", help="Update the chart much less often", action="store_true")
    args = vars(parser.parse_args())


    # CONTROL PARAMETERS
    VOL_BREAK_DOWN = args["vol_breakdown"]  # Breakdown volume by exchange
    INTERVAL = args["interval"]             # Time interval to watch
    HISTORY = args["history"]               # amount of history to load at start
    SYMBOL = args["symbol"].upper()         # the ticker symbol of the asset being tracked
    #isIdle = args["idle"]
    
    exchanges = ["binance", "okex", "bitfinex", "gemini", "coinbasepro"] # Binance must be first, CBP must be last
    numEx = len(exchanges)
    granularity = api.granFromInterv(INTERVAL)
    legend = ["Binance", "OKEx", "Bitfinex", "Gemini", "CoinbasePro"]

    # --- arg checks --- #
    if (HISTORY > 1405):
        print("WARNING: Cannot retrieve more than 1405 intervals of history")
        HISTORY = 1405

    if not api.validInterval("binance", INTERVAL):
        print("WARNING: %s is not a valid interval" % INTERVAL)
        print("\tDefaulting to 1h")
        INTERVAL="1h"
        granularity = 3600
    tempEx = exchanges[:]
    for ex in tempEx:
        if not api.validInterval(ex, INTERVAL):
            print("WARNING: %s is not a valid interval for the exchange %s" % (INTERVAL, ex))
            print("\tThis exchange will not be included in tracking")
            del legend[exchanges.index(ex)]
            exchanges.remove(ex)
            numEx -= 1
        elif ex == "bitfinex" and INTERVAL == "1w":
            print("INFO: 1w is a valid interval for bitfinex but will not be included in tracking")
            del legend[exchanges.index(ex)]
            exchanges.remove(ex)
            numEx -=1

        elif not api.isValidSymbol(ex, SYMBOL):
            print("WARNING: %s cannot be traded for USD or USDT on %s" % (SYMBOL, ex))
            print("\tThis exchange will not be included in tracking")
            del legend[exchanges.index(ex)]
            exchanges.remove(ex)
            numEx -= 1
            
    useCBP = ("coinbasepro" in exchanges)


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
    main()

    print("Done.")
