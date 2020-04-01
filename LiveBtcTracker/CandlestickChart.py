import time
import gc
from matplotlib import rcParams as rcparams
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.collections as mcoll

from Indicators import *
from Configuration import SettingsDialog as confDiag

class Colors():

    background = "#1e1e1e"
    text = "#cecece"
    cursor = "#6e6e6e"
    axis = "#3e3e3e"
    axis_labels = "#9e9e9e"
    grid_lines = "#5e5e5e"
    fib_levels = "#e5ce46"
    buyEMA = "#3333ff"
    sellEMA = "#ffff00"
    bband_fill = "#273146"

    green = "#22d615"
    red = "#ea2222"
    blue = "#5087fa"

class PriceChart():

    def __init__(self, ax, xlims):
        self.ax = ax
        self.xlims = xlims

        self.bbands = [[],[],[]]            # list of lists of data that creates the three lines for the BBands
        self.bbandOn = False                # display bbands
        self.bbandsPlt = [None, None, None] # list of line objects that create the BBands
        self.bbandsUpdated = False          # bbands data has been updated
        self.candlesticks = ([],[])         # tuple of lists of lines and rectangle patches forming candlesticks
        self.fibs = [[],[]]                 # tuple of lists of fib retrace level lines and text
        self.fibOn = False                  # display fib levels
        self.grid = None                    # grid lines collection
        self.hiLine = None                  # line object marking the highest price in the viewing window
        self.hiText = None                  # text to go with the highest price marker
        self.last20 = []                    # keep track of last 20 closing prices for BBands
        self.loaded = False                 # price chart has been loaded and initialized
        self.loLine = None                  # line object marking the lowest price in the viewing window
        self.loText = None                  # text to go with the lowest price marker
        self.lvlTextPos = 0                 # x-position of the text for the price level markers
        self.ohlc = []                      # data for each period of price data: [index, open, high, low, close]
        self.title = None                   # text object showing live ticker price and time left in candle

        self.ax.set_ylabel("Price (USD)")
        self.ax.set_facecolor(Colors.background)

    # ----- Private Functions ----- #
    def _calcBBfromHist(self, data, histCnt):
        numEx = len(data)
        smaBBandStart = histCnt + 20
        sumPd = 0
        sqSum = 0
        
        # First EMA value is a SMA
        # calculate SMA for first X intervals of emaX
        for i in range(20):
            idx = smaBBandStart-1-i
            temp = sum([float(x[idx][4]) for x in data if x[idx][4] != 0]) / len([float(x[idx][4]) for x in data if x[idx][4] != 0])
            self.last20.append(temp)
            sumPd += temp
            sqSum += temp * temp

        mean = sumPd / 20
        var = sqSum / 20 - mean * mean
        stdev = var**0.5
        self.bbands[0].append(mean+stdev*2)
        self.bbands[1].append(mean)
        self.bbands[2].append(mean-stdev*2)

    def _initHiLoLevels(self):           
        maxHi = self.getHighestPrice()
        self.hiLine, = self.ax.plot(self.xlims,
                                  [maxHi, maxHi],
                                  linestyle="--",
                                  color=Colors.green,
                                  linewidth=0.5)
        self.hiText = self.ax.text(self.xlims[1] + self.lvlTextPos,
                                   maxHi,
                                   "%.2f" % maxHi,
                                   fontsize=9,
                                   color=Colors.green)
        
        minLo = self.getLowestPrice()
        self.loLine, = self.ax.plot(self.xlims,
                                  [minLo, minLo],
                                  linestyle="--",
                                  color=Colors.red,
                                  linewidth=0.5)
        self.loText = self.ax.text(self.xlims[1] + self.lvlTextPos,
                                   minLo,
                                   "%.2f" % minLo,
                                   fontsize=9,
                                   color=Colors.red)

        buf = (maxHi - minLo) * 0.12
        self.ax.set_ylim(minLo - buf, maxHi + buf)

        # initialize fib levels
        for i in range(6):
            temp, = self.ax.plot([0,0], [0,0], linestyle="--", color=Colors.fib_levels, linewidth=0.4)
            temp2 = self.ax.text(self.xlims[1]+self.lvlTextPos,0,"",fontsize=9,color=Colors.fib_levels)
            self.fibs[0].append(temp)
            self.fibs[1].append(temp2)

    def _initGrid(self):
        yticks = self.ax.get_yticks()
        lines = ([[(x, y) for x in self.xlims] for y in yticks])
        self.grid = mcoll.LineCollection(lines, linestyles="--", linewidth=0.7, color=Colors.grid_lines)
        self.ax.add_collection(self.grid)

    def _initCandlesticks(self):
        self.candlesticks = [[],[]] #candle(self.axes[0], self.ohlc, width=0.5, colorup=Colors.green, colordown=Colors.red)
        for i in range(len(self.ohlc)):
            self._createCandlestick(i=i)
            self.drawCandlesticks(i=i)

    def _initBBands(self): 
        self.bbandsPlt[0], = self.ax.plot(range(len(self.bbands[0])-1), self.bbands[0][1:], color=Colors.blue, linewidth=0.6)
        self.bbandsPlt[1], = self.ax.plot(range(len(self.bbands[1])-1), self.bbands[1][1:], color=Colors.blue, linestyle=(0,(5,10)), linewidth=0.6)
        self.bbandsPlt[2], = self.ax.plot(range(len(self.bbands[2])-1), self.bbands[2][1:], color=Colors.blue, linewidth=0.6)
        self.bbandFill = self.ax.fill_between(range(len(self.bbands[0])-1), self.bbands[0][1:], self.bbands[2][1:], facecolor=Colors.bband_fill, interpolate=True)

    def _createCandlestick(self, i):
        # create new candlestick and add it to the axis
        self.candlesticks[0].append(mlines.Line2D([i, i], [0, 0], linewidth=0.5))
        self.ax.add_line(self.candlesticks[0][-1])
        self.candlesticks[1].append(mpatches.Rectangle((i - 0.25, 0), width=0.5, height=0))
        self.ax.add_patch(self.candlesticks[1][-1])

    # ----- Public Functions ----- #
    def loadHistory(self, idx, data):
        self.ohlc.append([idx] + [0]*4)
        for j in range(1,5):
            self.ohlc[idx][j] = sum([float(x[j]) for x in data]) / len(data)

        # BBands
        self.last20 = self.last20[1:] + [self.ohlc[idx][4]]
        newMean = sum(self.last20) / 20
        sqSum = sum([(x-newMean)**2 for x in self.last20])
        newStdev = (sqSum / 20)**0.5

        self.bbands[0].append(newMean+newStdev*2)
        self.bbands[1].append(newMean)
        self.bbands[2].append(newMean-newStdev*2)

    def initPlot(self, xlims):
        self.xlims = xlims
        self._initHiLoLevels()
        self._initGrid()
        self._initCandlesticks()
        self._initBBands()
        self.loaded = True
        self.updateFibLevels()

    def incCurrIntvl(self, idx):
        # update candlestick chart
        self.ohlc.append([idx] + [0]*4)
        self.bbands[0].append(self.bbands[0][-1])
        self.bbands[1].append(self.bbands[1][-1])
        self.bbands[2].append(self.bbands[2][-1])
        self.last20 = self.last20[1:] + [0]
        self._createCandlestick(idx)

        # make sure bbands are updated and drawn
        self.updateBBands(update=True)
        self.drawBBands()

    # ----- Attributes, getters/setters ----- #
    def setTextPos(self, xpos):
        self.lvlTextPos = xpos

    def toggleFib(self, flag=None):
        if flag != None:
            if self.fibOn == flag: return
            self.fibOn = flag
        else:
            self.fibOn = not self.fibOn

        if not self.loaded: return
        for lvl,txt in zip(self.fibs[0], self.fibs[1]):
            lvl.set_visible(self.fibOn)
            txt.set_visible(self.fibOn)
        self.updateFibLevels()

    def toggleBBand(self, flag=None):
        if flag != None:
            if self.bbandOn == flag: return
            self.bbandOn = flag
        else:
            self.bbandOn = not self.bbandOn
            
        if not self.loaded: return
        for bb in self.bbandsPlt:
            if bb != None:
                bb.set_visible(self.bbandOn)
            self.bbandFill.set_visible(self.bbandOn)
        self.drawBBands()

    def setXlims(self, xlims, updatemarkers=True):
        self.xlims = xlims

        if not updatemarkers: return
        # get hi/lo prices after panning
        hi = self.getHighestPrice()
        lo = self.getLowestPrice()
        self.updateHiLevel(hi=hi, lo=lo)
        self.updateLoLevel(hi=hi, lo=lo)
        self.updateFibLevels(hi=hi, lo=lo)
        self.updateGrid()

        return lo, hi

    def getHighestPrice(self):
        idx = int(max(0, self.xlims[0]))
        idx2 = int(min(len(self.ohlc), self.xlims[1]))
        return max([x[2] for x in self.ohlc[idx:idx2]])

    def getLowestPrice(self):
        idx = int(max(0, self.xlims[0]))
        idx2 = int(min(len(self.ohlc), self.xlims[1]))
        return min([x[3] for x in self.ohlc[idx:idx2]])

    def getCandle(self, idx):
        if 0 <= idx <= len(self.ohlc):
            return self.ohlc[idx]
        else:
            print("Invalid candle index")
    
    # ----- Update and Draw ----- #
    def updateCandlesticks(self, data):
        for i in range(1,5):
            self.ohlc[-1][i] = sum([float(x[0][i]) for x in data]) / len(data)
        
    def drawCandlesticks(self, i=None):
        if i == None:
            i = -1
        try:
            self.candlesticks[0][i].set_ydata([self.ohlc[i][2], self.ohlc[i][3]])
            # open > close
            if self.ohlc[i][1] > self.ohlc[i][4]:
                self.candlesticks[1][i].set_y(self.ohlc[i][4])
                self.candlesticks[1][i].set_height(self.ohlc[i][1] - self.ohlc[i][4])
                self.candlesticks[1][i].set_color(Colors.red)
                self.candlesticks[0][i].set_color(Colors.red)
            # open <= close
            else:
                self.candlesticks[1][i].set_y(self.ohlc[i][1])
                self.candlesticks[1][i].set_height(self.ohlc[i][4] - self.ohlc[i][1])
                self.candlesticks[1][i].set_color(Colors.green)
                self.candlesticks[0][i].set_color(Colors.green)
        except Exception as e:
            print("Could not draw candlesticks:", e)
               
    def updateHiLevel(self, hi=None, lo=None):
        if hi == None: hi = self.getHighestPrice()
        if lo == None: lo = self.getLowestPrice()
        
        self.hiLine.set_data([-1, self.xlims[1]], [hi, hi])
        self.hiText.set_text("%.2f" % hi)
        self.hiText.set_position((self.xlims[1] + self.lvlTextPos, hi))
        buf = (hi - lo) * 0.12
        self.ax.set_ylim(self.ax.get_ylim()[0], hi + buf)
 
    def updateLoLevel(self, hi=None, lo=None):
        if hi == None: hi = self.getHighestPrice()
        if lo == None: lo = self.getLowestPrice()
        if lo == 0: return
        
        self.loLine.set_data([-1, self.xlims[1]], [lo, lo])  
        self.loText.set_text("%.2f" % lo)
        self.loText.set_position((self.xlims[1] + self.lvlTextPos, lo))
        buf = (hi - lo) * 0.12
        self.ax.set_ylim(lo - buf, self.ax.get_ylim()[1])

    def updateGrid(self):
        yticks = self.ax.get_yticks()
        lines = ([[(x, y) for x in self.xlims] for y in yticks])
        self.grid.set_paths(lines)        

    def updateFibLevels(self, hi=None,lo=None):
        if not self.fibOn: return
            
        if hi == None: hi = self.getHighestPrice()
        if lo == None: lo = self.getLowestPrice()
        diff = hi - lo
      
        xh = [i for i,d in enumerate(self.ohlc) if d[2] == hi]
        xl = [i for i,d in enumerate(self.ohlc) if d[3] == lo]
        xh = xh[-1]
        xl = xl[-1]
        if xh == xl:
            for fib,txt in zip(self.fibs[0], self.fibs[1]):
                fib.set_data([0,0], [0,0])
                txt.set_text("")
            return

        m = diff / (xh - xl)        
        b = hi - m*xh

        if xh > xl:
            fib23_6 = hi - diff * 0.236
            fib38_2 = hi - diff * 0.382
            fib50_0 = hi - diff * 0.5
            fib61_8 = hi - diff * 0.618
            fib78_6 = hi - diff * 0.786
        else:
            fib23_6 = lo + diff * 0.236
            fib38_2 = lo + diff * 0.382
            fib50_0 = lo + diff * 0.5
            fib61_8 = lo + diff * 0.618
            fib78_6 = lo + diff * 0.786
        self.fibs[0][0].set_data([(fib23_6 - b) / m, self.xlims[1]], [fib23_6, fib23_6])
        self.fibs[0][1].set_data([(fib38_2 - b) / m, self.xlims[1]], [fib38_2, fib38_2])
        self.fibs[0][2].set_data([(fib50_0 - b) / m, self.xlims[1]], [fib50_0, fib50_0])
        self.fibs[0][3].set_data([(fib61_8 - b) / m, self.xlims[1]], [fib61_8, fib61_8])
        self.fibs[0][4].set_data([(fib78_6 - b) / m, self.xlims[1]], [fib78_6, fib78_6])
        self.fibs[0][5].set_data([(hi - b) / m, (lo - b) / m], [hi, lo])

        self.fibs[1][0].set_text("%.2f" % fib23_6)
        self.fibs[1][0].set_position((self.xlims[1]+self.lvlTextPos, fib23_6))
        self.fibs[1][1].set_text("%.2f" % fib38_2)
        self.fibs[1][1].set_position((self.xlims[1]+self.lvlTextPos, fib38_2))
        self.fibs[1][2].set_text("%.2f" % fib50_0)
        self.fibs[1][2].set_position((self.xlims[1]+self.lvlTextPos, fib50_0))
        self.fibs[1][3].set_text("%.2f" % fib61_8)
        self.fibs[1][3].set_position((self.xlims[1]+self.lvlTextPos, fib61_8))
        self.fibs[1][4].set_text("%.2f" % fib78_6)
        self.fibs[1][4].set_position((self.xlims[1]+self.lvlTextPos, fib78_6))

    def updateBBands(self, update=False):
        # avoid doing a costly calculation unless the new value is more than one stdev away
        stdev = (self.bbands[0][-1] - self.bbands[1][-1])/2
        if not update and abs(self.ohlc[-1][4] - self.last20[-1]) < stdev: return

        self.last20[-1] = self.ohlc[-1][4]
        newMean = sum(self.last20) / 20
        sqSum = sum([(x-newMean)**2 for x in self.last20])
        newStdev = (sqSum / 20)**0.5

        self.bbands[0][-1] = (newMean+newStdev*2)
        self.bbands[1][-1] = (newMean)
        self.bbands[2][-1] = (newMean-newStdev*2)
        self.bbandsUpdated = True

    def drawBBands(self):
        if not self.bbandOn or not self.bbandsUpdated: return
        
        for bbp, bb in zip(self.bbandsPlt, self.bbands):
            bbp.set_data(range(len(bb)-1), bb[1:])
        self.bbandFill.remove()
        self.bbandFill = self.ax.fill_between(range(len(self.bbands[0])-1), self.bbands[0][1:], self.bbands[2][1:], facecolor=Colors.bband_fill, interpolate=True)
        self.bbandsUpdated = False

    def update(self, data, xlims):
        needFullRedraw = False
        self.xlims = xlims

        tempHi = self.getHighestPrice()
        tempLo = self.getLowestPrice()
        self.updateCandlesticks(data)
        self.drawCandlesticks()
        # check if highest or lowest price changed (new data or panning window) and update the markers
        newHi = self.getHighestPrice()
        newLo = self.getLowestPrice()
        if tempHi != newHi:
            self.updateHiLevel(hi=newHi, lo=newLo)
            self.updateFibLevels(hi=newHi, lo=newLo)
            self.updateGrid()
            needFullRedraw = True
        if tempLo != newLo:
            self.updateLoLevel(hi=newHi, lo=newLo)
            self.updateFibLevels(hi=newHi, lo=newLo)
            self.updateGrid()
            needFullRedraw = True
        self.updateBBands()
        self.drawBBands()

        return needFullRedraw

    def efficientDraw(self, redraw):
        if redraw:
            if self.bbandOn:
                self.ax.draw_artist(self.bbandFill)
                for bband in self.bbandsPlt:
                    self.ax.draw_artist(bband)
                    
            if self.fibOn:
                for fib in self.fibs[0]:
                    self.ax.draw_artist(fib)

            self.ax.draw_artist(self.grid)
            
            # draw all candlesticks in current viewing window (within xlims)
            idx0 = max(0, self.xlims[0])
            idx1 = min(self.xlims[1]+1, len(self.candlesticks[0]))
            if idx1 == len(self.candlesticks[0]): idx1 -= 1
            for i in range(idx0, idx1):
                self.ax.draw_artist(self.candlesticks[0][i])
                self.ax.draw_artist(self.candlesticks[1][i])
            self.ax.draw_artist(self.hiLine)
            self.ax.draw_artist(self.loLine)
        else:
            # only redraw the newest (live) candle and the bbands
            self.ax.draw_artist(self.candlesticks[0][-1])
            self.ax.draw_artist(self.candlesticks[1][-1])


