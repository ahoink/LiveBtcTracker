import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from abc import ABC, abstractmethod

class Indicator(ABC):
# abstract Indicator class
# outlines functions required by indicator classes

    def __init__(self, ax, xlims):
        # All indicators have these attributes initialized
        # Make sure the indicator class calls super()
        self.ax = ax
        self.xlims = xlims
        self.active = False
        self.removeX = ax.text(0,0, "[X]", fontsize=9, color="#9e9e9e")
        
        self.ax.set_facecolor("#1e1e1e")

    @abstractmethod
    def initPlot(self, i):
        # plot data calculated in loadHistory on indicator axis
        # store the chart object (artist) as an attribute
        pass

    @abstractmethod
    def loadHistory(self, ohlc, data, vol, histCnt):
        # Calculate the indicator history using history data
        # store data as class attribute
        pass

    @abstractmethod
    def update(self, ohlc, vol, currInt, retain=True):
        # update the most recent data point
        # if not retain:
        #   <time period incremented>
        #   permanently store the most recent data point
        #   append new data point
        pass

    @abstractmethod
    def draw(self, currInt):
        # Update the chart object with the recently updated data point
        pass

    @abstractmethod
    def drawArtists(self, redraw):
        # Actually perform the drawing function
        # if redraw:
        #   draw artists that DON'T get redrawn every frame
        # else:
        #   draw artists that DO get redrawn every frame
        pass

    # --- Inherit these, don't override --- #
    def X_Clicked(self, event):
        return self.removeX.contains(event)[0]
    
class MACD(Indicator):

    def __init__(self, ax, xlims, ema1=26, ema2=12, ema3=9):
        super(MACD, self).__init__(ax, xlims)
        
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
        self.deriv_dx = 2
        self.green = "#22d615"
        self.red = "#ea2222"

        self.ax.set_ylabel("MACD (%d, %d, %d)" % (self.ema2pd, self.ema1pd, self.ema3pd), fontsize=9)      
    
    def initPlot(self, i):
        self.macdBars = self.ax.bar(range(i+1), self.macd).patches
        for bar,v in zip(self.macdBars, self.macd):
            bar.set_height(v)
            if v < 0: bar.set_color(self.red)
            else: bar.set_color(self.green)
        self.derivLine, = self.ax.plot(range(self.deriv_dx, i+1), self.deriv, "-", c="white", linewidth=0.7)           

    def calcEMAfromHistory(self, data, histCnt):
        numEx = len(data)
        ema1Start = histCnt + self.ema1pd+self.ema3pd
        ema2Start = min(ema1Start - (self.ema1pd-self.ema2pd), histCnt + self.ema2pd+self.ema3pd)
        
        # First EMA value is a SMA
        # calculate SMA for first X intervals of emaX
        for i in range(self.ema1pd):
            # price ema 1
            idx = ema1Start-1-i
            temp = [float(x[idx][4]) for x in data if x[idx][-1]] # data has been modified so last element is bool classifying its validity
            self.ema1 += sum(temp) / len(temp)
            # price ema 2
            if i < self.ema2pd:
                idx = ema2Start-1-i
                self.ema2 += sum(temp) / len(temp)#sum([float(x[idx][4]) for x in data]) / numEx
            
        self.ema1 /= self.ema1pd
        self.ema2 /= self.ema2pd
        self.ema3 += (self.ema2 - self.ema1)

        # calculate SMA of (ema2-ema1)
        for i in range(self.ema3pd-1,0,-1):
            idx = histCnt+i
            temp = [float(x[idx][4]) for x in data if x[idx][-1]]
            p = sum(temp) / len(temp)
            # ema = price * ema_weight + prev_ema * (1 - ema_weight)
            self.ema1 = p * self.ema1Wt + self.ema1 * (1 - self.ema1Wt)
            self.ema2 = p * self.ema2Wt + self.ema2 * (1 - self.ema2Wt)
            self.ema3 += (self.ema2 - self.ema1)
        self.ema3 /= self.ema3pd

    def loadHistory(self, ohlc, data, vol, histCnt):
        # MACD = EMA_9 of (EMA_12 - EMA_26)
        # Derivative = (MACD_i+2 - MACD_i) / 2
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
            if i >= self.deriv_dx:
                self.deriv.append((self.macd[i] - self.macd[i-self.deriv_dx]) / self.deriv_dx)

    def update(self, ohlc, vol, currInt, retain=True):
        tempEMA1 = ohlc[currInt][4] * self.ema1Wt + self.ema1 * (1 - self.ema1Wt)
        tempEMA2 = ohlc[currInt][4] * self.ema2Wt + self.ema2 * (1 - self.ema2Wt)
        tempEMA3 = (tempEMA2 - tempEMA1) * self.ema3Wt + self.ema3 * (1 - self.ema3Wt)
        self.macd[currInt] = (tempEMA2 - tempEMA1) - tempEMA3
        self.deriv[-1] = (self.macd[-1] - self.macd[-3]) / self.deriv_dx

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
            self.derivLine.set_data(range(self.deriv_dx,currInt+1), self.deriv)

            # find min and max values being plotted to set the bounds of the y-axis
            maxMacd = max(self.macd[max(0, self.xlims[0]):self.xlims[1]])
            minMacd = min(self.macd[max(0, self.xlims[0]):self.xlims[1]])
            maxDeriv = max(self.deriv[max(0, self.xlims[0]):self.xlims[1]])
            minDeriv = min(self.deriv[max(0, self.xlims[0]):self.xlims[1]])
            maxMacd = max(maxMacd, maxDeriv)
            minMacd = min(minMacd, minDeriv)
            buf = (maxMacd - minMacd) * 0.12
            self.ax.set_ylim(min(0, minMacd - buf), max(0, maxMacd+buf))

            if self.active: self.removeX.set_text("[X]")
            else: self.removeX.set_text("")
            self.removeX.set_position(((self.xlims[1] - self.xlims[0])*0.97 + self.xlims[0], min(0, minMacd-buf/2)))

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
            self.ax.draw_artist(self.removeX)

