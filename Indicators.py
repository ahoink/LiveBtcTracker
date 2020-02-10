import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

class MACD():

    def __init__(self, ax, xlims, ema1=26, ema2=12, ema3=9):
        self.macdBars = []
        self.macd = []
        self.ema1 = 0
        self.ema2 = 0
        self.ema3 = 0
        self.ema1pd = ema1
        self.ema2pd = ema2
        self.ema3pd = ema3
        self.ema1Wt = 2 / (self.ema1pd+1)
        self.ema2Wt = 2 / (self.ema2pd+1)
        self.ema3Wt = 2 / (self.ema3pd+1)

        self.deriv = []
        self.derivLine = None

        self.ax = ax
        self.ax.set_facecolor("#1e1e1e")
        self.ax.set_ylabel("MACD (%d, %d, %d)" % (self.ema2pd, self.ema1pd, self.ema3pd),
                           fontsize=9)
        self.xlims = xlims
                           
        self.green = "#22d615"
        self.red = "#ea2222"                

    def initPlot(self, i):
        self.macdBars = self.ax.bar(range(i-len(self.macd)+1, i+1), self.macd).patches
        for bar,v in zip(self.macdBars, self.macd):
            bar.set_height(v)
            if v < 0:
                bar.set_color(self.red)
            else:
                bar.set_color(self.green)
        self.derivLine, = self.ax.plot(range(i-len(self.deriv)+1, i+1), self.deriv, "-", c="white", linewidth=0.7)
            

    def calcEMAfromHistory(self, data, histCnt):
        numEx = len(data)
        ema1Start = min(200, histCnt + self.ema1pd+self.ema3pd)
        ema2Start = min(ema1Start - (self.ema1pd-self.ema2pd), histCnt + self.ema2pd+self.ema3pd)
        
        # First EMA value is a SMA
        # calculate SMA for first X intervals of emaX
        for i in range(self.ema1pd):
            # price ema 1
            idx = ema1Start-1-i
            self.ema1 += sum([float(x[idx][4]) for x in data]) / numEx
            # price ema 2
            if i < self.ema2pd:
                idx = ema2Start-1-i
                self.ema2 += sum([float(x[idx][4]) for x in data]) / numEx
            
        self.ema1 /= self.ema1pd
        self.ema2 /= self.ema2pd
        self.ema3 += (self.ema2 - self.ema1)

        # calculate SMA of (ema2-ema1)
        for i in range(self.ema3pd-1,0,-1):
            idx = histCnt+i
            p = sum([float(x[idx][4]) for x in data]) / numEx
            self.ema1 = p * self.ema1Wt + self.ema1 * (1 - self.ema1Wt)
            self.ema2 = p * self.ema2Wt + self.ema2 * (1 - self.ema2Wt)
            self.ema3 += (self.ema2 - self.ema1)
        self.ema3 /= self.ema3pd

    def loadHistory(self, ohlc, data, histCnt):

        # calculate EMAs for history data before displayed data
        self.calcEMAfromHistory(data, histCnt)

        for i in range(histCnt):
            idx = histCnt - i - 1
            if idx == 0:
                self.macd.append(0)
                self.deriv.append(0)
                continue
            self.ema1 = ohlc[i][4] * self.ema1Wt + self.ema1 * (1-self.ema1Wt)
            self.ema2 = ohlc[i][4] * self.ema2Wt + self.ema2 * (1-self.ema2Wt)
            self.ema3 = (self.ema2-self.ema1) * self.ema3Wt + self.ema3 * (1-self.ema3Wt)
            self.macd.append((self.ema2-self.ema1) - self.ema3)
            if i >= 2:
                self.deriv.append((self.macd[i] - self.macd[i-2]) / 2)

    def update(self, ohlc, currInt, retain=True):
        tempEMA1 = ohlc[currInt][4] * self.ema1Wt + self.ema1 * (1 - self.ema1Wt)
        tempEMA2 = ohlc[currInt][4] * self.ema2Wt + self.ema2 * (1 - self.ema2Wt)
        tempEMA3 = (tempEMA2 - tempEMA1) * self.ema3Wt + self.ema3 * (1 - self.ema3Wt)
        self.macd[currInt] = (tempEMA2 - tempEMA1) - tempEMA3
        self.deriv[-1] = (self.macd[-1] - self.macd[-3]) / 2

        if not retain:
            self.ema1 = tempEMA1
            self.ema2 = tempEMA2
            self.ema3 = tempEMA3
            self.addBar(currInt+1)
            self.deriv.append(0)

    def addBar(self, i):
        self.macd.append(0)
        self.macdBars.append(mpatches.Rectangle((i - 0.4, 0), width=0.8, height=0))
        self.ax.add_patch(self.macdBars[-1])

    def draw(self, currInt):
        try:
            self.macdBars[currInt].set_height(self.macd[currInt])
            if self.macd[currInt] < 0:
                self.macdBars[currInt].set_color(self.red)
            else:
                self.macdBars[currInt].set_color(self.green)

            maxMacd = max(self.macd[max(0, self.xlims[0]):self.xlims[1]])
            minMacd = min(self.macd[max(0, self.xlims[0]):self.xlims[1]])
            maxDeriv = max(self.deriv[max(0, self.xlims[0]):self.xlims[1]])
            minDeriv = min(self.deriv[max(0, self.xlims[0]):self.xlims[1]])
            maxMacd = max(maxMacd, maxDeriv)
            minMacd = min(minMacd, minDeriv)
            buf = (maxMacd - minMacd) * 0.12
            self.ax.set_ylim(min(0, minMacd - buf), max(0, maxMacd+buf))

            self.derivLine.set_data(range(2,currInt+1), self.deriv)
        except Exception as e:
            print("Could not draw MACD:", e)

    def drawArtists(self, redraw):
        if redraw:
            idx0 = max(0, self.xlims[0])
            idx1 = min(self.xlims[1]+1, len(self.macdBars)-1)
            for i in range(idx0, idx1):
                self.ax.draw_artist(self.macdBars[i])
        else:
            self.ax.draw_artist(self.macdBars[(min(self.xlims[1]+1, len(self.macdBars)-1))])
            self.ax.draw_artist(self.derivLine)