class VolumeChart():
    def __init__(self, ax, xlims, coinPair):
        self.ax = ax
        self.xlims = xlims

        self.volBars = []                   # stores the rectangle patches for the volume bar graph
        self.vol = []                       # stores the value of the cumulative volume per period by exchange
        self.volRatio = []                  # stores the ratio of buys/total for each period
        self.volRatioText = None            # text object that displays the buy volume ratio of the current viewing window
        self.buyEma = []                    # values for the EMA of buy volume
        self.sellEma = []                   # values for the EMA of sell volume
        self.volEmaPd = 10                  # period for the volume EMAs
        self.volEmaWt = 2/(self.volEmaPd+1) # weight for the volume EMAs  
        self.buyEmaPlt = None               # actual plot object for the buy volume EMA
        self.sellEmaPlt = None              # actual plot object for the sell volume EMA
        self.showVolBreakdown = False       # Volume bars showing the breakdown by exchange
        self.legendLabels = []              # list of strings for the legend
        self.legend = None                  # legend object
        self.loaded = False

        self.ax.set_ylabel("Volume (%s)" % coinPair)
        self.ax.set_facecolor(Colors.background)

    # ----- Private Functions ----- #
    def _calcEMAfromHist(self, data, histCnt):
        numEx = len(data)
        emaVolStart = histCnt + self.volEmaPd
        sumPd = 0
        sqSum = 0
        self.buyEma = [0]
        self.sellEma = [0]
        
        # First EMA value is a SMA
        # calculate SMA for first X intervals of emaX
        for i in range(self.volEmaPd):
            idx = emaVolStart-1-i
            totalVol = sum([float(x[idx][5]) for x in data])
            if len(data[0][idx]) < 10:
                self.buyEma[0] += totalVol * 0.5
                self.sellEma[0] += totalVol * 0.5
            else:
                self.buyEma[0] += totalVol * (float(data[0][idx][9]) / float(data[0][idx][5]))
                self.sellEma[0] += totalVol * (1 - float(data[0][idx][9]) / float(data[0][idx][5]))         
            
        self.buyEma[0] /= self.volEmaPd
        self.sellEma[0] /= self.volEmaPd
        
    def _initVolBars(self):
        numEx = len(self.vol)
        self.volBars.append(self.ax.bar(
                    range(len(self.vol[0])),
                    self.vol[0],
                    linewidth=1).patches)
        if self.showVolBreakdown:
            for i in range(1,numEx):
                self.volBars.append(self.ax.bar(
                    range(len(self.vol[i])),
                    self.vol[i],
                    linewidth=0.7).patches)
                
        for bar,v,r in zip(self.volBars[0], self.vol[0], self.volRatio):
            bar.set_height(v)
            # Highlight bars depending on the ratio of taker buys:sells
            # Binance is the only exchange that provides this info
            if r > 0.5:
                if self.showVolBreakdown:
                    bar.set_edgecolor(Colors.green)
                else:
                    bar.set_color(Colors.green)
            elif r < 0.5:
                if self.showVolBreakdown:
                    bar.set_edgecolor(Colors.red)
                else:
                    bar.set_color(Colors.red)
            else:
                if self.showVolBreakdown:
                    bar.set_edgecolor(Colors.blue)
                else:
                    bar.set_color(Colors.blue)
                    
        if self.showVolBreakdown:
            for i in range(1, numEx):
                for bar,v in zip(self.volBars[i], self.vol[i]):
                    bar.set_height(v)

        self.buyEmaPlt, = self.ax.plot(
            range(len(self.buyEma)-1), self.buyEma[1:], "-", c=Colors.buyEMA, linewidth=0.9)
        self.sellEmaPlt, = self.ax.plot(
            range(len(self.sellEma)-1), self.sellEma[1:], "-", c=Colors.sellEMA, linewidth=0.9)

        self.volRatioText = self.ax.text(0, 0, "", fontsize=9, color=Colors.text)

    def _createBar(self):
        for i in range(len(self.volBars)):
            self.volBars[i].append(mpatches.Rectangle((len(self.vol[0])-1 - 0.4, 0), width=0.8, height=0, color=self.volBars[i][-1].get_fc()))
            self.ax.add_patch(self.volBars[i][-1])
  
    # ----- Public Functions ----- #
    def loadHistory(self, idx, data):
        numEx = len(data)

        if len(self.vol) == 0:
            self.vol = [[] for i in range(numEx)]
            
        # sum volume from all exchanges
        for j in range(numEx):           
            self.vol[j].append( sum([float(x[5]) for x in data[j:]]) )

        # calc buy volume percentage
        # ignore if binance isn't being tracked, or server is down, or has no volume
        if len(data[0]) < 10 or float(data[0][5]) == 0:
            self.volRatio.append(0.5)
        else:
            self.volRatio.append( (float(data[0][9]) / float(data[0][5])) )

        # update volume EMAs
        self.buyEma.append((self.volRatio[idx] * self.vol[0][idx]) * self.volEmaWt +\
                           self.buyEma[-1] * (1 - self.volEmaWt))
        self.sellEma.append(((1 - self.volRatio[idx]) * self.vol[0][idx]) * self.volEmaWt +\
                           self.sellEma[-1] * (1 - self.volEmaWt))

    def initPlot(self, xlims):
        self.xlims = xlims
        self._initVolBars()
        self.setVolumeLegend()
        self.loaded = True

    def incCurrIntvl(self, idx):
        for v in self.vol:
            v.append(0)
        self.volRatio.append(0)
        self._createBar()
        self.buyEma.append(0)
        self.sellEma.append(0)
        
    # ----- Attributes, getters/setters
    def getVolBar(self, idx, ex=0):
        return self.vol[ex][idx], self.volRatio[idx]

    def setVol(self, ex, intvl, val):
        self.vol[ex][intvl] = val
        if ex == 0:
            self.volBars[0][intvl].set_height(val)
        elif self.showVolBreakdown:
            self.volBars[ex][intvl].set_height(val)

    def getMaxVolume(self, mode):
        if mode == "window":
            return max(self.vol[0][max(0, self.xlims[0]):min(len(self.vol[0]), self.xlims[1])])
        elif mode == "all":
            return max(self.vol[0])
        else:
            return -1

    def setVolBreakdown(self, show):
        if not self.loaded: self.showVolBreakdown = show; return
        if show:
            for bar,r in zip(self.volBars[0], self.volRatio):
                bar.set_color(Colors.blue)
                if r > 0.5: bar.set_edgecolor(Colors.green)
                elif r < 0.5: bar.set_edgecolor(Colors.red)
            for i in range(1,len(self.vol)):
                self.volBars.append(self.ax.bar(
                    range(len(self.vol[i])),
                    self.vol[i],
                    linewidth=0.7).patches)
        elif self.showVolBreakdown:
            for bar,r in zip(self.volBars[0], self.volRatio):
                if r > 0.5: bar.set_color(Colors.green)
                elif r < 0.5: bar.set_color(Colors.red)
                else: bar.set_color(Colors.blue)
            for i in range(1,len(self.vol)):
                for bar in self.volBars[i]:
                    bar.remove()
            self.volBars = self.volBars[:1]
            
        self.showVolBreakdown = show

    def setVolumeLegend(self, labels=None):
        if not self.loaded and labels != None: self.legendLabels = labels; return
        if labels != None:
            self.legendLabels = labels
        if self.showVolBreakdown:
            self.legend = self.ax.legend([x[0] for x in self.volBars], self.legendLabels,
                                              fancybox=False,
                                              shadow=False,
                                              frameon=False,
                                              loc="lower right")
            for text in self.legend.get_texts():
                text.set_color(Colors.text)
        else:
            if self.legend != None: self.ax.get_legend().remove()


    # ----- Update and Draw ----- #
    def updateCurrentVol(self, data):
        numEx = len(data)
        # bar graph is stacked so each vol is the sum of all vols proceeding it
        # (i.e. vol[0] is sum of all exchanges, vol[-1] is the volume of a single exchange)
        for i in range(numEx):
            self.vol[i][-1] = sum([float(x[0][5]) for x in data[i:]])
        if len(data[0][0]) < 10 or float(data[0][0][5]) == 0:    # in case binance data isn't included
            self.volRatio[-1] = 0.5
        else:
            self.volRatio[-1] = (float(data[0][0][9]) / float(data[0][0][5]))

        self.buyEma[-1] = (self.volRatio[-1] * self.vol[0][-1]) * self.volEmaWt +\
                             self.buyEma[-2] * (1 - self.volEmaWt)
        self.sellEma[-1] = ((1 - self.volRatio[-1]) * self.vol[0][-1]) * self.volEmaWt +\
                             self.sellEma[-2] * (1 - self.volEmaWt)

    def drawVolBars(self):
        try:
            numEx = len(self.vol)
            self.volBars[0][-1].set_height(self.vol[0][-1])
            if self.volRatio[-1] > 0.5:
                if self.showVolBreakdown:
                    self.volBars[0][-1].set_edgecolor(Colors.green)
                else:
                    self.volBars[0][-1].set_color(Colors.green)
            elif self.volRatio[-1] < 0.5:
                if self.showVolBreakdown:
                    self.volBars[0][-1].set_edgecolor(Colors.red)
                else:
                    self.volBars[0][-1].set_color(Colors.red)
            else:
                if self.showVolBreakdown:
                    self.volBars[0][-1].set_edgecolor(Colors.blue)
                else:
                    self.volBars[0][-1].set_color(Colors.blue)
                    
            if self.showVolBreakdown:
                for i in range(1, numEx):
                    self.volBars[i][-1].set_height(self.vol[i][-1])
                
            # Update y-axis limits to be just above the max volume
            startIdx = max(0, self.xlims[0])
            maxVol = max(self.vol[0][startIdx:self.xlims[1]])
            self.ax.set_ylim(0, maxVol*1.06)

            # Draw EMA lines of buy and sell volume
            self.buyEmaPlt.set_data(range(len(self.buyEma)-1), self.buyEma[1:])
            self.sellEmaPlt.set_data(range(len(self.sellEma)-1), self.sellEma[1:])

            # Calculate the percentage of buys from total volume (in current window)
            buyRat = 0
            stopIdx = min(self.xlims[1], len(self.vol[0]))
            for i in range(startIdx, stopIdx):
                buyRat += self.volRatio[i] * self.vol[0][i]
            buyRat /= sum([x for x in self.vol[0][startIdx:stopIdx]])
            
            xloc = (self.xlims[1] - self.xlims[0])*0.94 + self.xlims[0] #self.xlims[1] - self._pixelsToPoints(50)#(self.xlims[1] - self.xlims[0])*0.94 + self.xlims[0]
            self.volRatioText.set_text("%.1f%%" % (buyRat * 100))
            self.volRatioText.set_position((xloc, maxVol*0.99))
        except Exception as e:
           print("Could not draw volume chart:", e)

    def update(self, data, xlims):
        self.xlims = xlims
        self.updateCurrentVol(data)
        self.drawVolBars()

    def efficientDraw(self, redraw):
        if redraw:
            if self.showVolBreakdown:
                self.ax.draw_artist(self.legend)
            idx0 = max(0, self.xlims[0])
            idx1 = min(self.xlims[1]+1, len(self.volBars[0]))
            if idx1 == len(self.volBars[0]): idx1 -= 1
            for i in range(idx0, idx1):
                self.ax.draw_artist(self.volBars[0][i])
                if self.showVolBreakdown:
                    for j in range(1, len(self.volBars)):
                        self.ax.draw_artist(self.volBars[j][i])
        else:
            self.ax.draw_artist(self.volBars[0][-1])
            if self.showVolBreakdown:
                for j in range(1, len(self.volBars)):
                    self.ax.draw_artist(self.volBars[j][-1])
            self.ax.draw_artist(self.buyEmaPlt)
            self.ax.draw_artist(self.sellEmaPlt)
            self.ax.draw_artist(self.volRatioText)


