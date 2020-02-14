import time
import threading
import argparse
from datetime import datetime, timedelta

from CandlestickChart import CandlestickChart
import BTC_API as api

def retrieveData():
    global lastBfx
    global run
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

        # Get candle data from each exchange
        if useCBP:
            cbpPrice = api.liveTicker("coinbasepro")
            if cbpPrice == None:
                cbpPrice = {"price":0}
                failures[-1] += 1
        for i in range(numEx):
            # bitfinex api is rate limited to every 3 seconds
            if (exchanges[i] == "bitfinex" and time.time() - lastBfx < 3):
                continue
            temp = api.getCandle(exchanges[i], interval)
            if temp == None:
                failures[i] += 1
                if failures[i] == 3:
                    print("Stopping requests to %s (Restart to try again)" % exchanges[i])
                temp = [0]*6
            else:
                failures[i] = 0
                candleData[i] = temp
            if exchanges[i] == "bitfinex": lastBfx = time.time()

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

    # shift data in case application was launched soon after new interval start
    if data[0][0] < tnow:
        data = [[data[0][0] + granularity, data[0][4], data[0][4], data[0][4], data[0][4], 0]] + data
    
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
        if interval == "6h":
            dt = datetime.fromtimestamp(data[-1][0])
            if dt.hour == 6 or dt.hour == 18:
                data = adjustTimestamps(data,7200)
            else:
                data = adjustTimestamps(data,-14400)
        elif interval == "1d":
            data = adjustTimestamps(data, -14400)
            
    # okex is based on Hong Kong time
    elif ex == "okex":
        isdst = time.localtime().tm_isdst > 0
        if interval == "6h":
            dt = datetime.fromtimestamp(data[-1][0])
            if not isdst:
                dt += timedelta(hours=1)
            if dt.hour == 6 or dt.hour == 18:
                data = adjustTimestamps(data,7200)
            else:
                data = adjustTimestamps(data,-14400)
        elif interval == "12h":
            data = adjustTimestamps(data, -14400)
        elif interval == "1d":
            dt = datetime.today()
            if not isdst:
                dt += timedelta(hours=1)
            if dt.hour < 12:
                data = adjustTimestamps(data, 28800)
            else:
                data = adjustTimestamps(data, -57600)

    return data

