import tkinter as tk
import Indicators
import inspect
import sys

class SettingsDialog(tk.Frame):

    def __init__(self):
        
        self.wheel = Wheel()
        self.wheel.setTitle("Settings")
        self.wheel.setBackground("#1e1e1e")
        self.wheel.setSize("480x360")

        self.textColor = "#cecece"
        self.edgeColor = "#6e6e6e"

        self.wheel.addFrame("titleLeft", 50, 10)
        self.wheel.setFrameText("titleLeft", "Indicators", self.textColor)
        self.wheel.addOptionMenu("indicatorSelection", 15, 35, 26, self.getAllIndicators())
        self.wheel.addButton("add_ind", "+", 187, 36, self.addIndicator)
        self.wheel.setButtonText("add_ind", " + ", color=self.textColor)
        
        self.wheel.addCanvas("divider", 219, 0, 3, 360)
        self.wheel.canvasLine("divider", 2, 15, 2, 345, color=self.edgeColor)
              
        self.timeFrame = 0
        self.indicators = []
        self.addedInd = []
        self.removedInd = []

    def isActive(self):
        return self.wheel.active

    def update(self):
        self.wheel.update()
        
    def getAllIndicators(self):
        classes = inspect.getmembers(sys.modules[Indicators.__name__], inspect.isclass)
        indicators = [x[0] for x in classes[2:]]
        return ["Add Indicator"] + indicators #, "MACD", "RSI", "OBV"]

    def loadIndicators(self, indicators):
        self.indicators = [type(ind).__name__ for ind in indicators]

        x = 15
        y = 70  # title at y=10, dropdown menu at y=35
        for ind in self.indicators:
            self.wheel.addCanvas(ind, x, y, 190, 45, border=1, bordercolor=self.edgeColor)
            self.wheel.canvasText(ind, len(ind)*7, 20, ind, self.textColor)
            y += 55

        self.wheel.update()

    def addIndicator(self):
        indName = self.wheel.getOptionValue("indicatorSelection")
        if indName == "Add Indicator": return
        for ind in self.indicators:
            if ind == indName:
                print("Indicator already added")
                return
        self.wheel.addCanvas(indName, 15, 70 + len(self.indicators) * 55, 190, 45, border=1, bordercolor=self.edgeColor)
        self.wheel.canvasText(indName, len(indName)*7, 20, indName, self.textColor)
        self.indicators.append(indName)
        self.addedInd.append(indName)
        self.wheel.update()
    
class Wheel(tk.Frame):
    def __init__(self):
        self.master = tk.Tk()
        tk.Frame.__init__(self, self.master)
        self.buttonDict = {}
        self.canvasDict  = {}
        self.frameDict = {}
        self.entryDict = {}
        self.optionsDict = {}
        self.color = None
        self.active = True

        self.master.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self):
        self.active = False
        self.master.destroy()
        
        
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

    def addButton(self, identifier, text, dx, dy, command):
            if identifier in self.buttonDict:
                    self.buttonDict[identifier].destroy()
            self.buttonDict[identifier] = tk.Button(self, text=text, command=command, bg=self.color)
            self.buttonDict[identifier].place(x=dx, y=dy)
    
    def setButtonText(self, identifier, text, color=None):
        if identifier in self.buttonDict:
            self.buttonDict[identifier].config(text=text, foreground=color)

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
            self.entryDict[identifier] = tk.Entry(self, width=width, validate="key", validatecommand=command)
            self.entryDict[identifier].place(x=dx, y=dy)

    def getEntryValue(self, identifier):
        if identifier in self.entryDict:
            return self.entryDict[identifier].get()
        return None

    def clearEntry(self, identifier):
            if identifier in self.entryDict:
                    self.entryDict[identifier].delete(0, 'end')

    def disableEntry(self, identifier):
            if identifier in self.entryDict:
                    self.entryDict[identifier].config(state="disabled")

    def enableEntry(self, identifier):
            if identifier in self.entryDict:
                    self.entryDict[identifier].config(state="normal")		

    def addOptionMenu(self, identifier, dx, dy, width, options, command=None):
        if identifier in self.optionsDict:
            self.optionsDict[identifier].destroy()
        variable = tk.StringVar(self)
        variable.set(options[0])
        self.optionsDict[identifier] = (tk.OptionMenu(self, variable, *options, command=command), variable)
        self.optionsDict[identifier][0].place(x=dx, y=dy)
        self.optionsDict[identifier][0].config(width=width, bd=0, bg="#cecece", highlightbackground=self.color)

    def getOptionValue(self, identifier):
        if identifier in self.optionsDict:
            return self.optionsDict[identifier][1].get()

    def addCanvas(self, identifier, dx, dy, w, h, border=0, bordercolor=None):
        if identifier in self.canvasDict:
            self.canvasDict[identifier].destroy()
        if bordercolor == None: bordercolor = self.color
        self.canvasDict[identifier] = tk.Canvas(self, width=w, height=h, bd=border, bg=self.color, highlightbackground=bordercolor)
        self.canvasDict[identifier].place(x=dx, y=dy)

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
