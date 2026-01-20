
from asyncio.windows_events import NULL
from http.client import NETWORK_AUTHENTICATION_REQUIRED
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal, QObject
from mainwindow import mainWindow
import time
import sys
import threading

import csv
from scanner import *
from databaserun import DatabaseRun
from NetworkClient import Network_client
from state_enum import state_enum
from statuscontrol import StatusControl
from SMN import (
    Event as SMNEvent,
    CMD_TO_STATE,
    SMNState
)

from feed import LiveFeed, VideoFeed
from camera_scanner import CameraScanner, standard_profile
from decoders import DataMatrixDecoder, BarcodeDecoder
from roi_auto_detector import ROIAutoDetector
#from profile_setup import wallet_profile, giftbox_profile, barcode_profile

# Initialize environment and logging before importing modules that use cv2/matplotlib
from logging_config import init_environment, set_up_logger

from profile_setup import standard_profile, wallet_profile, giftbox_profile

import defines

class Worker(QObject):
    update_status = Signal(str)
    enable_start = Signal(bool)
    update_box_status = Signal(int, str)
    scan_finished = Signal(bool)
    startScan = Signal(bool)
    showErrorWindow = Signal(str, str)

    def __init__(self, error_event, start_event, scan_event, done_event, net_client: Network_client, scanner, window, csvreader, database, status):
        super().__init__()
        self.start_event = start_event
        self.scan_event = scan_event
        self.restart_flag = False
        self.error_event = error_event
        self.done_event = done_event
        self.net_client = net_client
        self.scanner = scanner
        self.window = window
        self.clientConnected = False

        self.csvReader = csvreader
        self.giftboxCoords = []
        self.walletCoords = []
        self.giftboxAndWalletCheck = False

        self.db = database
        self.status = status


        self.allowRestart = True
        self.giftboxValues = []
        self.klaarSituatie = 0
        self.fouteGiftboxWaardes = []
        self.fouteWalletWaardes = []

        self.indexCurrentWallet = 0


    def restart_triggered(self):
        print("Worker received restart signal")
        self.allowRestart = True
        self.restart_flag = True
        # Clear events zodat de worker opnieuw kan starten
        if self.error_event.is_set():
            self.error_event.clear()
        if self.done_event.is_set():
            self.done_event.clear()
        # Forceer client disconnect (unblocks recv thread)
        try:
            #voeg if statement toe of hij done of error moet sturen!!!!!!!!!!!!!!!!!!!!!!!
            # 0 is error situatie, 1 is normale situatie

            self.net_client.clear_queue()
            if not self.net_client.is_connected():
                self.net_client.stop_socket()
                time.sleep(0.2)
                self.net_client.start_server()
            self.klaarSituatie = 0
        except Exception as e:
            print(f"restart_triggered: disconnect error: {e}")
        self.clientConnected = False

    def run(self):
        timer = 0.4

        # start scanner thread
        scan_thread = threading.Thread(
            target= self.scanner.run,
            daemon=True
        )
        scan_thread.start()
        #self.scanner.run()
        self.clientConnected = self.net_client.is_connected()
        errorOfDoneGestuurd = False


        while True:



            if self.restart_flag:
                self.restart()
                #self.clientConnected = False
                continue 

            # Wait for a client to connect (non-blocking check)
            if errorOfDoneGestuurd:
                # if self.klaarSituatie == 0:
                #     self.net_client.send_client("0 0 0 0 0 0 0 0")

                # elif self.klaarSituatie == 1:
                #     self.net_client.send_client("0 0 0 0 0 0 0 0")
                try:
                    cmd = self.net_client.get_message(timeout=0.5)
                except Exception:
                    cmd = None

                if cmd == "SEND_GIFTBOX_COORDINATES":
                    self.net_client.send_client("(0, 0, 0, 0, 0, 0, 0, 0)")
                    errorOfDoneGestuurd = False


            if not self.clientConnected:
                print("not connected")
                if self.net_client.is_connected():
                    self.clientConnected = True
                    self.startScan.emit(True)
                    print("Worker: client connected (detected by is_connected())")
                else:
                    # handle UI events like restart/error/done while waiting
                    if self.restart_flag or self.error_event.is_set() or self.done_event.is_set():
                        time.sleep(0.05)
                        continue
                    time.sleep(0.1)
                    continue

            # start scan (from UI)
            if self.scan_event.is_set():
                self.scanButtonPressed()

            #pak alle coordinaten van de excel sheet
            self.csvReader.selectgiftboxtype(1)
            self.giftboxCoords = self.csvReader.formatdata(False)
            self.csvReader.selectwallettype(1)
            self.walletCoords = self.csvReader.formatdata(True)
            # Start event handling
            if self.start_event.is_set():
                print("Worker: start geaccepteerd, nu begint de loop!")
                self.net_client.send_client("start")


                self.indexCurrentWallet = 1
                box_ID = None
                self.giftboxAndWalletCheck = False
                stop_run = False
                batchCompleted = False
                total_wallets =  50 #len(self.window.page2.wallet_statusbox)
                self.scanner.switch_profile(standard_profile)
                current_state = SMNState.IDLE
                

                # Main processing loop
                while not batchCompleted:
                    # React quickly to restart/error/done
                    if self.restart_flag:
                        print("Worker: restart detected in batch loop, breaking")
                        stop_run = True
                        break

                    if self.error_event.is_set() or self.done_event.is_set():
                        print(f"Worker: error/done event detected at wallet {self.indexCurrentWallet}")
                        stop_run = True
                        break



                    if self.indexCurrentWallet > total_wallets:
                        print("Worker: batch completed")
                        batchCompleted = True
                        self.klaarSituatie = 1
                        break

                    # Fetch a command from network client queue; do not block long
                    try:
                        cmd = self.net_client.get_message(timeout=0.5)
                    except Exception:
                        if self.restart_flag or self.error_event.is_set() or self.done_event.is_set():
                            print("Worker: exiting batch loop due to flag during receive timeout")
                            stop_run = True
                            break

                        if not self.net_client.is_connected():
                            print("geen client meer ")
                            #self.window.page2.errorwindow("Robot is niet meer verbonden", "Klik op restart om terug te gaan naar startpagine")
                            self.showErrorWindow.emit("Robot is niet meer verbonden", "Klik op restart om terug te gaan naar startpagine")
                            stop_run = True
                            self.net_client.clse_socket()
                            self.net_client.strt_socket()
                            break
                        
                        continue

                    if cmd is None:
                        # no message received in timeout
                        continue

                    print(f"COMMAND: {cmd}")

                    if cmd not in CMD_TO_STATE:
                        print(f"Unknown command: {cmd}")
                        self.net_client.send_client("Unknow command")
                        continue

                    # Determine event from command
                    event = None
                    for event_key, state in CMD_TO_STATE.items():
                        if state == CMD_TO_STATE[cmd]:
                            event = event_key
                            break

                    if not event:
                        print(f"No matching event for command {cmd}")
                        continue

                    print(f"event: {event}")
                    current_state = self.status.run(event)
                    print(f"new state: {current_state}")

                    # State handling similar to before
                    if current_state == SMNState.SEND_GIFTBOX_COORDINATES:
                        if not self.sendCoords(defines.GIFTBOX):
                            self.giftboxAndWalletCheck = False
                        else:
                            self.giftboxAndWalletCheck = True
                        self.update_box_status.emit(self.indexCurrentWallet, "current")

                    elif current_state == SMNState.SCANNING_GIFTBOX:
                        self.scanGiftbox()



                    elif current_state == SMNState.SEND_WALLET_COORDINATES:
                        self.sendCoords(defines.WALLET)

                    elif current_state == SMNState.SCANNING_WALLET:
                        self.scanWallet()


                    elif current_state == SMNState.DONE_CYCLE:
                        errorOfDoneGestuurd = True
                        if not self.cycleCompleted():
                            break
                        self.indexCurrentWallet += 1

                    elif current_state == SMNState.ERROR:
                        self.errorState()
                        break

                # Na batch loop - cleanup
                print("Worker: exited batch loop")
                if self.start_event.is_set():
                    self.start_event.clear()

                continue

            # korte sleep
            time.sleep(0.05)
    

    def restart(self):
        print("Worker: restart flag detected at main loop start")
        self.restart_flag = False
                # Clear start_event zodat we niet automatisch weer starten
        if self.start_event.is_set():
            self.start_event.clear
        print("Worker: restart completed, ready for new scan")
        self.indexCurrentWallet = 0
        self.klaarSituatie = 0
        self.giftboxValues.clear()
        self.fouteGiftboxWaardes.clear()
        self.fouteWalletWaardes.clear()
        self.giftboxAndWalletCheck = False
        print("restart")

    def checkCode(self):
        print("checkcode")

    def errorState(self):
        print("ERROR STATE")
        stop_run = True
        self.showErrorWindow.emit("Robot heeft error gestuurd", "Proces gestopt door robot <br> Klik op restart om terug te gaan naar het startscherm")
        #self.showErrorWindow.emit("Robot heeft error gestuurd", "Proces beëindgid door Robot <br> Klik op restart om terug te gaan naar het startscherm")


    def checkBreakInCode(self):
        print("check break in code")

    def custom_key(n):
        last_digit = n % 10

        # gewenste volgorde van laatste cijfers
        order = [0, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        return (order.index(last_digit), n)

    def scanButtonPressed(self):
        self.scanner.switch_profile(giftbox_profile)
        time.sleep(0.5)
        print("Worker: scan gestart...")
        resultsGiftboxScanDict = None
        
        while True:
            resultsGiftboxScanDict= self.scanner.get_code()
            if resultsGiftboxScanDict is not None:
                break
                

        #resultsGiftboxScanDict = dict(sorted(resultsGiftboxScanDict.items()))
        #ordered_keys = sorted(resultsGiftboxScanDict.keys())
        #ordered_values = [resultsGiftboxScanDict[k] for k in ordered_keys]  
        order_map = {v: i for i, v in enumerate([0, 9, 8, 7, 6, 5, 4, 3, 2, 1])}
        ordered_dict = dict(
            sorted(
                resultsGiftboxScanDict.items(),
                key=lambda item: (order_map[item[0] % 10], item[0])
            )
        )

        ordered_values = list(ordered_dict.values())
        
        if len(ordered_values) > 47:
            indexCurrentWallet = 1
            for scanWaarde in ordered_values:
                print(scanWaarde)
                self.db.bbuffer = scanWaarde
                checkWaarde = self.db.send_data(SMNState.SCANNING_GIFTBOX)
                if checkWaarde:
                    print("Box ID validated")
                else:
                    print("Box ID validation failed")
                    self.update_box_status.emit(indexCurrentWallet, "unsuccessful")
                self.giftboxValues.append([scanWaarde, checkWaarde])
                indexCurrentWallet += 1
                        
                        #niet in database gelijk fout in het systeem
                        #self.
        else:
            print("te weinig helaas")
            for i in range(1, 51):
                self.update_box_status.emit(i, "unsuccessful")
        self.scan_event.clear()
        self.scan_finished.emit(True)
        print(self.giftboxValues)
        print(self.giftboxCoords)
        print(self.walletCoords)
        self.scanner.switch_profile(standard_profile)
        time.sleep(0.5)


    def sendCoords(self, typeCoords):
        print("sendgiftboxcoords")
        if typeCoords == defines.GIFTBOX:
            if self.giftboxValues[self.indexCurrentWallet-1][1] == True:
                verwerkteVerzendData =  self.giftboxCoords[self.indexCurrentWallet-1] +[1] 
                print(verwerkteVerzendData)
                self.net_client.send_client(verwerkteVerzendData)
                return True
            else:
                verwerkteVerzendData = self.giftboxCoords[self.indexCurrentWallet-1] + [0] 
                print(verwerkteVerzendData)
                self.net_client.send_client(verwerkteVerzendData)
                self.giftboxAndWalletCheck = False
                return False
        else:
            if self.giftboxValues[self.indexCurrentWallet-1][1] == True:
                verwerkteVerzendData = self.walletCoords[self.indexCurrentWallet-1] + [1]  
                print(verwerkteVerzendData)
                self.net_client.send_client(verwerkteVerzendData)
                return True
            else:
                verwerkteVerzendData = self.walletCoords[self.indexCurrentWallet-1] + [0]  
                print(verwerkteVerzendData)
                self.net_client.send_client(verwerkteVerzendData)
                return True


    
    def scanGiftbox(self):
        print("SCANNING_GIFTBOX")
        #self.scanner.switch_profile(wallet_profile)
        self.net_client.send_client("SCAN_giftbox")

    def scanWallet(self):
        print("SCANNING_WALLET")
        self.scanner.switch_profile(wallet_profile)
        time.sleep(0.2)
        result = None
        box_id = None
        
        while True:
            result= self.scanner.get_code()
            if result is not None:
                break

        #box_ID = result.values()[0]

        for value in result.values():
            print(value)
            box_id = value
        self.db.bbuffer = self.giftboxValues[self.indexCurrentWallet-1][0]
        self.db.ibuffer = box_id #"QH82M-9D5Z-B7X1"
        checkWaarde = self.db.send_data(SMNState.SCANNING_WALLET)
        self.giftboxAndWalletCheck = checkWaarde

        result = "true" if checkWaarde else "false"
        self.net_client.send_client(result)
        print(result)
        # if checkWaarde:
        #     print("true")
        #     self.net_client.send_client("true")
        # else:
        #     self.net_client.send_client("false")
        #     print("false")
        print("scanevent")
        self.scanner.switch_profile(standard_profile)

        

    def cycleCompleted(self):
        print("DONE_CYCLE")
        #self.net_client.send_client("DONECYCLE")

        result = "succes" if self.giftboxAndWalletCheck else "unsuccessful"
        self.update_box_status.emit(self.indexCurrentWallet, result)

        # if self.giftboxAndWalletCheck:
        #     self.update_box_status.emit(self.indexCurrentWallet, "succes")
        # else:
        #     self.update_box_status.emit(self.indexCurrentWallet, "unsuccessful")

        if self.restart_flag or self.error_event.is_set() or self.done_event.is_set():
            print(f"Worker: stopping after wallet {self.indexCurrentWallet} status update")
            return False


        self.net_client.send_client("Continue")
        return True