def loadInitData(chart, hist, t):
    global candleData
    global numEx
    global exchanges
    global useCBP

    candleData = []
    failed = []
    histPlusEMAPd = hist + 26 + 9
    for i in range(numEx):
        temp = api.getCandle(exchanges[i], interval, histPlusEMAPd)
        if temp is None:
            failed.append(exchanges[i])
            continue
        if len(temp) < histPlusEMAPd:
            print("WARNING: could only retrieve %d intervals of history for %s" % (len(temp), exchanges[i]))
            hist -= histPlusEMAPd - len(temp)
            histPlusEMAPd = hist + 26 + 9
        temp = correctData(temp, exchanges[i], t)
        candleData.append(temp)
    lastBfx = time.time()
    for f in failed:
        exchanges.remove(f)
    useCBP = ("coinbasepro" in exchanges)
    numEx = len(exchanges)
       
    # Load history
    exDown = chart.loadHistory(candleData, hist)
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
    global hist

    # ---------- PREPARE TRACKER ---------- #
    # Create chart object that controls all matplotlib related functionality
    chart = CandlestickChart(useCBP, "MACD", "RSI")
    chart.setVolBreakdown(volBrkDwn)
    chart.show()

    # Most recent interval start time
    t = time.time()
    t -= (t%granularity)

    # Get some history and current candle to start
    loadInitData(chart, hist, t)

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
        t1 = time.time()
        if t1 - (t1%granularity) > t:
            t = t1 - (t1%granularity)
            chart.incCurrIntvl()

        # Coinbase doesn't update in realtime (every 3-5 minutes)
        if useCBP:
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
            #else:
            if float(cbpPrice["price"]) != 0:
                candleData[-1][0][4] =  float(cbpPrice["price"])
        elif chart.useCBP: chart.useCBP = False


        # average price from all exchanges (should weight by volume?)
        # cbp candles don't update in realtime but ticker does
        if useCBP:
            price = sum([float(x[0][4]) for x in candleData[:-1]])
            price = (price + float(cbpPrice["price"])) / numEx
        else:
            price = sum([float(x[0][4]) for x in candleData]) / numEx

        timeLeft = secondsToString(t+granularity-t1)
        chart.setTitle("$%.2f (%s - %s)" % (price, interval, timeLeft))

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
    #parser.add_argument("--idle", help="Update the chart much less often", action="store_true")
    args = vars(parser.parse_args())


    # CONTROL PARAMETERS
    volBrkDwn = args["vol_breakdown"]   # Breakdown volume by exchange
    interval = args["interval"]         # Time interval to watch
    hist = args["history"]              # amount of history to load at start
    #isIdle = args["idle"]
    
    exchanges = ["binance", "okex", "bitfinex", "gemini", "coinbasepro"] # Binance must be first, CBP must be last
    numEx = len(exchanges)
    granularity = api.granFromInterv(interval)
    legend = ["Binance", "OKEx", "Bitfinex", "Gemini", "CoinbasePro"]

    # arg checks
    if (hist > 1405):
        print("WARNING: Cannot retrieve more than 1405 intervals of history")
        hist = 1405

    if not api.validInterval("binance", interval):
        print("WARNING: %s is not a valid interval" % interval)
        print("\tDefaulting to 1h")
        interval="1h"
        granularity = 3600
    tempEx = exchanges[:]
    for ex in tempEx:
        if not api.validInterval(ex, interval):
            print("WARNING: %s is not a valid interval for the exchange %s" % (interval, ex))
            print("\tThis exchange will not be included in tracking")
            del legend[exchanges.index(ex)]
            exchanges.remove(ex)
            numEx -= 1
        elif ex == "bitfinex" and interval == "1w":
            print("INFO: 1w is a valid interval for bitfinex but will not be included in tracking")
            del legend[exchanges.index(ex)]
            exchanges.remove(ex)
            numEx -=1
    useCBP = ("coinbasepro" in exchanges)


    # ---------- 24hr ---------- #
    bfxStats = api.getDailyVol("bitfinex")
    #stampStats = api.getDailyVol("bitstamp")
    binStats = api.getDailyVol("binance")
    cbpStats = api.getDailyVol("coinbasepro")
    gemStats = api.getDailyVol("gemini")
    okStats = api.getDailyVol("okex")

    totVol = 0
    if bfxStats != None: totVol += float(bfxStats[0]["volume"])
    #totVol += float(stampStats["volume"])
    if binStats != None: totVol += float(binStats["volume"])
    if cbpStats != None: totVol += float(cbpStats["volume"])
    if gemStats != None: totVol += float(gemStats["volume"]["BTC"])
    if okStats != None: totVol += float(okStats["base_volume_24h"])

    # ---------- Print info ---------- #
    print("Tracking %d exchanges on the %s interval" % (numEx, interval))
    print("Data sources: ", exchanges)
    print("Break down volume bars by exchange: %s" % str(volBrkDwn))
    print("24 hour volume: %f BTC" % totVol)
    if bfxStats != None: print("\tBitfinex: %d" % float(bfxStats[0]["volume"]))
    if binStats != None: print("\tBinance: %d" % float(binStats["volume"]))
    if cbpStats != None: print("\tCoinbasePro: %d" % float(cbpStats["volume"]))
    if gemStats != None: print("\tGemini: %d" % float(gemStats["volume"]["BTC"]))
    if okStats != None: print("\tOKEx: %d" % float(okStats["base_volume_24h"]))

    # global variable used between threads
    run = True              # flag for running data retreival thread
    lastBfx = 0             # finex has a lower rate limit, keep track of last call
    candleData = []         # TOHLCV candlestick data for each exchange
    cbpPrice = {"price":0}  # keep track of real-time CBP price - candlestick API doesn't update as often

    main()

    print("Done.")
