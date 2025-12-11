from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal, QObject
from mainwindow import mainWindow
import time
from threading import Event
import sys

import csv 

from scanner import *
from databaserun import DatabaseRun
from NetworkClient import Network_client
import threading
from state_enum import state_enum
import time
from statuscontrol import StatusControl
from SMN import (
    Event as SMNEvent,
    CMD_TO_STATE,
    SMNState
)

class Worker(QObject):
    update_status = Signal(str)
    enable_start = Signal(bool)
    update_box_status = Signal(int, str)
    scan_finished = Signal(bool)

    def __init__(self, error_event, start_event, scan_event, done_event, net_client):
        super().__init__()
        self.start_event = start_event
        self.scan_event = scan_event
        self.restart_flag = False
        self.error_event = error_event
        self.done_event = done_event
        self.net_client = net_client 

    def restart_triggered(self):
        print("Worker received restart signal")
        self.restart_flag = True
        # Clear alle events zodat de worker opnieuw kan starten
        if self.error_event.is_set():
            self.error_event.clear()
        if self.done_event.is_set():
            self.done_event.clear()
        # Forceer socket disconnect om blocking receive te stoppen
        self.net_client.disconnect_client()

    def run(self):
        timer = 0.4
        # [Profile setup code blijft hetzelfde...]
        
        # Wallet profile
        top1, left1 = 100, 100
        bottom1, right1 = top1 + 100, left1 + 100
        wallet_profile = ScanProfile(
            name="Wallet",
            camera_index=0,
            roi=(top1, bottom1, left1, right1),
            focus=175,
            exposure=-5,
            brightness=100,
            data_timeout=0.5
        )

        # Giftbox profile
        top2, left2 = 150, 150
        bottom2, right2 = top2 + 150, left2 + 150
        giftbox_profile = ScanProfile(
            name="GiftBox",
            camera_index=0,
            roi=(top2, bottom2, left2, right2),
            focus=120,
            exposure=-4,
            brightness=100,
            data_timeout=0.5
        )

        # Barcode profile
        top3, left3 = 200, 200
        bottom3, right3 = top3 + 150, left3 + 300
        barcode_profile = ScanProfile(
            name="Barcode",
            camera_index=0,
            roi=(top3, bottom3, left3, right3),
            focus=120,
            exposure=-5,
            brightness=120,
            data_timeout=1.0,
            type="barcode"
        )

        profiles = {
            "wallet": wallet_profile,
            "giftbox": giftbox_profile,
            "barcode": barcode_profile
        }
        scanner = CameraScanner(profiles)

        scan_thread = threading.Thread(
            target=scanner.run, 
            daemon=True
        )
        scan_thread.start()

        self.net_client.strt_socket()
        status = StatusControl()
        db = DatabaseRun()

        while True:
            # Check restart flag aan het begin van de main loop
            if self.restart_flag:
                print("Worker: restart flag detected at main loop start")
                self.restart_flag = False
                # Clear start_event zodat we niet automatisch weer starten
                if self.start_event.is_set():
                    self.start_event.clear()
                # Heropen socket voor volgende run
                time.sleep(0.5)  # Korte delay
                self.net_client.strt_socket()
                print("Worker: restart completed, ready for new scan")
                continue

            # Scan event handling
            scanner.switch_profile("barcode")
            if self.scan_event.is_set():
                print("Worker: scan gestart...")
                result = scanner.get_code()
                connected = self.net_client.connect_client()
                #    print("asdajshdjkajksdasd")
                if not connected:
                    print("Worker: connect_client failed")
                    if self.start_event.is_set():
                        self.start_event.clear()
                    continue
                self.scan_event.clear()
                self.scan_finished.emit(True)

            # Start event handling
            if self.start_event.is_set():
                print("Worker: start geaccepteerd, nu begint de loop!")
                
                

                self.net_client.send_client("start")
                i = 1
                box_ID = None
                boxValue = False
                stop_run = False
                batchCompleted = False
                total_wallets = len(window.page2.wallet_statusbox)

                # Main processing loop
                while not batchCompleted:
                    # Check restart EERST
                    if self.restart_flag:
                        print("Worker: restart detected in batch loop, breaking")
                        stop_run = True
                        break
                    
                    # Check error/done events
                    if self.error_event.is_set() or self.done_event.is_set():
                        print(f"Worker: error/done event detected at wallet {i}")
                        stop_run = True
                        break
                    
                    # Check if batch complete
                    if i > total_wallets:
                        print("Worker: batch completed")
                        batchCompleted = True
                        break

                    # Receive command (dit kan blocken!)
                    try:
                        cmd = self.net_client.receive_client()
                        if cmd is None:
                            print("Worker: client disconnected")
                            stop_run = True
                            break
                    except Exception as e:
                        print(f"Worker: receive error: {e}")
                        # Waarschijnlijk socket gesloten door restart
                        if self.restart_flag:
                            print("Worker: receive interrupted by restart")
                            stop_run = True
                            break
                        continue
                    
                    print(f"COMMAND: {cmd}")

                    if cmd not in CMD_TO_STATE:
                        print(f"Unknown command: {cmd}")
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
                    current_state = status.run(event)
                    print(f"new state: {current_state}")

                    # State handling
                    if current_state == SMNState.SEND_GIFTBOX_COORDINATES:
                        print("SEND_GIFTBOX_COORDINATES")
                        self.net_client.send_client("GIFTBOX")
                        self.update_box_status.emit(i, "current")
                        
                    elif current_state == SMNState.SCANNING_GIFTBOX:
                        print("SCANNING_GIFTBOX")
                        scanner.switch_profile("giftbox")
                        self.net_client.send_client("SCAN_giftbox")
                        
                        box_ID = 1  # Mock scan
                        db.bbuffer = "FK19T-0L3N-R8H6"
                        checkWaarde = db.send_data(current_state)
                        boxValue = checkWaarde
                        
                        if checkWaarde:
                            print("Box ID validated")
                        else:
                            print("Box ID validation failed")
                            
                    elif current_state == SMNState.SEND_WALLET_COORDINATES:
                        print("SEND_WALLET_COORDINATES")
                        self.net_client.send_client("WALLET")
                        
                    elif current_state == SMNState.SCANNING_WALLET:
                        print("SCANNING_WALLET")
                        scanner.switch_profile("wallet")
                        self.net_client.send_client("SCAN_wALLT")
                        
                        wallet_ID = 1  # Mock scan
                        db.ibuffer = "QH82M-9D5Z-B7X1"
                        checkWaarde = db.send_data(SMNState.SCANNING_WALLET)
                        boxValue = checkWaarde
                        
                        if checkWaarde:
                            print("Wallet ID validated")
                        else:
                            print("Wallet ID validation failed")
                            
                    elif current_state == SMNState.DONE_CYCLE:
                        print("DONE_CYCLE")
                        self.net_client.send_client("DONECYCLE")
                        
                        if boxValue:
                            self.update_box_status.emit(i, "succes")
                        else:
                            self.update_box_status.emit(i, "unsuccessful")
                        
                        # Check restart/error/done NA status update
                        if self.restart_flag or self.error_event.is_set() or self.done_event.is_set():
                            print(f"Worker: stopping after wallet {i} status update")
                            stop_run = True
                            break
                            
                        i += 1
                        
                    elif current_state == SMNState.ERROR:
                        print("ERROR STATE")
                        stop_run = True
                        break

                # Na batch loop - cleanup
                print("Worker: exited batch loop")
                if self.start_event.is_set():
                    self.start_event.clear()
                
                # Disconnect client
                self.net_client.disconnect_client()
                
                continue

            # Geen scan en geen start => korte sleep
            time.sleep(0.05)

