import tkinter as tk
from tkinter import filedialog
import inspect
import sys
import gc
import time

import Indicators
import BTC_API

class DefaultConfig():
    params = {
        "version":"0.13.0",
        "indicators":"MACD,RSI",
        "timeFrame":"1h",
        "enableIdle":0,
        "showVolBreakdown":0,
        "showFib":0,
        "showBBands":0,
        "viewSize":16
        }

class SettingsDialog(tk.Frame):

    def __init__(self):
        
        self.wheel = Wheel()
        self.wheel.setTitle("Settings")
        self.wheel.setBackground("#1e1e1e")
        self.wheel.setSize("480x360")

        self.textColor = "#cecece"
        self.edgeColor = "#6e6e6e"
        self.saveTimer = -1

        self.wheel.addFrame("titleLeft", 80, 10)
        self.wheel.setFrameText("titleLeft", "Indicators", self.textColor)
        self.wheel.addOptionMenu("indicatorSelection", 15, 35, self.getAllIndicators(), width=26, color=self.textColor, textcolor=self.edgeColor)
        self.wheel.addButton("add_ind", "+", 187, 36, self.addIndicator)
        self.wheel.setButtonText("add_ind", " + ", color=self.textColor)
        
        self.wheel.addCanvas("divider", 219, 0, 3, 360)
        self.wheel.canvasLine("divider", 2, 15, 2, 345, color=self.edgeColor)

        self.wheel.addFrame("titleRight", 300, 10)
        self.wheel.setFrameText("titleRight", "Other Settings", self.textColor)
        self.wheel.addFrame("timeFrameLbl", 235, 40)
        self.wheel.setFrameText("timeFrameLbl", "Time Frame", self.textColor)
        self.wheel.addOptionMenu("timeFrame", 415, 40, BTC_API.getIntervals(), width=3, color="#1e1e1e", textcolor=self.textColor) 
        self.wheel.addFrame("idleLbl", 235, 70)
        self.wheel.setFrameText("idleLbl", "Enable Idling", self.textColor)
        self.wheel.addCheckbox("enableIdle", 440, 70)
        self.wheel.addFrame("volBrkDwnLbl", 235, 100)
        self.wheel.setFrameText("volBrkDwnLbl", "Show Volume Breakdown", self.textColor)
        self.wheel.addCheckbox("showVolBreakdown", 440, 100)
        self.wheel.addFrame("fibLbl", 235, 130)
        self.wheel.setFrameText("fibLbl", "Show Fibonacci Retracement", self.textColor)
        self.wheel.addCheckbox("showFib", 440, 130)
        self.wheel.addFrame("bbandsLbl", 235, 160)
        self.wheel.setFrameText("bbandsLbl", "Show Bollinger Bands", self.textColor)
        self.wheel.addCheckbox("showBBands", 440, 160)
        self.wheel.addFrame("viewSize", 235, 190)
        self.wheel.setFrameText("viewSize", "# of Visible Candles", self.textColor)
        self.wheel.addUserEntry("viewSize", 440, 190, 3)

        self.wheel.addButton("setDefault", "Save as Default", 235, 225, lambda: self.saveConfig("default"))
        self.wheel.setButtonText("setDefault", "Save as Default", color=self.textColor, width=32)
        self.wheel.addButton("saveNew", "Save as New", 235, 255, lambda: self.saveConfig(""))
        self.wheel.setButtonText("saveNew", "Save as New", color=self.textColor, width=32)
        self.wheel.addButton("loadConfig", "Load Config", 235, 285, self.loadConfig)
        self.wheel.setButtonText("loadConfig", "Load Config", color=self.textColor, width=32)
        self.wheel.addButton("reset", "Reset", 235, 315, self.resetConfig)
        self.wheel.setButtonText("reset", "Reset", color=self.textColor, width=32)
        

        # Params
        self.version = DefaultConfig.params["version"]
        self.origParams = {}
        self.params = {}
        self.origInd = []
        self.indicators = []
        self.addedInd = []
        self.removedInd = []

    def isActive(self):
        return self.wheel.active

    def update(self):
        self.params["timeFrame"] = self.wheel.getOptionValue("timeFrame")
        self.params["enableIdle"] = self.wheel.getCheckboxValue("enableIdle")
        self.params["showVolBreakdown"] = self.wheel.getCheckboxValue("showVolBreakdown")
        self.params["showFib"] = self.wheel.getCheckboxValue("showFib")
        self.params["showBBands"] = self.wheel.getCheckboxValue("showBBands")
        self.params["viewSize"] = self.wheel.getEntryValue("viewSize")
        if self.saveTimer != -1 and time.time() - self.saveTimer > 3:
            self.wheel.setButtonText("setDefault", "Save as Default", color=self.textColor, width=32)
            self.saveTimer = -1
        self.wheel.update()
        
    def getAllIndicators(self):
        classes = inspect.getmembers(sys.modules[Indicators.__name__], inspect.isclass)
        indicators = sorted([x[0] for x in classes[2:]]) # ignore "ABC" and "Indicator" classes
        return ["Add Indicator"] + indicators

    def setConfig(self, tf, idle, vbd, fib, bb, nc):
        self.origParams["timeFrame"] = tf
        self.origParams["enableIdle"] = idle
        self.origParams["showVolBreakdown"] = vbd
        self.origParams["showFib"] = fib
        self.origParams["showBBands"] = bb
        self.origParams["viewSize"] = nc
        
        self.wheel.setOptionValue("timeFrame", tf)
        self.wheel.setCheckboxValue("enableIdle", idle)
        self.wheel.setCheckboxValue("showVolBreakdown", vbd)
        self.wheel.setCheckboxValue("showFib", fib)
        self.wheel.setCheckboxValue("showBBands", bb)
        self.wheel.setEntryValue("viewSize", nc)
        self.update()

    def loadIndicators(self, indicators):
        if not self.indicators and indicators != None:
            self.indicators = [type(ind).__name__ for ind in indicators]
            self.origInd = [j for j in self.indicators]

        x = 15
        y = 70  # title at y=10, dropdown menu at y=35
        for i,ind in enumerate(self.indicators):
            self.wheel.addCanvas(ind, x, y, 190, 45, border=1, bordercolor=self.edgeColor)
            self.wheel.canvasText(ind, len(ind)*7, 20, ind, self.textColor)
            self.wheel.addButton("rem%d" % i, " x ", 188, y+1, lambda ii=i: self.removeIndicator(ii), relief="ridge", border=1)
            self.wheel.setButtonText("rem%d" % i, " x ", color=self.textColor)
            y += 55

        self.update()

    def addIndicator(self, indName=None):
        if indName == None:
            indName = self.wheel.getOptionValue("indicatorSelection")
        if indName == "Add Indicator": return
        for ind in self.indicators:
            if ind == indName:
                print("Indicator already added")
                return
        idx = len(self.indicators)
        self.wheel.addCanvas(indName, 15, 70 + idx * 55, 190, 45, border=1, bordercolor=self.edgeColor)
        self.wheel.canvasText(indName, len(indName)*7, 20, indName, self.textColor)
        self.wheel.addButton("rem%d" % idx, " x ", 188, 71 + idx * 55, lambda: self.removeIndicator(idx), relief="ridge", border=1)
        self.wheel.setButtonText("rem%d" % idx, " x ", color=self.textColor)
        self.indicators.append(indName)
        if indName in self.removedInd:
            self.removedInd.remove(indName)
        else:
            self.addedInd.append(indName)
        self.update()

    def removeIndicator(self, idx):
        indName = self.indicators[idx]
        if indName in self.addedInd: self.addedInd.remove(indName)
        else: self.removedInd.append(indName)
        
        for i, ind in enumerate(self.indicators):
            self.wheel.removeButton("rem%d" % i)
            self.wheel.removeCanvas(ind)
        self.indicators.remove(indName)
        self.loadIndicators(None)

    def saveConfig(self, name):
        isDefault = False
        if name == "default":
            isDefault = True
            name = "..\\Configs\\" + name + ".conf"
        else:
            name = filedialog.asksaveasfilename(initialdir="..\\Configs\\", title="Save as", filetypes=(("config files", "*.conf"), ("all files", "*.*")))
            if name[-5:] != ".conf":
                name += ".conf"

        writeout = "version=%s\n" % self.version
        # write indicators to config
        writeout += "indicators="
        for ind in self.indicators:
            writeout += ind + ","
        writeout = writeout[:-1] + "\n"

        # write other settings
        writeout += "timeFrame=%s\n" % self.wheel.getOptionValue("timeFrame")
        writeout += "enableIdle=%s\n" % self.wheel.getCheckboxValue("enableIdle")
        writeout += "showVolBreakdown=%s\n" % self.wheel.getCheckboxValue("showVolBreakdown")
        writeout += "showFib=%s\n" % self.wheel.getCheckboxValue("showFib")
        writeout += "showBBands=%s\n" % self.wheel.getCheckboxValue("showBBands")
        writeout += "viewSize=%s" % self.wheel.getEntryValue("viewSize")
 
        with open(name, 'w') as f:
            f.write(writeout)

        if isDefault:
            self.wheel.setButtonText("setDefault", "Saved Config!", color=self.textColor, width=32)
            self.saveTimer = time.time()
            
    def loadConfig(self):
        conf = []
        name = filedialog.askopenfilename(initialdir="..\\Configs\\", title="Load Config", filetypes=(("config files", "*.conf"), ("all files", "*.*")))

        with open(name, 'r') as f:
            conf = f.readlines()
        conf = [x.replace("\n", "") for x in conf]

        # load indicators
        self.indicators = conf[0].split('=')[1].split(',')
        self.loadIndicators(None)

        # load other settings
        for line in conf[1:]:
            splitted = line.split('=')
            if len(splitted[1]) > 1:
                self.wheel.setOptionValue(splitted[0], splitted[1])
            else:
                self.wheel.setCheckboxValue(splitted[0], int(splitted[1]))

        self.update()
       
    def resetConfig(self):
        # remove all indicators and reload the original
        for i in range(len(self.indicators)):
            self.removeIndicator(0)
        self.indicators = list(self.origInd)
        self.removedInd = []
        self.addedInd = []
        self.loadIndicators(None)

        for param in self.origParams:
            if isinstance(self.origParams[param], str):
                self.wheel.setOptionValue(param, self.origParams[param])
            else:
                self.wheel.setCheckboxValue(param, self.origParams[param])
        
    