class RSI(Indicator):

    def __init__(self, ax, xlims):
        super(RSI, self).__init__(ax, xlims)
        
        self.avgGain = 0
        self.avgLoss = 0
        self.rsi = []
        self.lastPrice = 0
        self.xlims = xlims
        self.rsiPlot = None
        self.hiThresh = None
        self.loThresh = None
        self.rsiText = None
        self.over_fill = []
        
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
      
    def loadHistory(self, ohlc, data, vol, histCnt):
        #                        100
        # RSI = 100  -   --------------------
        #               (1 + avgGain/avgLoss)
        #
        # calculate rsi for history data that occurs before the displayed data
        n = min([len(d) for d in data]) #(data[0])
        for i in range(n - histCnt):
            idx = n-i-1
            temp = [float(x[idx][1]) for x in data if x[idx][-1]] # data has been modified so last element is bool classifying the validity
            tempOpen = sum(temp) / len(temp)
            temp = [float(x[idx][4]) for x in data if x[idx][-1]]
            tempClose = sum(temp) / len(temp)
            diff = tempClose - tempOpen
            # find average of first 14 periods
            if i < 14:
                if diff < 0:
                    self.avgLoss -= diff
                else:
                    self.avgGain += diff
                if i == 13:
                    self.avgGain /= 14
                    self.avgLoss /= 14
            # remaining periods = (prev_avg * 13 + current_diff) / 14
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

    def resetRSItime(self):
        gains = self.avgGain
        losses = self.avgLoss
        startRSI = self.rsi[-1]
        expectedTime = 0

        avgDiff = 0
        for i in range(1, len(self.rsi)):
            avgDiff += abs(self.rsi[i] - self.rsi[i-1])
        avgDiff /= (len(self.rsi) - 1)
        candles = int(abs(startRSI - 50) / avgDiff + 0.5)

        lastDiff = startRSI-self.rsi[-2]
        g_l = 100/((100/(1+gains/losses))-lastDiff)-1
        if lastDiff < 0:
            gains = gains*13/14
            losses = gains/g_l
        elif lastDiff > 0:
            losses = losses*13/14
            gains = losses*g_l
                
        gainOrLoss = 0
        if startRSI > 50: avgDiff *= -1
        for i in range(candles):
            g_l = 100/((100/(1+gains/losses))-avgDiff)-1
            if startRSI > 50:
                gains = gains*13/14
                tempL = gains/g_l
                gainOrLoss -= tempL*14 - 13*losses
                #print(g_l, gains, tempL, tempL*14 - 13*losses)
                losses = tempL
            elif startRSI < 50:
                losses = losses*13/14
                tempG = losses*g_l
                gainOrLoss += tempG*14 - 13*gains
                gains = tempG
        return candles, gainOrLoss

        tempRSI = startRSI
        while (tempRSI > 50 and startRSI > 50) or (tempRSI < 50 and startRSI < 50):
            if startRSI < 50:
                gains = (gains * 13 + avgDiff) / 14
                losses = losses * 13 / 14
                tempRSI += avgDiff
            elif startRSI > 50:
                gains = gains * 13 / 14
                losses = (losses * 13 + avgDiff) / 14
                tempRSI -= avgDiff
            #tempRSI = 100 - (100 / (1 + (gains / losses)))
            expectedTime += 1

        return expectedTime    

    def update(self, ohlc, vol, currInt, retain=True):
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
        self.lastPrice = ohlc[currInt][4]

        if not retain:
            self.avgGain = tempGain
            self.avgLoss = tempLoss
            self.rsi.append(0)

    def draw(self, currInt):
        rsit, dp = self.resetRSItime()
        self.rsiPlot.set_data(range(currInt+1), self.rsi)
        self.hiThresh.set_xdata(self.xlims)
        self.loThresh.set_xdata(self.xlims)
        self.rsiText.set_text("%.2f, %d, %.2f" % (self.rsi[-1], rsit, self.lastPrice+dp))
        self.rsiText.set_position(((self.xlims[1] - self.xlims[0])*0.82 + self.xlims[0], 88))

        if self.active: self.removeX.set_text("[X]")
        else: self.removeX.set_text("")
        self.removeX.set_position(((self.xlims[1] - self.xlims[0])*0.97 + self.xlims[0], 5))

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
            self.ax.draw_artist(self.removeX)