class CandlestickChart():

    def __init__(self, coinPair, conf):
        
        numIndicators = len(conf["indicators"])
        rcparams["toolbar"] = "None"
        self.fig = plt.figure("Live BTC Tracker (v%s)" % conf["version"], facecolor=Colors.background)
        self.fig.set_size_inches(8, 5+(1.5*numIndicators))  # 1.5-inch per indicator
            
        # Initialize subplots for price and volume charts
        self.axes = [plt.subplot2grid((5+numIndicators,1),(0,0), rowspan=3)]
        self.axes.append(plt.subplot2grid((5+numIndicators,1),(3,0), rowspan=2, sharex=self.axes[0]))
        for i in range(numIndicators): # add subplot axes for indicators (1 rowspan per indicator)
            self.axes.append(plt.subplot2grid((5+numIndicators,1),(5+i,0), sharex=self.axes[0]))
        plt.subplots_adjust(top=0.99, bottom=0.05, wspace=0, hspace=0.05)

        # Connect event handlers
        self.fig.canvas.mpl_connect("resize_event", self._handleResize)
        self.fig.canvas.mpl_connect("close_event", self._handleClose)
        self.fig.canvas.mpl_connect("scroll_event", self._handleScroll)
        self.fig.canvas.mpl_connect("button_press_event", self._mouseClick)
        self.fig.canvas.mpl_connect("button_release_event", self._mouseRelease)
        self.fig.canvas.mpl_connect("key_press_event", self._handleKey)
        self.fig.canvas.mpl_connect("motion_notify_event", self._mouseMove)
        self.fig.canvas.mpl_connect("figure_enter_event", self._mouseEnter)
        self.fig.canvas.mpl_connect("axes_enter_event", self._mouseEnter)
        self.fig.canvas.mpl_connect("axes_leave_event", self._mouseLeave)
        self.fig.canvas.mpl_connect("figure_leave_event", self._mouseLeave)

        # Cursor
        self.cursor = mlines.Line2D([-1, -1], [0, 100000], linewidth=1, color=Colors.cursor)
        self.cursor1 = mlines.Line2D([-1, -1], [0, 100000], linewidth=1, color=Colors.cursor)
        self.axes[0].add_line(self.cursor)
        self.axes[1].add_line(self.cursor1)
        self.cursorText0 = self.axes[0].text(-0.75, 0, "", fontsize=8, color=Colors.text)
        self.cursorText1 = self.axes[1].text(-0.75, 0, "", fontsize=8, color=Colors.text)
        self.cursorOn = False

        # misc vars
        self.active = False                 # figure is "active" (mouse is on figure)
        self.backgrounds = None             # canvas image for each axis to draw more efficently [blank canvas, canvas with non-changing objects drawn]
        self.currInt = 0                    # index of the current interval
        self.kill = False                   # application has been closed
        self.enableIdle = conf["enableIdle"]# idling is enabled (updated less often)
        self.fullRedraw = False             # figure and all objects should be completely redrawn
        self.lastMouseX = 0                 # last record x-position of the mouse
        self.loaded = False                 # whether or not history was loaded and drawn
        self.numCandles = conf["viewSize"]  # number of candles to view at launch
        self.oldData = None                 # original data loaded onto chart
        self.pan = False                    # figure is in panning mode
        self.redraw = True                  # figure should be redrawn efficiently (reload background_0, resave background_1)       
        self.resaveBG = False               # canvas backgrounds need to be resaved (e.g. figure resized)
        self.settings = None                # settings dialog
        self.timeframe = conf["timeFrame"]  # string of timeframe (e.g. "1h")
        self.timestamps = []                # store epoch timestamps of every interval
        self.xlims = [100 - self.numCandles, 100 + self.numCandles]   # bounds of the x-axis

        # price chart
        self.priceChart = PriceChart(self.axes[0], self.xlims)
        self.priceChart.toggleFib(conf["showFib"])
        self.priceChart.toggleBBand(conf["showBBands"])

        # volume chart
        self.volumeChart = VolumeChart(self.axes[1], self.xlims, coinPair)
        self.volumeChart.setVolBreakdown(conf["showVolBreakdown"])
        self.volumeChart.setVolumeLegend(conf["legend"])
                  
        # indicators
        self.indicators = []
        for i,ind in enumerate(conf["indicators"]):
            ind = ind.lower()
            if ind == "macd":
                self.indicators.append(MACD(self.axes[2+i], self.xlims))
            elif ind == "rsi":
                self.indicators.append(RSI(self.axes[2+i], self.xlims))
            elif ind == "obv":
                self.indicators.append(OBV(self.axes[2+i], self.xlims))
            else:
                print("WARNING: No indicator named '%s'" % ind)

        # Initialize title
        self.title = self.axes[0].text(95, 0.01, "", fontsize=12, color=Colors.text)

        # set axis limits (also affects indicators)
        for ax in self.axes:
            ax.set_xticklabels([])
            ax.set_xlim(self.xlims)
            ax.spines["bottom"].set_color(Colors.axis)
            ax.spines["top"].set_color(Colors.axis)
            ax.spines["left"].set_color(Colors.axis)
            ax.spines["right"].set_color(Colors.axis)
            ax.tick_params(axis='y', colors=Colors.axis_labels)
            ax.yaxis.label.set_color(Colors.axis_labels)

    # ----- Event Handlers ----- #
    def _handleClose(self, event):
        self.kill = True

    def _handleResize(self, event):
        if self.loaded:
            self.resaveBG = True
            self.fullRedraw = True
            self.priceChart.setTextPos(self._pixelsToPoints(10))

    def _handleScroll(self, event):
        dx = int(event.step)
        while abs(dx) > 0:
            if -1 <= self.xlims[0] + dx < self.currInt - 1:
                self._adjustXlims(dx, 0)

                # adjust cursor and text
                if self.cursorOn:
                    cx = int(round(event.xdata))
                    self.cursor.set_xdata([cx, cx])
                    self.cursor1.set_xdata([cx, cx])
                    self._updateCursorText(cx)
                    
                break
            dx = dx + 1 if dx < 0 else dx - 1

    def _handleKey(self, event):
        if event.key == "r":
            self.priceChart.toggleFib() 
            self.fullRedraw = True
        elif event.key == "b":
            self.priceChart.toggleBBand()
            self.redraw = True
        elif event.key == "s":
            if self.settings == None:
                self.settings = confDiag()
                self.settings.loadIndicators(self.indicators)
                self.settings.setConfig(self.timeframe, self.enableIdle, self.volumeChart.showVolBreakdown,
                                        self.priceChart.fibOn, self.priceChart.bbandOn, self.numCandles)

    def _mouseClick(self, event):
        self.pan = True
        self.lastMouseX = event.x

        if event.inaxes != None and self.settings == None:
            axIdx = self.axes.index(event.inaxes) # get which axis was clicked
            # check if [X] was clicked and remove the indicator
            if axIdx >= 2 and self.indicators[axIdx-2].X_Clicked:
                self._removeIndicator(axIdx-2)

    def _mouseRelease(self, event):
        self.pan = False

    def _mouseEnter(self, event):
        self.cursorOn = True
        self.pan = False
        self.active = True

    def _mouseLeave(self, event):
        self.cursorOn = False
        self.cursorText0.set_text("")
        self.cursorText1.set_text("")
        self.cursor.set_xdata([-1, -1])
        self.cursor1.set_xdata([-1, -1])

        self.pan = False
        self.active = False
    
    def _mouseMove(self, event):
        if not self.loaded: return
        if event.xdata == None: return
        if self.pan:
            dx = self._pixelsToPoints(event.x - self.lastMouseX)
            if abs(dx) < 1: return
            if -1 <= self.xlims[0]-dx < self.currInt-1:
                self.lastMouseX = event.x
                self._adjustXlims(-dx, -dx)               

        if self.cursorOn:
            x = int(round(event.xdata))
            # cursor is within bounds of candlestick data - round to nearest interval
            if 0 <= x <= self.currInt: cx = x
            else: cx = event.xdata
            self.cursor.set_xdata([cx, cx])
            self.cursor1.set_xdata([cx, cx])
            self.cursor1.set_ydata([0, self.volumeChart.getMaxVolume("all")*1.1])
            self._updateCursorText(x)

        # get which axis was clicked and set the appropriate indicator to active
        axIdx = self.axes.index(event.inaxes)
        for i in range(len(self.indicators)):
            self.indicators[i].active = (axIdx == i+2)


    # ----- Private Functions ----- #
    def _removeIndicator(self, idx):
        if idx < 0: return

        # delete the axis and remove from axes and indicator lists
        self.fig.delaxes(self.axes[2+idx])
        self.axes = self.axes[:2+idx] + self.axes[2+idx+1:]
        self.indicators = self.indicators[:idx] + self.indicators[idx+1:]
        self.backgrounds = self.backgrounds[:2+idx] + self.backgrounds[2+idx+1:]

        self._resetAxesPos(len(self.indicators))

    def _addIndicator(self, name):
        name = name.lower()
        numIndicators = len(self.indicators) + 1

        self._resetAxesPos(numIndicators)    

        self.axes.append(plt.subplot2grid((5+numIndicators, 1), (4+numIndicators, 0), sharex=self.axes[0]))
        if name == "macd":
            self.indicators.append(MACD(self.axes[1+numIndicators], self.xlims))
        elif name == "rsi":
            self.indicators.append(RSI(self.axes[1+numIndicators], self.xlims))
        elif name == "obv":
            self.indicators.append(OBV(self.axes[1+numIndicators], self.xlims))
        self.backgrounds.append([None, None])

        self.axes[-1].set_xticklabels([])
        self.axes[-1].set_xlim(self.xlims)
        self.axes[-1].spines["bottom"].set_color(Colors.axis)
        self.axes[-1].spines["top"].set_color(Colors.axis)
        self.axes[-1].spines["left"].set_color(Colors.axis)
        self.axes[-1].spines["right"].set_color(Colors.axis)
        self.axes[-1].tick_params(axis='y', colors=Colors.axis_labels)
        self.axes[-1].yaxis.label.set_color(Colors.axis_labels)

    def _resetAxesPos(self, n):
        gs = gridspec.GridSpec(5+n, 1)
        
        # Set the new position and subplotspec for price and volume
        self.axes[0].set_position(gs[0:3].get_position(self.fig))
        self.axes[0].set_subplotspec(gs[0:3])
        self.axes[1].set_position(gs[3:5].get_position(self.fig))
        self.axes[1].set_subplotspec(gs[3:5])

        # set new positino and subplotspec for each indicator
        for i in range(2, len(self.axes)):
            self.axes[i].set_position(gs[3+i].get_position(self.fig))
            self.axes[i].set_subplotspec(gs[3+i])

        plt.subplots_adjust(top=0.99, bottom=0.05, wspace=0, hspace=0.05)
        #self.fig.set_size_inches(8, 5+(1.5*numIndicators))  # 1.5-inch per indicator
        self.resaveBG = True
        self.fullRedraw = True     

    def _adjustXlims(self, dx0, dx1):
        # get hi/lo prices before panning
        tempHi = self.priceChart.getHighestPrice()
        tempLo = self.priceChart.getLowestPrice()

        # shift the xlims
        self.xlims = [int(round(self.xlims[0]+dx0)), int(round(self.xlims[1]+dx1))]
        for ax in self.axes:
            ax.set_xlim(self.xlims)

        newLo, newHi = self.priceChart.setXlims(self.xlims)

        # if hi/lo price changed, do a full redraw to redraw axis labels and hi/lo text
        if tempHi != newHi or tempLo != newLo:
            self.fullRedraw = True
        self.redraw = True           

    def _updateCursorText(self, x):
        if 0 <= x <= self.currInt:
            timeStr = time.strftime("%d %b %Y %H:%M", time.localtime(self.timestamps[x]))
            tempCandle = self.priceChart.getCandle(x)
            self.cursorText0.set_text(
                "%s    Open: %.2f, High: %.2f, Low: %.2f, Close: %.2f" %
                (timeStr, tempCandle[1], tempCandle[2], tempCandle[3], tempCandle[4]))
            self.cursorText0.set_y(
                self.priceChart.getHighestPrice() + (self.priceChart.getHighestPrice() - self.priceChart.getLowestPrice()) * 0.04)
            self.cursorText0.set_x(self.xlims[0]+0.25)

            tempvol, tempratio = self.volumeChart.getVolBar(x)
            self.cursorText1.set_text("Volume: %.8f (%.1f%% Buys)" % (tempvol, tempratio*100))
            self.cursorText1.set_y(self.volumeChart.getMaxVolume("window"))
            self.cursorText1.set_x(self.xlims[0]+0.25)
        else:
            self.cursorText0.set_text("")
            self.cursorText1.set_text("")

    def _getPlotWidthPixels(self):
        # (figure width in inches * dots/inch) * plot takes up 77.4% of the figure width = plot width in pixels
        return (self.fig.get_size_inches()*self.fig.dpi)[0] * 0.774

    def _pixelsToPoints(self, px):
        return px * (self.xlims[1]-self.xlims[0]) / self._getPlotWidthPixels()

    def _checkTimestamps(self, data, histCnt):
        numEx = len(data)
        fullHist = min([len(x) for x in data])
        medT = sorted([x[fullHist-1][0] for x in data])[int(numEx/2)]
        medT2 = sorted([x[fullHist-2][0] for x in data])[int(numEx/2)]
        gran = medT2 - medT

        newData = [[] for x in data]
        expectedTimestamp = medT + gran * (fullHist-1)
        # shift data when needed if exchange was down (to reallign)
        for i in range(fullHist):
            #avgT = sum([x[i][0] for x in data]) / numEx
            for j in range(numEx):
                # timestamp is less than the average
                if data[j][i][0] != expectedTimestamp:#avgT:
                    # add a dummy entry to shift the data
                    data[j] = data[j][:i] + [[0]*6] + data[j][i:]
                    newData[j].append([0]*6 + [False])
                else:
                    newData[j].append(data[j][i] + [True])
            expectedTimestamp -= gran
        return newData


    # ----- MPL Figure attribute functions ----- #
    def setTitle(self, title):
        try:
            if self.enableIdle and not self.active: title += " [IDLE]"
            self.title.set_text(title)
            ypos = self.axes[0].get_ylim()[0]
            ypos = ypos + (self.priceChart.getLowestPrice() - ypos) * 0.2
            self.title.set_y(ypos)
            self.title.set_x((self.xlims[0] + self.xlims[1])/2 - (self.xlims[1] - self.xlims[0])/6)
        except:
            print("Could not update title")


    # ----- Only run at startup ----- #
    def loadHistory(self, data, histCnt):
        numEx = len(data)

        # calc volume EMAs from history
        self.volumeChart._calcEMAfromHist(data, histCnt)
        self.priceChart._calcBBfromHist(data, histCnt)

        exDown = [[] for i in range(numEx)]
        data = self._checkTimestamps(data, histCnt)
                    
        # traverse history from old to new data
        for i in range(histCnt):
            # candle data is sorted new->old, so index in reverse order
            idx = histCnt-1-i

            # Check timestamps to see if an exchange was down during that time
            self.timestamps.append(max([x[idx][0] for x in data]))
            invalid = []
            avgT = sum([x[idx][0] for x in data]) / numEx
            for j in range(numEx):
                if not data[j][idx][-1]:
                    invalid.append(data[j])
                    exDown[j].append(i)
            # sometimes Binance trading will be down even when the API is active. Check for volume
            if len(data[0][idx]) >= 10 and float(data[0][idx][5]) == 0:
                invalid.append(data[0])
                exDown[0].append(i)

            tempData = [x[idx] if x not in invalid else [0]*10 for x in data]
            self.volumeChart.loadHistory(i, tempData)
            # load an interval of data (one candle/bar) onto price and volume charts
            tempData = [x[idx] for x in data if x not in invalid]
            self.priceChart.loadHistory(i, tempData)
            

        # set axis lims
        self.xlims = [histCnt - self.numCandles, histCnt + self.numCandles]
        for ax in self.axes:
            ax.set_xlim(self.xlims)
        self.priceChart.setXlims(self.xlims, updatemarkers=False)
            
        # "save" backgrounds of axes (before actual data and patches are plotted)
        self.fig.canvas.draw()
        self.backgrounds = [[self.fig.canvas.copy_from_bbox(ax.bbox), None] for ax in self.axes]

        # update title
        self.setTitle("Loading Chart Objects...")
        self.fig.canvas.draw()
        
        # draw price and volume charts
        self.currInt = histCnt - 1
        self.priceChart.setTextPos(self._pixelsToPoints(10))
        self.priceChart.initPlot(self.xlims)
        self.volumeChart.initPlot(self.xlims)     

        # Load history for indicators and plot data
        self.oldData = (data, histCnt)
        for ind in self.indicators:
            ind.loadHistory(self.priceChart.ohlc, data, self.volumeChart.vol[0], histCnt)
            ind.initPlot(self.currInt)

        # draw everything to start
        self.refresh(fullRedraw=True)
        self.loaded = True
        return exDown


    # ----- Everything Else --- #
    def incCurrIntvl(self):
        # update indicators
        for ind in self.indicators:
            ind.update(self.priceChart.ohlc, self.volumeChart.vol[0], self.currInt, retain=False)

        # make sure bbands are updated
        self.priceChart.updateBBands(update=True)

        # update chart limits
        self.currInt += 1
        if self.currInt >= self.xlims[1]-1:
            self.xlims = [self.xlims[0]+1, self.xlims[1]+1]
            for ax in self.axes:
                ax.set_xlim(self.xlims)
            self.priceChart.updateHiLevel()
            self.priceChart.updateLoLevel()

        # update price and volume charts
        self.priceChart.incCurrIntvl(self.currInt)
        self.volumeChart.incCurrIntvl(self.currInt)

        # misc updates
        self.timestamps.append([0])
        self.redraw = True


    # --- Indicator functions --- #
    def updateIndicators(self, retain=True):
        for ind in self.indicators:
            ind.update(self.priceChart.ohlc, self.volumeChart.vol[0], self.currInt, retain)
        
    def drawIndicators(self):
        for ind in self.indicators:
            ind.xlims = self.xlims
            ind.draw(self.currInt)


    # --- Draw/show figure functions --- #
    def resaveBackground(self):
        # shift axes to hide chart objects
        for ax in self.axes:
            ax.set_xlim([-1,-0.5])
            
        self.fig.canvas.draw() # redraw the "blank" canvas

        # copy the blank canvas
        for i in range(len(self.axes)):
            self.backgrounds[i][0] = self.fig.canvas.copy_from_bbox(self.axes[i].bbox)

        # shift axes back to normal
        for ax in self.axes:
            ax.set_xlim(self.xlims)

        # reset fibs so text is alligned correctly (TODO: move this somewhere else?)
        self.priceChart.updateFibLevels()
        
    def efficientDraw(self):
        # Axis 0 (price)
        if self.redraw: # redraw viewing window in event of zooming/panning
            self.fig.canvas.restore_region(self.backgrounds[0][0]) # restore the blank canvas
            self.priceChart.efficientDraw(True)
            self.backgrounds[0][1] = self.fig.canvas.copy_from_bbox(self.axes[0].bbox) # save canvas with all candles except most recent (these objects won't change)
        else:
            self.fig.canvas.restore_region(self.backgrounds[0][1]) # restore the canvas with old candles
        self.priceChart.efficientDraw(False)
            
        # draw the remaining chart objects (cursor, text, etc.)
        self.axes[0].draw_artist(self.title)
        if self.cursorOn:
            self.axes[0].draw_artist(self.cursor)
            self.axes[0].draw_artist(self.cursorText0)
               
        # blit the canvas within the axis bounding box to refresh with the redrawn objects
        self.fig.canvas.blit(self.axes[0].bbox)
        
        # Axis 1 (volume)
        if self.redraw:
            self.fig.canvas.restore_region(self.backgrounds[1][0])
            self.volumeChart.efficientDraw(True)
            self.backgrounds[1][1] = self.fig.canvas.copy_from_bbox(self.axes[1].bbox)
        else:
            self.fig.canvas.restore_region(self.backgrounds[1][1])
        self.volumeChart.efficientDraw(False)

        if self.cursorOn:
            self.axes[1].draw_artist(self.cursor1)
            self.axes[1].draw_artist(self.cursorText1)
        self.fig.canvas.blit(self.axes[1].bbox)

        # Axis 2+ (indicators)
        for i, ind in enumerate(self.indicators):
            if self.redraw:
                self.fig.canvas.restore_region(self.backgrounds[2+i][0])
                ind.drawArtists(self.redraw) # draw objects that are no longer updating so the canvas can be copied
                self.backgrounds[2+i][1] = self.fig.canvas.copy_from_bbox(self.axes[2+i].bbox)
                ind.drawArtists(False) # draw the objects that are updating live
            else:
                self.fig.canvas.restore_region(self.backgrounds[2+i][1])
                ind.drawArtists(self.redraw)
            self.fig.canvas.blit(self.axes[2+i].bbox)

    def updateSettings(self, params):
        # update other parameters
        self.timeframe = params["timeFrame"]
        self.enableIdle = params["enableIdle"] == '1'
        tempVolBreakdown = params["showVolBreakdown"] == '1'
        tempfibOn = params["showFib"] == '1'
        tempbbandOn = params["showBBands"] == '1'

        if tempVolBreakdown != self.volumeChart.showVolBreakdown:
            self.volumeChart.setVolBreakdown(tempVolBreakdown)
            self.volumeChart.setVolumeLegend()
            
        # Update fib levels and bbands as needed
        self.priceChart.toggleFib(tempfibOn)
        self.priceChart.toggleBBand(tempbbandOn)
                  
        self.fullRedraw = True
        
    def update(self, data):
        # check if settings dialog was recently closed
        if self.settings != None and not self.settings.isActive():
            # add and initialize any new indicators
            for ind in self.settings.addedInd:
                self._addIndicator(ind)
                self.indicators[-1].loadHistory(self.priceChart.ohlc, self.oldData[0], self.volumeChart.vol[0], self.oldData[1])
                self.indicators[-1].initPlot(self.currInt)
            # remove indicators
            for ind in self.settings.removedInd:
                tempInd = [type(ind).__name__ for ind in self.indicators]
                self._removeIndicator(tempInd.index(ind))

            self.updateSettings(self.settings.params)
            self.settings = None # dispose of settings object
            gc.collect()    # force garbage collection to prevent "wrong thread disposal"
            
        elif self.settings != None and self.settings.isActive():
            self.settings.update()

        # misc updates
        self.timestamps[-1] = data[0][0][0]

        # update volume chart
        self.volumeChart.update(data, self.xlims)

        # update price chart
        self.fullRedraw = self.fullRedraw or self.priceChart.update(data, self.xlims)

        # update technical indicators
        self.updateIndicators()
        self.drawIndicators() 
        
    def show(self, fullscreen=False, pos=0):
        if fullscreen:
            mgr = plt.get_current_fig_manager()
            mgr.window.wm_geometry("+%d+0" % pos)
            #mgr.window.state("zoomed")
        plt.show(block=False)
        if fullscreen:
            mgr.window.state("zoomed")
            mgr.window.focus()
    
    def refresh(self, fullRedraw=False):
        t0 = time.time()
        if self.kill: raise Exception("Figure closed")

        # resave the background (figure was resized)
        if self.resaveBG:
            self.resaveBackground()
            self.resaveBG = False
                
        # fullRedraw redraws everything on the figure (objects out of view, axes, titles, text, etc.)
        elif fullRedraw or self.fullRedraw:
            self.fig.canvas.draw()
            self.fullRedraw = False
            self.redraw = True
            
        # only draw what needs to be updated (anything that has changed within the viewing window)
        else:
            self.efficientDraw()
            self.redraw = False
            
        self.fig.canvas.flush_events()
        t1 = time.time()
        return
        # print timing information
        if self.resaveBG:
            print("Resave BG: %.1f" % ((t1-t0)*1000))
        elif fullRedraw or self.fullRedraw:
            print("Full Redraw: %.1f" % ((t1-t0)*1000))
        elif self.redraw:
            print("Redraw: %.1f" % ((t1-t0)*1000))
        else:
            print("Draw: %.1f" % ((t1-t0)*1000))
        #print("%.1f fps" % (1/(t1-t0)))#*1000)
