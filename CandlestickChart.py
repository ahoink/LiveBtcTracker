import time
import warnings

# Hide MatplotlibDeprecationWarning
warnings.filterwarnings("ignore",".*GUI is implemented.*")
warnings.filterwarnings("ignore",".*mpl_finance*")

from matplotlib import rcParams as rcparams
import matplotlib.pyplot as plt
from matplotlib.finance import candlestick_ohlc as candle
import matplotlib.lines as mlines
import matplotlib.patches as mpatches

from Indicators import MACD
from Indicators import RSI

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

    green = "#22d615"
    red = "#ea2222"
    blue = "#5087fa"

class CandlestickChart():

    def __init__(self, useCBP, coinPair, *args):
        rcparams["toolbar"] = "None"
        self.fig = plt.figure("Live BTC Tracker (v0.7.0)", facecolor=Colors.background)
        numIndicators = len(args)
        # Initialize subplots for price and volume charts
        self.axes = [plt.subplot2grid((5+numIndicators,1),(0,0), rowspan=3)]
        self.axes.append(plt.subplot2grid((5+numIndicators,1),(3,0), rowspan=2, sharex=self.axes[0]))
        # add subplot axes for indicators (1 rowspan per indicator)
        for i in range(len(args)):
            self.axes.append(plt.subplot2grid((5+numIndicators,1),(5+i,0), sharex=self.axes[0]))

        # configure figure size/layout and connect event handlers
        self.fig.set_size_inches(8, 5+(1.5*numIndicators))  # 1.5-inch per indicator
        plt.subplots_adjust(top=0.99, bottom=0.05, wspace=0, hspace=0.05)
        self.fig.canvas.mpl_connect("resize_event", self._handleResize)
        self.fig.canvas.mpl_connect("close_event", self._handleClose)
        self.fig.canvas.mpl_connect("scroll_event", self._handleScroll)
        self.fig.canvas.mpl_connect("button_press_event", self._mouseClick)
        self.fig.canvas.mpl_connect("button_release_event", self._mouseRelease)
        self.fig.canvas.mpl_connect("key_press_event", self._handleKey)

        # Cursor
        self.cursor = mlines.Line2D([-1, -1], [0, 100000], linewidth=1, color=Colors.cursor)
        self.cursor1 = mlines.Line2D([-1, -1], [0, 100000], linewidth=1, color=Colors.cursor)
        self.axes[0].add_line(self.cursor)
        self.axes[1].add_line(self.cursor1)
        self.fig.canvas.mpl_connect("motion_notify_event", self._mouseMove)
        self.fig.canvas.mpl_connect("axes_enter_event", self._mouseEnter)
        self.fig.canvas.mpl_connect("axes_leave_event", self._mouseLeave)
        self.cursorText0 = self.axes[0].text(-0.75, 0, "", fontsize=8, color=Colors.text)
        self.cursorText1 = self.axes[1].text(-0.75, 0, "", fontsize=8, color=Colors.text)
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
        self.legendLabels = []
        self.legend = None

        # price vars
        self.candlesticks = ([],[])
        self.ohlc = []
        self.hiLine = None
        self.hiText = None
        self.loLine = None
        self.loText = None
        self.title = None
        self.fibs = [[],[]]
        self.fibOn = True

        # misc vars
        self.timestamps = []                # store epoch timestamps of every interval
        self.currInt = 0                    # index of the current interval
        self.loaded = False                 # whether or not history was loaded and drawn
        self.useCBP = useCBP                # coinbasePro is being used
        self.xlims = [100 - 16, 100 + 16]   # bounds of the x-axis
        self.pan = False                    # figure is in panning mode
        self.lastMouseX = 0                 # last record x-position of the mouse
        self.backgrounds = None             # canvas image for each axis to draw more efficently [blank canvas, canvas with non-changing objects drawn]
        self.redraw = True                  # figure should be redrawn efficiently (reload background_0, resave background_1)
        self.fullRedraw = False             # figure and all objects should be completely redrawn
        self.resaveBG = False               # canvas backgrounds need to be resaved (e.g. figure resized)

        # indicators
        self.indicators = []
        for i,arg in enumerate(args):
            lowArg = arg.lower()
            if lowArg == "macd":
                self.indicators.append(MACD(self.axes[2+i], self.xlims))
            elif lowArg == "rsi":
                self.indicators.append(RSI(self.axes[2+i], self.xlims))
            else:
                print("WARNING: No indicator named '%s'" % arg)

        # Initialize title
        self.title = self.axes[0].text(95, 0.01,
                                   "Loading History...",
                                   fontsize=12,
                                   color=Colors.text)

        # volume default attributes
        self.axes[1].set_ylabel("Volume (%s)" % coinPair)
        self.axes[1].set_facecolor(Colors.background)

        # price default attributes
        self.axes[0].set_ylabel("Price (USD)")
        self.axes[0].yaxis.grid(which="major", linestyle="--", color=Colors.grid_lines)
        self.axes[0].set_facecolor(Colors.background)

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
        pass

    def _handleResize(self, event):
        if self.loaded:
            self.resaveBG = True
            self.fullRedraw=True

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
            if self.fibOn:
                for txt in self.fibs[1]:
                    txt.set_text("")
                self.fibOn = False
            else:
                self.fibOn = True
                self.updateFibLevels()
                
            self.fullRedraw = True

    def _mouseClick(self, event):
        self.pan = True
        self.lastMouseX = event.x

    def _mouseRelease(self, event):
        self.pan = False

    def _mouseEnter(self, event):
        self.cursorOn = True
        self.pan = False

    def _mouseLeave(self, event):
        self.cursorOn = False
        self.cursorText0.set_text("")
        self.cursorText1.set_text("")
        self.cursor.set_xdata([-1, -1])
        self.cursor1.set_xdata([-1, -1])

        self.pan = False
    
    def _mouseMove(self, event):
        if not self.loaded: return          
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
            self.cursor1.set_ydata([0, max(self.vol[0])*1.1])
            self._updateCursorText(x)


    # ----- Private Functions ----- #
    def _initHiLoLevels(self):     
        xpos = self._pixelsToPoints(10)
        
        maxHi = self.getHighestPrice()
        self.hiLine, = self.axes[0].plot(self.xlims,
                                  [maxHi, maxHi],
                                  linestyle="--",
                                  color=Colors.green,
                                  linewidth=0.5)
        self.hiText = self.axes[0].text(self.xlims[1] + xpos,
                                   maxHi,
                                   "%.2f" % maxHi,
                                   fontsize=9,
                                   color=Colors.green)
        
        minLo = self.getLowestPrice()
        self.loLine, = self.axes[0].plot(self.xlims,
                                  [minLo, minLo],
                                  linestyle="--",
                                  color=Colors.red,
                                  linewidth=0.5)
        self.loText = self.axes[0].text(self.xlims[1] + xpos,
                                   minLo,
                                   "%.2f" % minLo,
                                   fontsize=9,
                                   color=Colors.red)

        buf = (maxHi - minLo) * 0.12
        self.axes[0].set_ylim(minLo - buf, maxHi + buf)

        # initialize fib levels
        if self.fibOn:
            for i in range(6):
                temp, = self.axes[0].plot([0,0], [0,0], linestyle="--", color=Colors.fib_levels, linewidth=0.4)
                temp2 = self.axes[0].text(self.xlims[1]+xpos,0,"",fontsize=9,color=Colors.fib_levels)
                self.fibs[0].append(temp)
                self.fibs[1].append(temp2)

    def _initCandlesticks(self):
        self.candlesticks = candle(self.axes[0], self.ohlc, width=0.5, colorup=Colors.green, colordown=Colors.red)

    def _initVolBars(self):
        numEx = len(self.vol)
        self.volBars.append(self.axes[1].bar(
                    range(self.currInt-len(self.vol[0])+1,self.currInt+1),
                    self.vol[0],
                    linewidth=1).patches)
        if self.showVolBreakdown:
            for i in range(1,numEx):
                self.volBars.append(self.axes[1].bar(
                    range(self.currInt-len(self.vol[i])+1,self.currInt+1),
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

        self.buyEmaPlt, = self.axes[1].plot(
            range(self.currInt+1), self.buyEma[1:], "-", c=Colors.buyEMA, linewidth=0.9)
        self.sellEmaPlt, = self.axes[1].plot(
            range(self.currInt+1), self.sellEma[1:], "-", c=Colors.sellEMA, linewidth=0.9)

        self.volRatioText = self.axes[1].text(0, 0, "", fontsize=9, color=Colors.text)

    def _calcEMAfromHist(self, data, histCnt):
        numEx = len(data)
        emaVolStart = min(200, histCnt + self.volEmaPd)
        
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

    def _adjustXlims(self, dx0, dx1):
        # get hi/lo prices before panning
        tempHi = self.getHighestPrice()
        tempLo = self.getLowestPrice()

        # shift the xlims
        self.xlims = [int(round(self.xlims[0]+dx0)), int(round(self.xlims[1]+dx1))]
        for ax in self.axes:
            ax.set_xlim(self.xlims)

        # get hi/lo prices after panning
        newHi = self.getHighestPrice()
        newLo = self.getLowestPrice()
        self.updateHiLevel(hi=newHi, lo=newLo)
        self.updateLoLevel(hi=newHi, lo=newLo)
        self.updateFibLevels(hi=newHi, lo=newLo)

        # if hi/lo price changed, do a full redraw to redraw axis labels and hi/lo text
        if tempHi != newHi or tempLo != newLo:
            self.fullRedraw = True
        self.redraw = True           

    def _updateCursorText(self, x):
        if 0 <= x <= self.currInt:
            timeStr = time.strftime("%d %b %Y %H:%M", time.localtime(self.timestamps[x]))
            self.cursorText0.set_text(
                "%s    Open: %.2f, High: %.2f, Low: %.2f, Close: %.2f" %
                (timeStr, self.ohlc[x][1], self.ohlc[x][2], self.ohlc[x][3], self.ohlc[x][4]))
            self.cursorText0.set_y(
                self.getHighestPrice() + (self.getHighestPrice() - self.getLowestPrice()) * 0.04)
            self.cursorText0.set_x(self.xlims[0]+0.25)
            
            self.cursorText1.set_text("Volume: %.8f (%.1f%% Buys)" % (self.vol[0][x], self.volRatio[x]*100))
            self.cursorText1.set_y(max(self.vol[0][max(0, self.xlims[0]):min(len(self.vol[0]), self.xlims[1])]))
            self.cursorText1.set_x(self.xlims[0]+0.25)
        else:
            self.cursorText0.set_text("")
            self.cursorText1.set_text("")

    def _getPlotWidthPixels(self):
        # (figure width in inches * dots/inch) * plot takes up 77.4% of the figure width = plot width in pixels
        return (self.fig.get_size_inches()*self.fig.dpi)[0] * 0.774

    def _pixelsToPoints(self, px):
        return px * (self.xlims[1]-self.xlims[0]) / self._getPlotWidthPixels()


    # ----- MPL Figure attribute functions ----- #
    def setVolBreakdown(self, show):
        if show:
            self.setVolumeLegend(self.legendLabels)
        elif self.showVolBreakdown:
            self.axes[1].get_legend().remove()
        self.showVolBreakdown = show

    def setVolumeLegend(self, labels):
        self.legendLabels = labels
        if self.showVolBreakdown:
            self.legend = self.axes[1].legend([x[0] for x in self.volBars], self.legendLabels,
                                              fancybox=False,
                                              shadow=False,
                                              frameon=False,
                                              loc="lower right")
            for text in self.legend.get_texts():
                text.set_color(Colors.text)

    def setTitle(self, title):
        try:
            self.title.set_text(title)
            ypos = self.axes[0].get_ylim()[0]
            ypos = ypos + (self.getLowestPrice() - ypos) * 0.2
            self.title.set_y(ypos)
            self.title.set_x((self.xlims[0] + self.xlims[1])/2 - (self.xlims[1] - self.xlims[0])/6)
        except:
            print("Could not update title")


    # ----- Only run at startup ----- #
    def loadHistory(self, data, histCnt):
        numEx = len(data)

        # initialize vol list for each exchange
        for i in range(numEx):
            self.vol.append([])
        self.buyEma = [0]
        self.sellEma = [0]

        # calc volume EMAs from history
        if False and self.useCBP: self._calcEMAfromHist(data[:-1], histCnt) # TODO: REMOVE FALSE
        else: self._calcEMAfromHist(data, histCnt)

        exDown = [[] for i in range(numEx)]
        # shift data when needed if exchange was down (to reallign)
        for i in range(histCnt):
            avgT = sum([x[i][0] for x in data]) / numEx
            for j in range(numEx):
                # timestamp is less than the average
                if data[j][i][0] < avgT:
                    # add a dummy entry to shift the data
                    data[j] = data[j][:i] + [[0]*6] + data[j][i:]
                    
        # traverse history from old to new data
        for i in range(histCnt):
            # candle data is sorted new->old, so index in reverse order
            idx = histCnt-1-i

            # Check timestamps to see if an exchange was down during that time
            self.timestamps.append(max([x[idx][0] for x in data]))
            invalid = []
            avgT = sum([x[idx][0] for x in data]) / numEx
            for j in range(numEx):
                if data[j][idx][0] < avgT:
                    invalid.append(data[j])
                    exDown[j].append(i)
            #invalid = [x for x in data if x[idx][0] < avgT]

            # sum volume from all exchanges
            for j in range(numEx):           
                self.vol[j].append( sum([float(x[idx][5]) for x in data[j:] if x not in invalid]))

            # calc buy volume percentage
            if len(data[0][0]) < 10 or data[0] in invalid:
                self.volRatio.append(0.5)
            else:
                self.volRatio.append( (float(data[0][idx][9]) / float(data[0][idx][5])))

            # update volume EMAs
            self.buyEma.append((self.volRatio[i] * self.vol[0][i]) * self.volEmaWt +\
                               self.buyEma[-1] * (1 - self.volEmaWt))
            self.sellEma.append(((1 - self.volRatio[i]) * self.vol[0][i]) * self.volEmaWt +\
                               self.sellEma[-1] * (1 - self.volEmaWt))
                    
            # append ohlc candle data (but ignore coinbase which may not be up-to-date)
            self.ohlc.append([i] + [0]*4)
            for j in range(1,5):
                if False and self.useCBP: # TODO: REMOVE FALSE
                    self.ohlc[i][j] =\
                    sum([float(x[idx][j]) for x in data[:-1] if x not in invalid]) /\
                    (len([x for x in data[:-1] if x not in invalid]))
                else:
                    self.ohlc[i][j] =\
                    sum([float(x[idx][j]) for x in data if x not in invalid]) /\
                    (len(data)-len(invalid))


        # initialize chart objects
        if len(self.ohlc) != 100:
            self.xlims = [len(self.ohlc) - 16, len(self.ohlc) + 16]
            for ax in self.axes:
                ax.set_xlim(self.xlims)

        # set axis lims
        self._initHiLoLevels()
        maxVol = max(self.vol[0][max(0, self.xlims[0]):self.xlims[1]])
        self.axes[1].set_ylim(0, maxVol*1.06)
            
        # "save" backgrounds of axes (before actual data and patches are plotted)
        self.fig.canvas.draw()
        self.backgrounds = [[self.fig.canvas.copy_from_bbox(ax.bbox), None] for ax in self.axes]

        # update title
        self.setTitle("Loading Chart Objects...")
        self.fig.canvas.draw()
        
        # draw candlestick and volume charts
        self.currInt = histCnt - 1
        self._initCandlesticks()
        self._initVolBars()
        self.updateFibLevels()

        # Load history for indicators
        if False and self.useCBP: # TODO: REMOVE FALSE
            for ind in self.indicators:
                ind.loadHistory(self.ohlc, data[:-1], histCnt)
        else:
            for ind in self.indicators:
                ind.loadHistory(self.ohlc, data, histCnt)

        # plot indicator data
        for ind in self.indicators:
                ind.initPlot(self.currInt)

        # draw everything to start
        self.refresh(fullRedraw=True)

        self.loaded = True
        return exDown


    # ----- Everything Else --- #
    def incCurrIntvl(self):
        # update indicators
        for ind in self.indicators:
            ind.update(self.ohlc, self.currInt, retain=False)

        # update chart limits
        self.currInt += 1
        if self.currInt >= self.xlims[1]-1:
            self.xlims = [self.xlims[0]+1, self.xlims[1]+1]
            for ax in self.axes:
                ax.set_xlim(self.xlims)
            self.updateHiLevel()
            self.updateLoLevel()

        # update candlestick chart
        self.ohlc.append([self.currInt] + [0]*4)
        self.timestamps.append([0])
        self.createCandlestick()

        # update volume chart
        for v in self.vol:
            v.append(0)
        self.volRatio.append(0)
        self.createBar()
        self.buyEma.append(0)
        self.sellEma.append(0)

        self.redraw = True

    # --- Candle/Price related functions --- #
    def updateCandlesticks(self, data):
        for i in range(1,5):
            # TODO: REMOVE FALSE
            if False and self.useCBP: self.ohlc[self.currInt][i] = sum([float(x[0][i]) for x in data[:-1]]) / (len(data)-1)
            else: self.ohlc[self.currInt][i] = sum([float(x[0][i]) for x in data]) / len(data)
        self.timestamps[self.currInt] = data[0][0][0]
            #self.ohlc[self.currInt][i] = sum([float(x[0][i]) for x in data]) / len(data)

    def createCandlestick(self):
        # create new candlestick and add it to the axis
        self.candlesticks[0].append(mlines.Line2D([self.currInt, self.currInt], [0, 0], linewidth=0.5))
        self.axes[0].add_line(self.candlesticks[0][-1])
        self.candlesticks[1].append(mpatches.Rectangle((self.currInt - 0.25, 0), width=0.5, height=0))
        self.axes[0].add_patch(self.candlesticks[1][-1])
        
    def drawCandlesticks(self):
        try:
            self.candlesticks[0][-1].set_ydata([self.ohlc[-1][2], self.ohlc[-1][3]])
            # open > close
            if self.ohlc[-1][1] > self.ohlc[-1][4]:
                self.candlesticks[1][-1].set_y(self.ohlc[-1][4])
                self.candlesticks[1][-1].set_height(self.ohlc[-1][1] - self.ohlc[-1][4])
                self.candlesticks[1][-1].set_color(Colors.red)
                self.candlesticks[0][-1].set_color(Colors.red)
            # open <= close
            else:
                self.candlesticks[1][-1].set_y(self.ohlc[-1][1])
                self.candlesticks[1][-1].set_height(self.ohlc[-1][4] - self.ohlc[-1][1])
                self.candlesticks[1][-1].set_color(Colors.green)
                self.candlesticks[0][-1].set_color(Colors.green)              
        except Exception as e:
            print("Could not draw candlesticks:", e)
            
    def getHighestPrice(self):
        idx = int(max(0, self.xlims[0]))
        idx2 = int(min(len(self.ohlc), self.xlims[1]))
        return max([x[2] for x in self.ohlc[idx:idx2]])

    def getLowestPrice(self):
        idx = int(max(0, self.xlims[0]))
        idx2 = int(min(len(self.ohlc), self.xlims[1]))
        return min([x[3] for x in self.ohlc[idx:idx2]])
    
    def updateHiLevel(self, hi=None, lo=None):
        if hi == None: hi = self.getHighestPrice()
        if lo == None: lo = self.getLowestPrice()
        
        xpos = self._pixelsToPoints(10)
        
        self.hiLine.set_data([-1, self.xlims[1]], [hi, hi])
        self.hiText.set_text("%.2f" % hi)
        self.hiText.set_position((self.xlims[1] + xpos, hi))
        buf = (hi - lo) * 0.12
        self.axes[0].set_ylim(self.axes[0].get_ylim()[0], hi + buf)
 
    def updateLoLevel(self, hi=None, lo=None):
        if hi == None: hi = self.getHighestPrice()
        if lo == None: lo = self.getLowestPrice()
        if lo == 0: return

        xpos = self._pixelsToPoints(10)
        
        self.loLine.set_data([-1, self.xlims[1]], [lo, lo])  
        self.loText.set_text("%.2f" % lo)
        self.loText.set_position((self.xlims[1] + xpos, lo))
        buf = (hi - lo) * 0.12
        self.axes[0].set_ylim(lo - buf, self.axes[0].get_ylim()[1])

    def updateFibLevels(self, hi=None,lo=None):
        if not self.fibOn: return
            
        if hi == None: hi = self.getHighestPrice()
        if lo == None: lo = self.getLowestPrice()
        diff = hi - lo

        xpos = self._pixelsToPoints(10)
      
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
        self.fibs[1][0].set_position((self.xlims[1]+xpos, fib23_6))
        self.fibs[1][1].set_text("%.2f" % fib38_2)
        self.fibs[1][1].set_position((self.xlims[1]+xpos, fib38_2))
        self.fibs[1][2].set_text("%.2f" % fib50_0)
        self.fibs[1][2].set_position((self.xlims[1]+xpos, fib50_0))
        self.fibs[1][3].set_text("%.2f" % fib61_8)
        self.fibs[1][3].set_position((self.xlims[1]+xpos, fib61_8))
        self.fibs[1][4].set_text("%.2f" % fib78_6)
        self.fibs[1][4].set_position((self.xlims[1]+xpos, fib78_6))

    # --- Volume related functions --- #
    def updateCurrentVol(self, data):
        numEx = len(data)
        # bar graph is stacked so each vol is the sum of all vols proceeding it
        # (i.e. vol[0] is sum of all exchanges, vol[-1] is the volume of a single exchange)
        for i in range(numEx):
            self.vol[i][self.currInt] = sum([float(x[0][5]) for x in data[i:]])
        if len(data[0][0]) < 10:    # in case binance data isn't included
            self.volRatio[self.currInt] = 0.5
        else:
            self.volRatio[self.currInt] = (float(data[0][0][9]) / float(data[0][0][5]))

        self.buyEma[-1] = (self.volRatio[self.currInt] * self.vol[0][self.currInt]) * self.volEmaWt +\
                             self.buyEma[self.currInt] * (1 - self.volEmaWt)
        self.sellEma[-1] = ((1 - self.volRatio[self.currInt]) * self.vol[0][self.currInt]) * self.volEmaWt +\
                             self.sellEma[self.currInt] * (1 - self.volEmaWt)

    def createBar(self):
        for i in range(len(self.volBars)):
            self.volBars[i].append(mpatches.Rectangle((self.currInt - 0.4, 0), width=0.8, height=0, color=self.volBars[i][self.currInt-1].get_fc()))
            self.axes[1].add_patch(self.volBars[i][-1])

    def drawVolBars(self):
        try:
            numEx = len(self.vol)
            self.volBars[0][self.currInt].set_height(self.vol[0][self.currInt])
            if self.volRatio[self.currInt] > 0.5:
                if self.showVolBreakdown:
                    self.volBars[0][self.currInt].set_edgecolor(Colors.green)
                else:
                    self.volBars[0][self.currInt].set_color(Colors.green)
            elif self.volRatio[self.currInt] < 0.5:
                if self.showVolBreakdown:
                    self.volBars[0][self.currInt].set_edgecolor(Colors.red)
                else:
                    self.volBars[0][self.currInt].set_color(Colors.red)
            else:
                if self.showVolBreakdown:
                    self.volBars[0][self.currInt].set_edgecolor(Colors.blue)
                else:
                    self.volBars[0][self.currInt].set_color(Colors.blue)
                    
            if self.showVolBreakdown:
                for i in range(1, numEx):
                    self.volBars[i][self.currInt].set_height(self.vol[i][self.currInt])
                
            # Update y-axis limits to be just above the max volume
            startIdx = max(0, self.xlims[0])
            maxVol = max(self.vol[0][startIdx:self.xlims[1]])
            self.axes[1].set_ylim(0, maxVol*1.06)

            # Draw EMA lines of buy and sell volume
            self.buyEmaPlt.set_data(range(self.currInt+1), self.buyEma[1:])
            self.sellEmaPlt.set_data(range(self.currInt+1), self.sellEma[1:])

            # Calculate the percentage of buys from total volume (in current window)
            buyRat = 0
            for i in range(startIdx, self.currInt + 1):
                buyRat += self.volRatio[i] * self.vol[0][i]
            buyRat /= sum([x for x in self.vol[0][startIdx:]])
            
            xloc = (self.xlims[1] - self.xlims[0])*0.94 + self.xlims[0]
            self.volRatioText.set_text("%.1f%%" % (buyRat * 100))
            self.volRatioText.set_position((xloc, maxVol*0.99))
        except Exception as e:
           print("Could not draw volume chart:", e)
           
    def setVol(self, ex, intvl, val):
        self.vol[ex][intvl] = val
        if ex == 0:
            self.volBars[0][intvl].set_height(val)
        elif self.showVolBreakdown:
            self.volBars[ex][intvl].set_height(val)

    def getVol(self, ex, intvl):
        return self.vol[ex][intvl]

    # --- Indicator functions --- #
    def updateIndicators(self, retain=True):
        for ind in self.indicators:
            ind.update(self.ohlc, self.currInt, retain)
        
    def drawIndicators(self):
        for ind in self.indicators:
            ind.xlims = self.xlims
            ind.draw(self.currInt)


    
    # --- Draw/show figure functions --- #
    def resaveBackground(self):
        # shift axes to hide chart objects
        for ax in self.axes:
            ax.set_xlim([-1,-0.5])
            
        # redraw the "blank" canvas
        hi = self.getHighestPrice()
        lo = self.getLowestPrice()
        self.updateHiLevel(hi=hi,lo=lo)
        self.updateLoLevel(hi=hi,lo=lo)
        self.fig.canvas.draw()

        # copy the blank canvas
        for i in range(len(self.axes)):
            self.backgrounds[i][0] = self.fig.canvas.copy_from_bbox(self.axes[i].bbox)

        # shift axes back to normal
        for ax in self.axes:
            ax.set_xlim(self.xlims)

        # reset fibs
        self.updateFibLevels()
        
    def efficientDraw(self):
        # Axis 0 (price)
        if self.redraw: # redraw viewing window in event of zooming/panning
            # restore the blank canvas
            self.fig.canvas.restore_region(self.backgrounds[0][0])
            if self.fibOn:
                for fib in self.fibs[0]:
                    self.axes[0].draw_artist(fib)
            # draw all candlesticks in current viewing window (within xlims)
            idx0 = max(0, self.xlims[0])
            idx1 = min(self.xlims[1]+1, len(self.candlesticks[0]))
            for i in range(idx0, idx1):
                self.axes[0].draw_artist(self.candlesticks[0][i])
                self.axes[0].draw_artist(self.candlesticks[1][i])
                if i + 2 == idx1:
                    # save the canvas that has all candles except most recent (these objects won't change)
                    self.backgrounds[0][1] = self.fig.canvas.copy_from_bbox(self.axes[0].bbox)
        else:
            # restore the canvas with old candles
            self.fig.canvas.restore_region(self.backgrounds[0][1])
            idx = min(self.currInt, self.xlims[1]+1)
            # only redraw the newest (live) candle
            self.axes[0].draw_artist(self.candlesticks[0][idx])
            self.axes[0].draw_artist(self.candlesticks[1][idx])
            
        # draw the remaining chart objects (cursor, text, etc.)
        self.axes[0].draw_artist(self.cursor)
        self.axes[0].draw_artist(self.cursorText0)
        self.axes[0].draw_artist(self.title)

        # blit the canvas within the axis bounding box to refresh with the redrawn objects
        self.fig.canvas.blit(self.axes[0].bbox)

        # REPEAT ABOVE PROCESS FOR ALL AXES
        
        # Axis 1 (volume)
        if self.redraw:
            self.fig.canvas.restore_region(self.backgrounds[1][0])
            if self.showVolBreakdown:
                self.axes[1].draw_artist(self.legend)
            idx0 = max(0, self.xlims[0])
            idx1 = min(self.xlims[1]+1, len(self.volBars[0]))
            for i in range(idx0, idx1):
                self.axes[1].draw_artist(self.volBars[0][i])
                if self.showVolBreakdown:
                    for j in range(1, len(self.volBars)):
                        self.axes[1].draw_artist(self.volBars[j][i])
                if i + 2 == idx1:
                    self.backgrounds[1][1] = self.fig.canvas.copy_from_bbox(self.axes[1].bbox)
        else:
            self.fig.canvas.restore_region(self.backgrounds[1][1])
            idx = min(self.currInt, self.xlims[1]+1)
            self.axes[1].draw_artist(self.volBars[0][idx])
            if self.showVolBreakdown:
                for j in range(1, len(self.volBars)):
                    self.axes[1].draw_artist(self.volBars[j][idx])
        self.axes[1].draw_artist(self.cursor1)
        self.axes[1].draw_artist(self.cursorText1)
        self.axes[1].draw_artist(self.buyEmaPlt)
        self.axes[1].draw_artist(self.sellEmaPlt)
        self.axes[1].draw_artist(self.volRatioText)
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
            
    def update(self, data):
        self.updateCurrentVol(data)
        self.drawVolBars()

        # update price chart
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
            self.fullRedraw = True
        if tempLo != newLo:
            self.updateLoLevel(hi=newHi, lo=newLo)
            self.updateFibLevels(hi=newHi, lo=newLo)
            self.fullRedraw = True

        # update technical indicators
        self.updateIndicators()
        self.drawIndicators() 
        
    def show(self):
        plt.show(block=False)
    
    def refresh(self, fullRedraw=False):
        t0 = time.time()

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
        #print("%.1f fps" % (1/(t1-t0)))#*1000)
