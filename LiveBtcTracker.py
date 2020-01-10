import time
import threading
import argparse
from datetime import datetime

from CandlestickChart import CandlestickChart
import BTC_API as api

def retrieveData():
    global lastBfx
    global run
    global cbpPrice
    global exchanges
    global numEx
    global candleData

    failures = [0]*numEx
    if run: print("success")
    else: print("failed")
    
    while run:
        ti = time.time()
        
        # Get candle data from each exchange
        if useCBP: cbpPrice = api.liveTicker("coinbasepro")
        for i in range(numEx):
            # bitfinex api is rate limited to every 3 seconds
            if exchanges[i] == "bitfinex" and time.time() - lastBfx < 3:
                continue
            temp = api.getCandle(exchanges[i], interval)
            if temp is None:
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
            
        tf = time.time()
        time.sleep(max(0.01, 1-(tf-ti)))
    print("ended")

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
            data = [[data[0][0] + granularity, 0, 0, 0, 0, 0]] + data
        
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
        if interval == "6h":
            dt = datetime.fromtimestamp(data[-1][0])
            if dt.hour == 6 or dt.hour == 18:
                data = adjustTimestamps(data,7200)
            else:
                data = adjustTimestamps(data,-14400)
        elif interval == "12h":
            data = adjustTimestamps(data, -14400)
        elif interval == "1d":
            dt = datetime.today()
            if dt.hour < 12:
                data = adjustTimestamps(data, 28800)
            else:
                data = adjustTimestamps(data, -57600)

    return data

def main():
    global run
    global lastBfx
    global candleData
    global exchanges
    global numEx
    global hist
    
    # Create chart object that controls all matplotlib related functionality
    chart = CandlestickChart(useCBP=useCBP)
    chart.setVolBreakdown(volBrkDwn)
    chart.show()

    # Most recent interval start time
    t = time.time()
    t -= (t%granularity)

    # Get some history and current candle to start
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
    numEx = len(exchanges)
       
    # Load history
    exDown = chart.loadHistory(candleData, hist)
    if any(exDown):
        print("WARNING: The following exchanges were down for a period of time")
        for wasDown,ex in zip(exDown, exchanges):
            if wasDown:
                print("\t%s" % ex)

    # For some reason, can only show legend AFTER plotting something
    chart.setVolumeLegend(legend)

    # Mark the highest and lowest prices levels in the current window
    maxHi = chart.getHighestPrice()
    minLo = chart.getLowestPrice()

    # Start separate thread for API calls (they're slow)
    print("Starting data retrieval thread...", end='')
    thrd = threading.Thread(target=retrieveData, args=())
    thrd.start()

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
                past = int(granularity / 300) + 1
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
        

        # average price from all exchanges (should weight by volume?)
        # cbp candles don't update in realtime but ticker does
        if useCBP:
            price = sum([float(x[0][4]) for x in candleData[:-1]])
            price = (price + float(cbpPrice["price"])) / numEx
        else:
            price = sum([float(x[0][4]) for x in candleData]) / numEx
        chart.setTitle("$%.2f (%s)" % (price, interval))

        # update all charts with the newest data
        chart.update(candleData)     
        
        # Mark highest and lowest wicks
        # TODO: this doesn't actually work anymore with shifting windows
        tempHi = chart.getHighestPrice()
        tempLo = chart.getLowestPrice()
        if tempHi > maxHi:
            chart.updateHiLevel()
            maxHi = tempHi
        if tempLo < minLo:
            chart.updateLoLevel()
            minLo = tempLo

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
    #parser.add_argument("-y", "--history", help="How many time intervals of history to load at start (must be less than num_intervals)", required=False, type=int, default=8)
    args = vars(parser.parse_args())


    # CONTROL PARAMETERS
    volBrkDwn = args["vol_breakdown"]   # Breakdown volume by exchange
    interval = args["interval"]         # Time interval to watch
    hist = 100
    
    exchanges = ["binance", "okex", "bitfinex", "gemini", "coinbasepro"] # Binance must be first, CBP must be last
    numEx = len(exchanges)
    granularity = api.granFromInterv(interval)
    legend = ["Binance", "OKEx", "Bitfinex", "Gemini", "CoinbasePro"]

    # arg checks
    #if (hist > 200):
    #    print("WARNING: Preloading history is limited to 200 intervals")
    #    hist = 200
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
    totVol += float(bfxStats[0]["volume"])
    #totVol += float(stampStats["volume"])
    totVol += float(binStats["volume"])
    totVol += float(cbpStats["volume"])
    totVol += float(gemStats["volume"]["BTC"])
    totVol += float(okStats["base_volume_24h"])

    # ---------- Print info ---------- #
    print("Tracking %d exchanges on the %s interval" % (numEx, interval))
    print("Data sources: ", exchanges)
    print("Break down volume bars by exchange: %s" % str(volBrkDwn))
    print("24 hour volume: %f BTC" % totVol)
    print("\tBitfinex: %d" % float(bfxStats[0]["volume"]))
    print("\tBinance: %d" % float(binStats["volume"]))
    print("\tCoinbasePro: %d" % float(cbpStats["volume"]))
    print("\tGemini: %d" % float(gemStats["volume"]["BTC"]))
    print("\tOKEx: %d" % float(okStats["base_volume_24h"]))

    # global variable used between threads
    run = True
    lastBfx = 0
    candleData = []
    cbpPrice = {"price":0}
    main()

    print("Done.")
