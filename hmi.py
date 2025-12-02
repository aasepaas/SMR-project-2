
from PyQt6 import QtWidgets
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QGraphicsAnchorLayout, QGraphicsProxyWidget, QGraphicsWidget, QMainWindow, QPushButton, QMessageBox
from PyQt6 import QtCore
from PyQt6.QtCore import QSizeF as Qf
from PyQt6.QtCore import Qt
import csv
import numpy as np






class MainWindow(QMainWindow):
  
    def __init__(self):
        self.mirrordata = []
        self.i = 0
        super().__init__()
        self.data = []
        self.Errormsg = QMessageBox(self)

        #state = program_State()

        


        self.minimumsize = Qf(100, 20)
        self.prefferedsize = Qf(200, 40)
        self.maximumsize = Qf(400, 80)
        inwindow = QGraphicsWidget()
        scene = QtWidgets.QGraphicsScene()
        scene.setSceneRect(0, 0, 1700, 1000)
        self.setGeometry(0,0,1700,1000)
        inwindow.setPreferredSize(1700, 1000)

        scene.setBackgroundBrush(Qt.GlobalColor.lightGray)
        
        
 

     

        importbutton = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QtWidgets.QPushButton("Import"))
        importbutton.widget().clicked.connect(self.on_button_click_import)
        
        exportbutton = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QtWidgets.QPushButton("Export"))
        exportbutton.widget().clicked.connect(lambda: self.on_button_click_export(self.data))

        Startbutton = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QtWidgets.QPushButton("Start"))
        Startbutton.setObjectName('Startbutton')
        Startbutton.widget().clicked.connect(self.startsystem)

        Stopbutton = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QtWidgets.QPushButton("Stop"))
        Stopbutton.widget().clicked.connect(self.stopsystem)

        Syrforward = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QtWidgets.QPushButton("Syringe forward"))
        Syrforward.widget().clicked.connect(self.syrforward)

        Syrbackward = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QtWidgets.QPushButton("Syringe backward"))
        Syrbackward.widget().clicked.connect(self.syrbackward)
        

        self.visualcoords = self.makeWidget(Qf(200, 240), Qf(400,480), Qf(800, 840), QtWidgets.QLabel("Visual Coordinates"))
        drawexample = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QtWidgets.QPushButton("drawcoords"))
        drawexample.widget().clicked.connect(self.drawvisualcoords)
        
        self.camcap = self.makeWidget(Qf(200, 240), Qf(400,480), Qf(800, 840), QtWidgets.QLabel("Camera Capture"))
        refresh = self.makeWidget(self.minimumsize, self.prefferedsize, self.maximumsize, QPushButton("refresh"))
        refresh.widget().clicked.connect(self.showimg)

        #if 
       
        
        anchor = QGraphicsAnchorLayout()
        inwindow.setLayout(anchor)

        anchor.setSpacing(10)

        anchor.addAnchor(importbutton, QtCore.Qt.AnchorPoint.AnchorLeft, anchor, QtCore.Qt.AnchorPoint.AnchorLeft)
        anchor.addAnchor(importbutton, QtCore.Qt.AnchorPoint.AnchorTop, anchor, QtCore.Qt.AnchorPoint.AnchorTop)

        anchor.addAnchor(exportbutton, QtCore.Qt.AnchorPoint.AnchorLeft, anchor, QtCore.Qt.AnchorPoint.AnchorLeft)
        anchor.addAnchor(exportbutton, QtCore.Qt.AnchorPoint.AnchorTop, importbutton, QtCore.Qt.AnchorPoint.AnchorBottom)

        anchor.addAnchor(self.visualcoords, QtCore.Qt.AnchorPoint.AnchorBottom, anchor, QtCore.Qt.AnchorPoint.AnchorBottom)
        anchor.addAnchor(self.visualcoords, QtCore.Qt.AnchorPoint.AnchorLeft, anchor, QtCore.Qt.AnchorPoint.AnchorLeft)

        anchor.addAnchor(drawexample, QtCore.Qt.AnchorPoint.AnchorLeft, anchor, QtCore.Qt.AnchorPoint.AnchorLeft)
        anchor.addAnchor(drawexample, QtCore.Qt.AnchorPoint.AnchorBottom, self.visualcoords, QtCore.Qt.AnchorPoint.AnchorTop)

        anchor.addAnchor(self.camcap, QtCore.Qt.AnchorPoint.AnchorRight, anchor, QtCore.Qt.AnchorPoint.AnchorRight)
        anchor.addAnchor(self.camcap, QtCore.Qt.AnchorPoint.AnchorBottom, anchor, QtCore.Qt.AnchorPoint.AnchorBottom)

        anchor.addAnchor(refresh, QtCore.Qt.AnchorPoint.AnchorRight, anchor, QtCore.Qt.AnchorPoint.AnchorRight)
        anchor.addAnchor(refresh, QtCore.Qt.AnchorPoint.AnchorBottom, self.camcap, QtCore.Qt.AnchorPoint.AnchorTop)

        anchor.addAnchor(Startbutton, QtCore.Qt.AnchorPoint.AnchorTop, anchor, QtCore.Qt.AnchorPoint.AnchorTop)
        anchor.addAnchor(Startbutton, QtCore.Qt.AnchorPoint.AnchorHorizontalCenter, anchor, QtCore.Qt.AnchorPoint.AnchorHorizontalCenter)

        anchor.addAnchor(Stopbutton, QtCore.Qt.AnchorPoint.AnchorTop, anchor, QtCore.Qt.AnchorPoint.AnchorTop)
        anchor.addAnchor(Stopbutton, QtCore.Qt.AnchorPoint.AnchorLeft, Startbutton, QtCore.Qt.AnchorPoint.AnchorRight)

        anchor.addAnchor(Syrforward, QtCore.Qt.AnchorPoint.AnchorBottom, anchor, QtCore.Qt.AnchorPoint.AnchorBottom)
        anchor.addAnchor(Syrforward, QtCore.Qt.AnchorPoint.AnchorHorizontalCenter, anchor, QtCore.Qt.AnchorPoint.AnchorHorizontalCenter)

        anchor.addAnchor(Syrbackward, QtCore.Qt.AnchorPoint.AnchorBottom, anchor, QtCore.Qt.AnchorPoint.AnchorBottom)
        anchor.addAnchor(Syrbackward, QtCore.Qt.AnchorPoint.AnchorLeft, Syrforward, QtCore.Qt.AnchorPoint.AnchorRight)

       
       


        
   


        scene.addItem(inwindow)
        graphicsView = QtWidgets.QGraphicsView(scene)
        self.setCentralWidget(graphicsView)
        self.setWindowTitle("HMI Main Window")


        
        



    def makeWidget(self, mini, pref, maxi, widget):
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(widget)
        proxy.setMinimumSize(mini)
        proxy.setMaximumSize(maxi)
        proxy.setPreferredSize(pref)
        proxy.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)

        return proxy
        
        
    def importfile(self):
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv);;All Files (*)")
        return file_path

    def extractdatafromcsv(self):
        file_path = self.importfile()
        if file_path:
            with open(file_path, 'r') as csvfile:
                csvreader = csv.reader(csvfile)
                data = [row for row in csvreader]
            return data
        return None

    def exportfile(self):
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv);;All Files (*)")
        return file_path

    def on_button_click_import(self):
        self.data = self.extractdatafromcsv()
        if self.data:
            print("Data imported successfully:")
            for row in self.data:
                if row[0] == '':
                    continue
                
            
                coords = (row[1].split())
                print(coords)

                x, y, z, rx, ry, rz = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]), int(coords[4]), int(coords[5]) 
                coordstosend = [ x, y, z, rx, ry, rz]
                self.mirrordata.append(coordstosend)
                print(coordstosend)

                print(type(coordstosend))
            
                
            
        else:
            print("No data imported.")



    def on_button_click_export(self, data):
        file_path = self.exportfile()
        if file_path:
            with open(file_path, 'w', newline='') as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerows(data)
            print("Data exported successfully.")
        else:
            print("No file selected for export.")

    def drawvisualcoords(self, data):
        data = self.data
        print(data)
        if data is None:
            data = ''
            print('did not finish import, data is empty, redo import')
    
        drawplane = self.visualcoords 
        drawplanereal = drawplane.widget()
        mapper = QPixmap(400, 480)
        mapper.fill(Qt.GlobalColor.white)
        drawplanereal.setPixmap(mapper)

        mapper = drawplanereal.pixmap()
        painter = QPainter(mapper)
        painter.drawLine(0, 133, 200, 240)
        painter.drawLine(400, 133, 200, 240)
        painter.drawLine(0, 480, 200, 240)
        painter.drawLine(400, 480, 200, 240)
        painter.drawLine(200, 0, 200, 240)
        painter.drawEllipse(QtCore.QPoint(200, 240), 195, 235)

        

        for row in data:
            if row[0] == '':
                
                continue
            
            
            coords = (row[1].split())
            print(coords)

            x, y, z, rx, ry, rz = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]), int(coords[4]), int(coords[5]) 
            coordstosend = [x, y, z, rx, ry, rz]
            self.mirrordata.append[coordstosend]
            print(coordstosend)
            print(type(coordstosend))

            painter.drawEllipse(QtCore.QPointF(x, y), 5, 5)

        painter.end()
        drawplanereal.setPixmap(mapper)
        drawplanereal.setScaledContents(True)
        return self.mirrordata


    def getVals(self, i):
        return self.mirrordata[i]


    def showimg(self):
        label = self.camcap
        
        labelreal = label.widget()
        pixmap = QPixmap(r"C:\Users\basti\Pictures\ims\protoimages\CamCap.bmp")
        labelreal.setPixmap(pixmap)
        labelreal.setScaledContents(True)
    
    def syrforward(self):
        print("syringe moving forward")

    def syrbackward(self):
        print("Syringe moving backward")

    def startsystem(self):
        print("start system, send flag to robot")

    def stopsystem(self):
        self.errorwindow()
        print("stop system, send flag to robot")

        
    def convert(self,x, y):
        
        convx = 400 / 1088
        convy = 480 / 734
        xim = x * convx
        yim = y * convy
        return xim, yim

    def errorwindow(self):
        error = self.Errormsg
        error.setWindowTitle("ERROR")
        error.setText("an error has occured, the robot has been stopped")
        error.setIcon(QMessageBox.Icon.Critical)
        error.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Abort)
        
        button = error.exec()
        if button == QMessageBox.StandardButton.Abort:
            self.quitprocess()
        else:
            button = QMessageBox.StandardButton.RestoreDefaults
            
    def quitprocess(self):
        QtCore.QCoreApplication.quit()

     

    

  

   
