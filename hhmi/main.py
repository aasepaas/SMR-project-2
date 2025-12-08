from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal, QObject
from mainwindow import mainWindow
import time
from threading import Event
import sys

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
    scan_finished = Signal(bool)  # resultaat van de scan (True = OK)

    def __init__(self, error_event, start_event, scan_event):
        super().__init__()
        self.start_event = start_event      # threading.Event gedeeld tussen threads
        self.scan_event = scan_event        # Event om een scan te triggeren
        self.restart_flag = False
        self.error_event = error_event

    def restart_triggered(self):
        print("Worker received restart signal")
        self.restart_flag = True

    def run(self):
        timer = 0.4
        ####profiles aanmaken
        # Wallet profile
        top1, left1 = 525, 800
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
        top2, left2 = 300, 800
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
        top3, left3 = 300, 1250
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

        scanner = CameraScanner(barcode_profile, profiles)
        # scanner.run(wallet_profile, giftbox_profile, barcode_profile)

        scan_thread = threading.Thread(
            target=scanner.run,
            args=(wallet_profile, giftbox_profile, barcode_profile),
            daemon=True
        )
        scan_thread.start()

        client_socket = Network_client('127.0.0.1', 5000)
        client_socket.strt_socket()
        status = StatusControl()
        db = DatabaseRun()

        while True:
            # 1) Als er een scan-request is, voer die uit en meld resultaat terug.
            scanner.set_profile(barcode_profile)
            if self.scan_event.is_set():
                if scanner.profile != barcode_profile:
                    scanner.set_profile(barcode_profile)
                print("Worker: scan gestart...")
                result = scanner.get_code()
                self.scan_event.clear()
                self.scan_finished.emit(True)
                '''if result is not None:
                    print(f"Worker: scan klaar, resultaat={result}")
                    # clear request en emit resultaat
                    self.scan_event.clear()
                    self.scan_finished.emit(True)
                    # ga terug naar top van loop om verdere requests te verwerken
                    #time.sleep(10000)
                    continue'''
            # 2) Als start_event is gezet, voer de hoofd-loop uit
            if self.start_event.is_set():
                print("Worker: start geaccepteerd, nu begint de loop!")
                client_socket.connect_client()
                # verwerk elke wallet sequentieel (current -> succes/unsuccessful)
                i = 0
                gui_index = 0
                box_ID = None
                while True:
                    ##new code
                    cmd = client_socket.receive_client()
                    if cmd is None:
                        print("Client disconnected.")
                        break
                    
                    print(f"COMMAND: {cmd}")

                    if cmd not in CMD_TO_STATE:
                        print(f"Unknown command: {cmd}")
                        continue

                    for event_key, state in CMD_TO_STATE.items():
                        if state == CMD_TO_STATE[cmd]:
                            event = event_key
                            break
                    if not event:
                        print(f"No matching event for command {cmd}")
                        continue

                    print(f"event: {event}")
                    current_state = status.run(event)
                    print(f" new state: {current_state}")

                    ##new code bastiaan
                    
                    if current_state == SMNState.SEND_GIFTBOX_DOORDINATES:
                        gui_index = i + 1
                        i += 1
                        print("SEND_GIFTBOX_DOORDINATES")
                        self.update_box_status.emit(gui_index, "current")
                        # #
                    if current_state == SMNState.IDLE:
                        print("idle")
                        # #
                    if current_state == SMNState.SCANNING_GIFTBOX:
                        print("SCANNING_GIFTBOX")
                        scanner.set_profile(giftbox_profile)
                        print("Worker: giftbox scan gestart")
                        while True:
                            box_ID = scanner.get_code()
                            if box_ID is not None:
                                print(f"Worker: scan klaar, resultaat={box_ID}")
                                #db.buffer = box_ID
                                db.bbuffer = "FK19T-0L3N-R8H6"
                                db.send_data(SMNState.SCANNING_GIFTBOX)
                                #check met if statement of hij in de database gevonden is of niet
                                continue

                    if current_state == SMNState.SEND_WALLET_COORDINATES:
                        print("SEND_WALLET_COORDINATES")
                        # #

                    if current_state == SMNState.SCANNING_WALLET:
                        print("SCANNING_WALLET")
                        scanner.set_profile(wallet_profile)
                        print("Worker: giftbox scan gestart")
                        while True:
                            wallet_ID = scanner.get_code()
                            if wallet_ID is not None:
                                print(f"Worker: scan klaar, resultaat={wallet_ID}")
                                #db.ibuffer = wallet_ID
                                db.ibuffer = "QH82M-9D5Z-B7X1"
                                db.send_data(SMNState.SCANNING_WALLET)
                                # check met if statement of hij in de database gevonden is of niet
                                #graag self.update_box_status.emit(gui_index, "unsuccessful")
                                #of self.update_box_status.emit(gui_index, "succes") op basis of hij de juiste wallet heeft
                                continue
                    if current_state == SMNState.SWITCH_CAMERA:
                        print("SWITCH_CAMERA")
                    if current_state == SMNState.PROCESSING:
                        print("PROCESSING")
                        # #
                    if current_state == SMNState.ERROR:
                        print("ERROR")
                        # #
                    if current_state == SMNState.DONE_CYCLE:
                        print("DONE_CYCLE")

                    if self.restart_flag:
                        print(f"Worker: restart_flag gedetecteerd vóór index {gui_index}, break")
                        self.restart_flag = False
                        break

                    # controleer opnieuw op error na succes (optioneel)
                    if self.error_event.is_set():
                        print(f"Worker: error_event na 'succes' bij index {gui_index}")
                        break

                # einde run of vroegtijdig door error/restart — clear start_event zodat we niet meteen opnieuw beginnen
                if self.start_event.is_set():
                    self.start_event.clear()

                # optionele status update naar GUI dat run klaar is
                self.update_status.emit("Status: Run klaar. Druk Start Scan voor nieuwe scan of Start voor run.")
                continue

            # geen scan en geen start => korte sleep en blijf luisteren
            time.sleep(0.05)


def main():
    app = QApplication(sys.argv)

    window = mainWindow()
    window.show()
    window.showFullScreen()

    # shared events
    error_event = Event()
    start_event = Event()
    scan_event = Event()

    # Thread aanmaken
    thread = QThread()
    worker = Worker(error_event, start_event, scan_event)
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
            window.page1.update_status("Status: Scan OK. Druk Start om te beginnen.")
        else:
            window.page1.update_status("Status: Scan failed. Probeer opnieuw.")

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

    # worker restart
    window.page2.restart_requested.connect(worker.restart_triggered)

    # START THREAD NU DIRECT zodat worker reageert op Start Scan ook op Page1
    thread.started.connect(worker.run)
    thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()