def main():
    global window
    app = QApplication(sys.argv)

    window = mainWindow()
    window.show()
    window.showFullScreen()

    # shared events
    error_event = Event()
    start_event = Event()
    scan_event = Event()
    done_event = Event()
    window.page2.set_done_event(done_event)

    client_socket = Network_client('127.0.0.1', 5000)
    client_socket.strt_socket()

    # Thread aanmaken
    thread = QThread()
    worker = Worker(error_event, start_event, scan_event, done_event, client_socket)
    worker.moveToThread(thread)

    # geef event ook door aan page2 zodat page2 het kan set/clear
    window.page2.set_error_event(error_event)

    # SIGNALS verbinden met GUI-functies
    worker.update_status.connect(window.page1.update_status)
    worker.update_box_status.connect(window.page2.update_wallet_status)

    # Wanneer scan klaar is: als resultaat True -> enable Start knop; altijd heractiveer Start Scan knop
    def handle_scan_result(ok: bool):
        window.page1.startScanButton.setEnabled(True)
        window.page1.startButton.setEnabled(ok)
        if ok:
            window.page1.update_status("Scan OK. Druk Start om te beginnen.")
        else:
            window.page1.update_status("Scan failed. Probeer opnieuw.")

    worker.scan_finished.connect(handle_scan_result)

    # verbind start_clicked naar lambda die start_event.set() doet (GUI-thread)
    window.page1.start_clicked.connect(lambda: start_event.set())
    # vervolgens de page-switch (ook in de GUI-thread)
    window.page1.start_clicked.connect(window.switch_to_page2)

    # verbind scan_requested naar een trigger die de knop tijdelijk disable't en de scan_event zet
    def trigger_scan():
        window.page1.startScanButton.setEnabled(False)
        window.page1.update_status("Status: Scannen...")
        scan_event.set()

    window.page1.scan_requested.connect(trigger_scan)

    def on_restart_requested():
        print("Main: restart requested — closing network sockets to unblock worker")
        worker.restart_triggered()
 

    # worker restart
    window.page2.restart_requested.connect(on_restart_requested)

    # START THREAD NU DIRECT zodat worker reageert op Start Scan ook op Page1
    thread.started.connect(worker.run)
    thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()