class Wheel(tk.Frame):
    def __init__(self):
        self.master = tk.Tk()
        tk.Frame.__init__(self, self.master)
        self.buttonDict = {}
        self.canvasDict  = {}
        self.frameDict = {}
        self.entryDict = {}
        self.optionsDict = {}
        self.checkboxDict = {}
        self.color = None
        self.active = True

        self.master.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self):
        self.active = False
        self.master.destroy()
        self.master = None
        gc.collect()    # force garbage collection now so it doesn't occur in the wrong thread
       
    def setSize(self, sizeStr):
        self.master.geometry(sizeStr)
        self.pack(fill=tk.BOTH, expand=1)

    def setTitle(self, title):
        self.master.title(title)

    def update(self):
        self.master.update()

    def mainloop(self):
        self.master.mainloop()

    def setBackground(self, color):
        self.configure(bg=color)
        self.color = color

    def addButton(self, identifier, text, dx, dy, command, relief=None, border=None):
        if identifier in self.buttonDict:
            self.buttonDict[identifier].destroy()
        self.buttonDict[identifier] = tk.Button(self, text=text, command=command, bg=self.color, relief=relief, bd=border)
        self.buttonDict[identifier].place(x=dx, y=dy)
    
    def setButtonText(self, identifier, text, color=None, width=None):
        if identifier in self.buttonDict:
            self.buttonDict[identifier].config(text=text, foreground=color, width=width)

    def removeButton(self, identifier):
        if identifier in self.buttonDict:
            self.buttonDict[identifier].destroy()
            del self.buttonDict[identifier]

    def posButton(self, identifier, dx, dy):
        if identifier in self.buttonDict:
            self.buttonDict[identifier].place(x=dx, y=dy)

    def addUserEntry(self, identifier, dx, dy, width, command=None):
        if identifier in self.entryDict:
            self.entryDict[identifier].destroy()
        var = tk.StringVar(self)
        self.entryDict[identifier] = (tk.Entry(self, width=width, validate="key", validatecommand=command, textvariable=var), var)
        self.entryDict[identifier][0].place(x=dx, y=dy)

    def getEntryValue(self, identifier):
        if identifier in self.entryDict:
            return self.entryDict[identifier][1].get()
        return None

    def setEntryValue(self, identifier, value):
        if identifier in self.entryDict:
            self.entryDict[identifier][1].set(value)

    def clearEntry(self, identifier):
        if identifier in self.entryDict:
            self.entryDict[identifier][0].delete(0, 'end')

    def disableEntry(self, identifier):
        if identifier in self.entryDict:
            self.entryDict[identifier][0].config(state="disabled")

    def enableEntry(self, identifier):
        if identifier in self.entryDict:
            self.entryDict[identifier][0].config(state="normal")		

    def addOptionMenu(self, identifier, dx, dy, options, width=None, command=None, color=None, textcolor=None):
        if identifier in self.optionsDict:
            self.optionsDict[identifier].destroy()
        variable = tk.StringVar(self)
        variable.set(options[0])
        self.optionsDict[identifier] = (tk.OptionMenu(self, variable, *options, command=command), variable)
        self.optionsDict[identifier][0].place(x=dx, y=dy)
        self.optionsDict[identifier][0].config(width=width, bd=1, bg=color, fg=textcolor,
                                               activebackground=color, activeforeground=textcolor, highlightbackground="#6e6e6e")

    def getOptionValue(self, identifier):
        if identifier in self.optionsDict:
            return self.optionsDict[identifier][1].get()

    def setOptionValue(self, identifier, val):
        if identifier in self.optionsDict:
            return self.optionsDict[identifier][1].set(val)

    def addCanvas(self, identifier, dx, dy, w, h, border=0, bordercolor=None):
        if identifier in self.canvasDict:
            self.canvasDict[identifier].destroy()
        if bordercolor == None: bordercolor = self.color
        self.canvasDict[identifier] = tk.Canvas(self, width=w, height=h, bd=border, bg=self.color, highlightbackground=bordercolor)
        self.canvasDict[identifier].place(x=dx, y=dy)

    def removeCanvas(self, identifier):
        if identifier in self.canvasDict:
            self.canvasDict[identifier].destroy()
            del self.canvasDict[identifier]

    def canvasText(self, identifier, x, y, text, color=None):
        if identifier in self.canvasDict:
            if color==None: color="black"
            self.canvasDict[identifier].create_text(x, y, text=text, fill=color)

    def canvasLine(self, identifier, x1, y1, x2, y2, color=None):
        if identifier in self.canvasDict:
            if color==None: color="black"
            self.canvasDict[identifier].create_line(x1, y1, x2, y2, fill=color) 

    def addFrame(self, identifier, dx, dy, canvas=False):
        if identifier in self.frameDict:
            self.frameDict[identifier].destroy()
        self.frameDict[identifier] = tk.Label(self, bg = self.color)
        self.frameDict[identifier].place(x=dx, y=dy)

    def setFrameImage(self, identifier, image):
        if identifier in self.frameDict:
            self.frameDict[identifier].configure(image=image)
            self.frameDict[identifier].image = image

    def setFrameClickEvent(self, identifier, eventFn):
        if identifier in self.frameDict:
            self.frameDict[identifier].bind('<Button-1>', eventFn)

    def setFrameText(self, identifier, text, color=None):
        if identifier in self.frameDict:
            self.frameDict[identifier].configure(text=text, foreground=color)

    def addCheckbox(self, identifier, dx, dy):
        if identifier in self.checkboxDict:
            self.checkboxDict[identifier].destroy()
        variable = tk.StringVar(self)
        variable.set(False)
        self.checkboxDict[identifier] = (tk.Checkbutton(self, variable=variable, onvalue=True, offvalue=False), variable)
        self.checkboxDict[identifier][0].place(x=dx, y=dy)
        self.checkboxDict[identifier][0].config(bg=self.color, activebackground=self.color)

    def getCheckboxValue(self, identifier):
        if identifier in self.checkboxDict:
            return self.checkboxDict[identifier][1].get()

    def setCheckboxValue(self, identifier, val):
        if identifier in self.checkboxDict:
            self.checkboxDict[identifier][1].set(val)
