import time
import warnings

# Hide MatplotlibDeprecationWarning
warnings.filterwarnings("ignore",".*GUI is implemented.*")
warnings.filterwarnings("ignore",".*mpl_finance*")
import matplotlib.pyplot as plt
from matplotlib.finance import candlestick_ohlc as candle
from matplotlib.widgets import Cursor
import matplotlib.lines as mlines
import matplotlib.patches as mpatches

class CandlestickChart():

    def __init__(self, numIntervals, numPlots=3, useCBP=True):
        self.fig, self.axes = plt.subplots(numPlots,1, sharex=True)
        self.fig.set_size_inches(6, 6)
        plt.subplots_adjust(top=0.95, bottom=0.05, wspace=0, hspace=0.01)
        self.axes[0].title.set_text("Loading...")

        # Cursor
        self.cursor = mlines.Line2D([-1, -1], [0, 100000], linewidth=1, color="#6e6e6e")
        self.cursor1 = mlines.Line2D([-1, -1], [0, 100000], linewidth=1, color="#6e6e6e")
        self.axes[0].add_line(self.cursor)
        self.axes[1].add_line(self.cursor1)
        self.fig.canvas.mpl_connect("motion_notify_event", self._mouseMove)
        self.fig.canvas.mpl_connect("axes_enter_event", self._mouseEnter)
        self.fig.canvas.mpl_connect("axes_leave_event", self._mouseLeave)
        self.cursorText0 = self.axes[0].text(-0.75, 0, "", fontsize=8, color="#cecece")
        self.cursorText1 = self.axes[1].text(-0.75, 0, "", fontsize=8, color="#cecece")
        self.cursorOn = False
        
        # volume vars
        self.volBars = []
        self.vol = []
        self.volRatio = []
        self.volRatioText = None
        self.buyEma = []
        self.sellEma = []
        self.volEmaPd = 10
        self.volEmaWt = 2 / (self.volEmaPd+1)
        self.buyEmaPlt = None
        self.sellEmaPlt = None
        self.showVolBreakdown = False
        self.legend = []

        # price vars
        self.candlesticks = ([],[])
        self.ohlc = []
        self.hiLine = None
        self.hiText = None
        self.loLine = None
        self.loText = None

        # MACD vars
        self.macdBars = []
        self.macd = []
        self.ema26 = 0
        self.ema12 = 0
        self.ema9 = 0
        self.ema26Wt = 2 / (26+1)
        self.ema12Wt = 2 / (12+1)
        self.ema9Wt = 2 / (9+1)

        # misc vars
        self.numInts = numIntervals
        self.currInt = 0
        self.green = "#22d615"
        self.red = "#ea2222"
        self.blue = "#5087fa"
        self.loaded = False
        self.useCBP = useCBP
        self._lastRefresh = time.time() 

        # volume default attributes
        self.axes[1].set_ylabel("Volume (BTC)")
        self.axes[1].set_facecolor("#1e1e1e")
        self.axes[1].set_xlim([-1, self.numInts+1])

        # price default attributes
        self.axes[0].set_ylabel("Price (USD)")
        self.axes[0].yaxis.grid(which="major", linestyle="--", color="#5e5e5e")
        self.axes[0].set_axisbelow(True)
        self.axes[0].set_facecolor("#1e1e1e")
        self.axes[0].set_xticklabels([])

        # MACD default attributes
        self.axes[2].set_facecolor("#1e1e1e")
        self.axes[2].set_ylabel("MACD (12, 26, 9)")

    # ----- Private Functions ----- #
    def _initHiLoLevels(self):
        maxHi = self.getHighestPrice()
        self.hiLine, = self.axes[0].plot([-1, self.numInts+1],
                                  [maxHi, maxHi],
                                  linestyle="--",
                                  color=self.green,
                                  linewidth=0.5)
        self.hiText = self.axes[0].text(self.numInts + 1.1,
                                   maxHi,
                                   "%.2f" % maxHi,
                                   fontsize=9)
        
        minLo = self.getLowestPrice()
        self.loLine, = self.axes[0].plot([-1, self.numInts+1],
                                  [minLo, minLo],
                                  linestyle="--",
                                  color=self.red,
                                  linewidth=0.5)
        self.loText = self.axes[0].text(self.numInts + 1.1,
                                   minLo,
                                   "%.2f" % minLo,
                                   fontsize=9)

    def _shiftIntervals(self):
        if not self.loaded: return

        numEx = len(self.vol)
        for i in range(numEx):
            self.vol[i] = self.vol[i][1:] + [0]
        self.macd = self.macd[1:] + [0]
        self.volRatio = self.volRatio[1:] + [0]
        self.buyEma = self.buyEma[1:] + [0]
        self.sellEma = self.sellEma[1:] + [0]
        self.ohlc = self.ohlc[1:]
        self.ohlc.append([0]*5)
        self.candlesticks[0][0].remove()
        self.candlesticks[1][0].remove()
        self.candlesticks = (self.candlesticks[0][1:], self.candlesticks[1][1:])
        self.createCandlestick()
        
        for i in range(self.numInts):
            self.ohlc[i][0] = i
            self.candlesticks[0][i].set_xdata([i, i])
            self.candlesticks[1][i].set_x(i - 0.25)

    def _mouseEnter(self, event):
        self.cursorOn = True

    def _mouseLeave(self, event):
        self.cursorOn = False
        self.cursorText0.set_text("")
        self.cursorText1.set_text("")
        self.cursor.set_xdata([-1, -1])
        self.cursor1.set_xdata([-1, -1])
    
    def _mouseMove(self, event):
        if self.cursorOn and self.loaded:
            x = int(round(event.xdata))
            if 0 <= x <= self.currInt:
                cx = x
            else:
                cx = event.xdata
            self.cursor.set_xdata([cx, cx])
            self.cursor1.set_xdata([cx, cx])
            self.cursor1.set_ydata([0, max(self.vol[0])*1.1])
            if 0 <= x <= self.currInt:
                self.cursorText0.set_text(
                    "Open: %.2f, High: %.2f, Low: %.2f, Close: %.2f" %
                    (self.ohlc[x][1], self.ohlc[x][2], self.ohlc[x][3], self.ohlc[x][4]))
                self.cursorText0.set_y(
                    self.getHighestPrice() + (self.getHighestPrice() - self.getLowestPrice()) * 0.04)

                self.cursorText1.set_text("Volume: %.8f (%.1f%% Buys)" % (self.vol[0][x], self.volRatio[x]*100))
                self.cursorText1.set_y(max(self.vol[0]))
            else:
                self.cursorText0.set_text("")
                self.cursorText1.set_text("")
        
        


    # ----- MPL Figure attribute functions ----- #
    def setVolBreakdown(self, show):
        if show:
            self.setVolumeLegend(self.legend)
        elif self.showVolBreakdown:
            self.axes[1].get_legend().remove()
        self.showVolBreakdown = show

    def setVolumeLegend(self, legend):
        self.legend = legend
        if self.showVolBreakdown:
            self.axes[1].legend(self.volBars, legend)

    def setTitle(self, title):
        try:
            self.axes[0].title.set_text(title)
        except:
            print("Could not update title")


    # ----- Everything Else ----- #
    def loadHistory(self, data, histCnt):
        numEx = len(data)

        # initialize vol and bar lists
        for i in range(numEx):
            self.vol.append([0]*self.numInts)
            if self.showVolBreakdown or i == 0:
                self.volBars.append(self.axes[1].bar(
                    range(self.numInts),
                    self.vol[i],
                    linewidth=0.7))
        for bar in self.volBars[0]:
            bar.set_linewidth(1)
        self.volRatio = [0]*self.numInts
        self.buyEma = [0]
        self.sellEma = [0]

        # initialize macd
        self.macd = [0]*self.numInts
        self.macdBars = self.axes[2].bar(range(self.numInts), self.macd)

        # calc EMA from history
        #   price ema12 and ema26
        #   macd signal ema9
        #   volume emaX (x specified in __init__)
        self.calcEMAfromHist(data, histCnt)

        exDown = [False]*numEx
        # traverse history from old to new data
        for i in range(histCnt):
            # candle data is sorted new->old
            # so index in reverse order
            idx = histCnt-1-i

            # Check timestamps to see if an exchange was down during that time
            invalid = []
            avgT = sum([x[idx][0] for x in data]) / numEx
            for j in range(numEx):
                if data[j][idx][0] < avgT:
                    invalid.append(data[j])
                    exDown[j] = True
            #invalid = [x for x in data if x[idx][0] < avgT]

            # sum volume from all exchanges
            for j in range(numEx):           
                self.vol[j][i] = sum([float(x[idx][5]) for x in data[j:] if x not in invalid])

            # calc buy volume percentage
            if len(data[0][0]) < 10 or data[0] in invalid:
                self.volRatio[i] = 0.5
            else:
                self.volRatio[i] = (float(data[0][idx][9]) / float(data[0][idx][5]))

            # update volume EMAs
            self.buyEma.append((self.volRatio[i] * self.vol[0][i]) * self.volEmaWt +\
                               self.buyEma[-1] * (1 - self.volEmaWt))
            self.sellEma.append(((1 - self.volRatio[i]) * self.vol[0][i]) * self.volEmaWt +\
                               self.sellEma[-1] * (1 - self.volEmaWt))
                    
            # append ohlc candle data (but ignore coinbase which may not be up-to-date)
            self.ohlc.append([i] + [0]*4)
            for j in range(1,5):
                if self.useCBP:
                    self.ohlc[i][j] =\
                    sum([float(x[idx][j]) for x in data[:-1] if x not in invalid]) /\
                    (len([x for x in data[:-1] if x not in invalid]))
                else:
                    self.ohlc[i][j] =\
                    sum([float(x[idx][j]) for x in data if x not in invalid]) /\
                    (len(data)-len(invalid))

            # update EMAs
            if idx == 0:
                continue
            self.ema26 = self.ohlc[i][4] * self.ema26Wt + self.ema26 * (1-self.ema26Wt)
            self.ema12 = self.ohlc[i][4] * self.ema12Wt + self.ema12 * (1-self.ema12Wt)
            self.ema9 = (self.ema12-self.ema26) * self.ema9Wt + self.ema9 * (1-self.ema9Wt)
            self.macd[i] = (self.ema12-self.ema26) - self.ema9

        self.currInt = histCnt - 1
        self.drawCandlesticks()
        self.drawVolBars(True)
        self.drawMACD(True)
        self.loaded = True
        return exDown

    def incCurrIntvl(self):
        self.updateMACD(retain=False)
        self.currInt += 1
        if self.currInt >= self.numInts:
            self.currInt = self.numInts -1
            self._shiftIntervals()
            self.drawVolBars(True)
            self.drawMACD(True)
            self.draw()
        else:
            self.ohlc.append([self.currInt] + [0]*4)
            self.createCandlestick()
            self.buyEma.append(0)
            self.sellEma.append(0)

    def getCurrIntvl(self):
        return self.currInt

    def calcEMAfromHist(self, data, histCnt):
        numEx = len(data)
        ema26Start = min(200, histCnt + 26+9)
        ema12Start = min(ema26Start - 14, histCnt + 12+9)
        emaVolStart = min(200, histCnt + self.volEmaPd)
        
        # First EMA value is a SMA
        # calculate SMA for first X intervals of emaX
        for i in range(26):
            # price ema26
            idx = ema26Start-1-i
            self.ema26 += sum([float(x[idx][4]) for x in data[:-1]]) / (numEx-1)
            # price ema12
            if i < 12:
                idx = ema12Start-1-i
                self.ema12 += sum([float(x[idx][4]) for x in data[:-1]]) / (numEx-1)
            # volume ema
            if i < self.volEmaPd:
                idx = emaVolStart-1-i
                totalVol = sum([float(x[idx][5]) for x in data[:-1]])
                if len(data[0][idx]) < 10:
                    self.buyEma[0] += totalVol * 0.5
                    self.sellEma[0] += totalVol * 0.5
                else:
                    self.buyEma[0] += totalVol * (float(data[0][idx][9]) / float(data[0][idx][5]))
                    self.sellEma[0] += totalVol * (1 - float(data[0][idx][9]) / float(data[0][idx][5]))
        self.ema26 /= 26
        self.ema12 /= 12
        self.ema9 += (self.ema12 - self.ema26)
        self.buyEma[0] /= self.volEmaPd
        self.sellEma[0] /= self.volEmaPd

        # calculate SMA9 of (ema12-ema26)
        for i in range(8,0,-1):
            idx = histCnt+i
            p = sum([float(x[idx][4]) for x in data[:-1]]) / (numEx-1)
            self.ema26 = p * self.ema26Wt + self.ema26 * (1 - self.ema26Wt)
            self.ema12 = p * self.ema12Wt + self.ema12 * (1 - self.ema12Wt)
            self.ema9 += (self.ema12 - self.ema26)
        self.ema9 /= 9

    # Volume related functions
    def setVol(self, ex, intvl, val):
        self.vol[ex][intvl] = val

    def getVol(self, ex, intvl):
        return self.vol[ex][intvl]
     
    def updateCurrentVol(self, data):
        numEx = len(data)
        # bar graph is stacked so each vol is the sum of all vols proceeding it
        # (i.e. vol[0] is sum of all exchanges, vol[-1] is the volume of a single exchange)
        for i in range(numEx):
            self.vol[i][self.currInt] = sum([float(x[0][5]) for x in data[i:]])
        if len(data[0][0]) < 10:
            self.volRatio[self.currInt] = 0.5
        else:
            self.volRatio[self.currInt] = (float(data[0][0][9]) / float(data[0][0][5]))

        self.buyEma[-1] = (self.volRatio[self.currInt] * self.vol[0][self.currInt]) * self.volEmaWt +\
                             self.buyEma[self.currInt] * (1 - self.volEmaWt)
        self.sellEma[-1] = ((1 - self.volRatio[self.currInt]) * self.vol[0][self.currInt]) * self.volEmaWt +\
                             self.sellEma[self.currInt] * (1 - self.volEmaWt)

        # Calculate the percentage of buys from total volume
        buyRat = 0
        for i in range(self.currInt + 1):
            buyRat += self.volRatio[i] * self.vol[0][i]
        buyRat /= sum([x for x in self.vol[0]])

        if self.volRatioText == None:
            self.volRatioText = self.axes[1].text(self.numInts*0.94,
                                                max(self.vol[0])*0.99,
                                                "%.1f%%" % buyRat,
                                                fontsize=9,
                                                color="#cecece")
        self.volRatioText.set_text("%.1f%%" % (buyRat * 100))
        self.volRatioText.set_position((self.numInts*0.94, max(self.vol[0])*0.99))
        
    def drawVolBars(self, updateColor=False):
        try:
            numEx = len(self.vol)
            for bar,v,r in zip(self.volBars[0], self.vol[0], self.volRatio):
                bar.set_height(v)
                # Highlight bars depending on the ratio of taker buys:sells
                # Binance is the only exchange that provides this info
                if updateColor or bar is self.volBars[0][self.currInt]:
                    if r > 0.5:
                        if self.showVolBreakdown:
                            bar.set_edgecolor(self.green)
                        else:
                            bar.set_color(self.green)
                    elif r < 0.5:
                        if self.showVolBreakdown:
                            bar.set_edgecolor(self.red)
                        else:
                            bar.set_color(self.red)
                    else:
                        if self.showVolBreakdown:
                            bar.set_edgecolor(self.blue)
                        else:
                            bar.set_color(self.blue)
                            
            if self.showVolBreakdown:
                for i in range(1, numEx):
                    for bar,v in zip(self.volBars[i], self.vol[i]):
                        bar.set_height(v)
                                         
            self.axes[1].set_ylim(0, max(self.vol[0])*1.06)

            # Draw EMA lines of buy and sell volume
            if self.buyEmaPlt == None:
                self.buyEmaPlt, = self.axes[1].plot(range(self.currInt + 1), self.buyEma[1:], "-", c="#3333ff", linewidth=0.9)
                self.sellEmaPlt, = self.axes[1].plot(range(self.currInt + 1), self.sellEma[1:], "-", c="yellow", linewidth=0.9)
            else:
                self.buyEmaPlt.set_data(range(self.currInt+1), self.buyEma[1:])
                self.sellEmaPlt.set_data(range(self.currInt+1), self.sellEma[1:])
        except:
           print("Could not draw volume chart")
            
    # MACD functions
    def updateMACD(self, retain=True):
        tempEMA26 = self.ohlc[self.currInt][4] * self.ema26Wt + self.ema26 * (1 - self.ema26Wt)
        tempEMA12 = self.ohlc[self.currInt][4] * self.ema12Wt + self.ema12 * (1 - self.ema12Wt)
        tempEMA9 = (tempEMA12 - tempEMA26) * self.ema9Wt + self.ema9 * (1 - self.ema9Wt)
        self.macd[self.currInt] = (tempEMA12 - tempEMA26) - tempEMA9

        if not retain:
            self.ema26 = tempEMA26
            self.ema12 = tempEMA12
            self.ema9 = tempEMA9
        
    def drawMACD(self, updateColor=False):
        try:
            for bar,v in zip(self.macdBars, self.macd):
                bar.set_height(v)
                if updateColor or bar is self.macdBars[self.currInt]:
                    if v < 0:
                        bar.set_color(self.red)
                    else:
                        bar.set_color(self.green)
                        
            buf = (max(self.macd) - min(self.macd)) * 0.12
            self.axes[2].set_ylim(min(0, min(self.macd) - buf), max(0, max(self.macd)+buf))
        except:
            print("Could not draw MACD")

    # Candle/Price related functions
    def updateCandlesticks(self, data):
        for i in range(1,5):
            if self.useCBP: self.ohlc[self.currInt][i] = sum([float(x[0][i]) for x in data[:-1]]) / (len(data)-1)
            else: self.ohlc[self.currInt][i] = sum([float(x[0][i]) for x in data]) / len(data)

    def createCandlestick(self):
        # create new candlestick and add it to the axis
        self.candlesticks[0].append(mlines.Line2D([self.currInt, self.currInt], [0, 0], linewidth=0.5))
        self.axes[0].add_line(self.candlesticks[0][-1])
        self.candlesticks[1].append(mpatches.Rectangle((self.currInt - 0.25, 0), width=0.5, height=0))
        self.axes[0].add_patch(self.candlesticks[1][-1])
        
    def drawCandlesticks(self):
        try:
            if self.candlesticks[0]:
                self.candlesticks[0][-1].set_ydata([self.ohlc[-1][2], self.ohlc[-1][3]])
                # open > close
                if self.ohlc[-1][1] > self.ohlc[-1][4]:
                    self.candlesticks[1][-1].set_y(self.ohlc[-1][4])
                    self.candlesticks[1][-1].set_height(self.ohlc[-1][1] - self.ohlc[-1][4])
                    self.candlesticks[1][-1].set_color(self.red)
                    self.candlesticks[0][-1].set_color(self.red)
                # open <= close
                else:
                    self.candlesticks[1][-1].set_y(self.ohlc[-1][1])
                    self.candlesticks[1][-1].set_height(self.ohlc[-1][4] - self.ohlc[-1][1])
                    self.candlesticks[1][-1].set_color(self.green)
                    self.candlesticks[0][-1].set_color(self.green)
            else:
                self.candlesticks = candle(self.axes[0], self.ohlc, width=0.5, colorup=self.green, colordown=self.red)
        except:
            print("Could not draw candlesticks")
            
    def getHighestPrice(self):
        return max([x[2] for x in self.ohlc])

    def getLowestPrice(self):
        return min([x[3] for x in self.ohlc])
    
    def updateHiLevel(self, hi):
        if self.hiLine == None or self.hiText == None:
            self._initHiLoLevels()
        else:
            self.hiLine.set_data([-1, self.numInts+1], [hi, hi])
            self.hiText.set_text("%.2f" % hi)
            self.hiText.set_position((self.numInts + 1.1, hi))
        buf = (hi - self.getLowestPrice()) * 0.12
        self.axes[0].set_ylim(self.axes[0].get_ylim()[0], hi + buf)
 
    def updateLoLevel(self, lo):
        if self.loLine == None or self.loText == None:
            self._initHiLoLevels()
        else:
            self.loLine.set_data([-1, self.numInts+1], [lo, lo])  
            self.loText.set_text("%.2f" % lo)
            self.loText.set_position((self.numInts + 1.1, lo))
        buf = (self.getHighestPrice() - lo) * 0.12
        self.axes[0].set_ylim(lo - buf, self.axes[0].get_ylim()[1])

    
    def show(self):
        plt.show(block=False)

    def draw(self):
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        self.show()
    
    def refresh(self):
        #self.fig.canvas.draw()
        #self.axes[0].draw_artist(self.candlesticks[0][-1])
        #self.axes[0].draw_artist(self.candlesticks[1][-1])
        #self.axes[0].draw_artist(self.cursor)
        #self.axes[1].draw_artist(self.volBars[0][-1])
        #self.axes[1].draw_artist(self.cursor1)
        #self.fig.canvas.blit(self.axes[0].bbox)
        #self.fig.canvas.blit(self.axes[1].bbox)
        self.fig.canvas.flush_events()
        self.show()
        #plt.pause(0.001)#max(0.001, 1 - (time.time() - self._lastRefresh)))
        self._lastRefresh = time.time()
        
        