class RSI():

    def __init__(self, ax, xlims):
        self.avgGain = 0
        self.avgLoss = 0
        self.rsi = []
        self.xlims = xlims
        self.rsiPlot = None
        self.hiThresh = None
        self.loThresh = None
        self.rsiText = None
        self.over_fill = []
        
        self.ax = ax
        self.ax.set_facecolor("#1e1e1e")
        self.ax.set_ylabel("RSI (14)", fontsize=8)
        self.ax.set_ylim(0, 100)


    def initPlot(self, i):
        self.rsiPlot, = self.ax.plot(range(i+1), self.rsi, "-", c="yellow", linewidth=0.9) 
        self.hiThresh, = self.ax.plot(self.xlims, [70,70], "--", c="white", linewidth=0.5)
        self.loThresh, = self.ax.plot(self.xlims, [30,30], "--", c="white", linewidth=0.5)
        self.rsiText = self.ax.text(0, 0, "", fontsize=9, color="#cecece")

        # fill areas that are overbought or oversold
        yhi = [70]*len(self.rsi)
        ylo = [30]*len(self.rsi)
        overbought = [y1 > y2 for y1,y2 in zip(self.rsi, yhi)]
        oversold = [y1 < y2 for y1,y2 in zip(self.rsi, ylo)]
        self.over_fill.append(self.ax.fill_between(range(i+1), self.rsi, yhi, where=overbought, facecolor="red", interpolate=True))
        self.over_fill.append(self.ax.fill_between(range(i+1), self.rsi, ylo, where=oversold, facecolor="blue", interpolate=True))
        #print(self.over_fill[0])

        
    def loadHistory(self, ohlc, data, histCnt):

        # calculate rsi for history data that occurs before the displayed data
        n = min([len(d) for d in data]) #(data[0])
        for i in range(n - histCnt):
            idx = n-i-1
            tempOpen = sum([float(x[idx][1]) for x in data]) / len(data)
            tempClose = sum([float(x[idx][4]) for x in data]) / len(data)
            diff = tempClose - tempOpen
            if i < 14:
                if diff < 0:
                    self.avgLoss -= diff
                else:
                    self.avgGain += diff
                if i == 13:
                    self.avgGain /= 14
                    self.avgLoss /= 14
            else:
                if diff < 0:
                    self.avgLoss = (self.avgLoss * 13 - diff)
                    self.avgGain *= 13
                else:
                    self.avgGain = (self.avgGain * 13 + diff)
                    self.avgLoss *= 13
                self.avgGain /= 14
                self.avgLoss /= 14
        self.rsi.append(100 - (100 / (1 + (self.avgGain / self.avgLoss))))

        # calculate rsi for every interval of displayed data
        for i in range(len(ohlc)-1):
            diff = ohlc[i][4] - ohlc[i][1]
            if diff < 0:
                self.avgLoss = (self.avgLoss * 13 - diff)
                self.avgGain *= 13
            else:
                self.avgGain = (self.avgGain * 13 + diff)
                self.avgLoss *= 13
            self.avgGain /= 14
            self.avgLoss /= 14
            self.rsi.append(100 - (100 / (1 + (self.avgGain / self.avgLoss))))

    def update(self, ohlc, currInt, retain=True):
        tempGain = 0
        tempLoss = 0
        diff = ohlc[currInt][4] - ohlc[currInt][1]
        if diff < 0:
            tempLoss = -diff
        else:
            tempGain = diff
        tempGain = (self.avgGain * 13 + tempGain) / 14
        tempLoss = (self.avgLoss * 13 + tempLoss) / 14

        self.rsi[-1] = 100 - (100 / (1 + (tempGain / tempLoss)))

        if not retain:
            self.avgGain = tempGain
            self.avgLoss = tempLoss
            self.rsi.append(0)

    def draw(self, currInt):
        self.rsiPlot.set_data(range(currInt+1), self.rsi)
        self.hiThresh.set_xdata(self.xlims)
        self.loThresh.set_xdata(self.xlims)
        self.rsiText.set_text("%.2f" % self.rsi[-1])
        self.rsiText.set_position(((self.xlims[1] - self.xlims[0])*0.94 + self.xlims[0], 88))

        # fill areas that are overbought or oversold
        if self.rsi[currInt] < 30: 
            ylo = [30]*len(self.rsi)
            oversold = [y1 < y2 for y1,y2 in zip(self.rsi, ylo)]
            self.over_fill[1].remove()
            self.over_fill[1] = self.ax.fill_between(range(currInt+1), self.rsi, ylo, where=oversold, facecolor="blue", interpolate=True)
        elif self.rsi[currInt] > 70:
            yhi = [70]*len(self.rsi)
            overbought = [y1 > y2 for y1,y2 in zip(self.rsi, yhi)]
            self.over_fill[0].remove()
            self.over_fill[0] = self.ax.fill_between(range(currInt+1), self.rsi, yhi, where=overbought, facecolor="red", interpolate=True)

    def drawArtists(self, redraw):
        if redraw:
            self.ax.draw_artist(self.hiThresh)
            self.ax.draw_artist(self.loThresh)
            self.ax.draw_artist(self.over_fill[0])
            self.ax.draw_artist(self.over_fill[1])
        else:
            self.ax.draw_artist(self.rsiPlot)
            self.ax.draw_artist(self.rsiText)
        
        
            
        
        