class OBV(Indicator):
    def __init__(self, ax, xlims):
        super(OBV, self).__init__(ax, xlims)
        
        self.obv = []
        self.obvPlt = None

        self.ax.set_ylabel("OBV", fontsize=8)
        self.ax.set_yticklabels([])
        
    def initPlot(self, i):
        self.obvPlt, = self.ax.plot(range(i+1), self.obv, "-", linewidth=0.9)
        self.ax.set_ylim(
            min(self.obv[max(self.xlims[0], 0):min(len(self.obv), self.xlims[1])]),
            max(self.obv[max(self.xlims[0], 0):min(len(self.obv), self.xlims[1])]))

    def loadHistory(self, ohlc, data, vol, histCnt):
        # OBV = prev_OBV - Volume     if red candle
        #        or
        # OBV = prevOBV + Volume      if green candle
        self.obv.append(0)
        for p,v in zip(ohlc, vol):
            temp = self.obv[-1]
            if p[4] > p[1]:
                self.obv.append(temp+v)
            elif p[4] < p[1]:
                self.obv.append(temp-v)
            else:
                self.obv.append(temp)
        self.obv = self.obv[1:]

    def update(self, ohlc, vol, currInt, retain=True):
        if ohlc[currInt][4] > ohlc[currInt][1]:
            self.obv[currInt] = self.obv[currInt-1] + vol[currInt]
        elif ohlc[currInt][4] < ohlc[currInt][1]:
            self.obv[currInt] = self.obv[currInt-1] - vol[currInt]
        else:
            self.obv[currInt] = self.obv[currInt-1]

        if not retain:
            self.obv.append(0)

    def draw(self, currInt):
        self.obvPlt.set_data(range(currInt+1), self.obv)
        
        minOBV = min(self.obv[max(0, self.xlims[0]):min(len(self.obv), self.xlims[1])])
        maxOBV = max(self.obv[max(0, self.xlims[0]):min(len(self.obv), self.xlims[1])])
        buf = (maxOBV - minOBV) * 0.1
        self.ax.set_ylim(minOBV-buf, maxOBV+buf)
        
        if self.active: self.removeX.set_text("[X]")
        else: self.removeX.set_text("")
        self.removeX.set_position(((self.xlims[1] - self.xlims[0])*0.97 + self.xlims[0], minOBV-buf/2))
        

    def drawArtists(self, redraw):
        if redraw:
            pass
        else:
            self.ax.draw_artist(self.obvPlt)
            self.ax.draw_artist(self.removeX)
