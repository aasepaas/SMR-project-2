from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal, QObject
from mainwindow import mainWindow
import time
from threading import Event
import sys


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

        while True:
            # 1) Als er een scan-request is, voer die uit en meld resultaat terug.
            if self.scan_event.is_set():
                print("Worker: scan gestart...")
                # simulate scan work (vervang dit door echte scan-logica)
                time.sleep(1.0)
                # voorbeeld: resultaat True/False; hier simuleren we True
                result = True
                print(f"Worker: scan klaar, resultaat={result}")
                # clear request en emit resultaat
                self.scan_event.clear()
                self.scan_finished.emit(result)
                # ga terug naar top van loop om verdere requests te verwerken
                continue

            # 2) Als start_event is gezet, voer de hoofd-loop uit
            if self.start_event.is_set():
                print("Worker: start geaccepteerd, nu begint de loop!")
                # verwerk elke wallet sequentieel (current -> succes/unsuccessful)
                for i in range(50):
                    gui_index = i + 1

                    # check of er een restart is aangevraagd vóór we beginnen met deze index
                    if self.restart_flag:
                        print(f"Worker: restart_flag gedetecteerd vóór index {gui_index}, break")
                        self.restart_flag = False
                        break

                    # MARKER: current
                    self.update_box_status.emit(gui_index, "current")
                    # geef GUI tijd om te reageren / knipper te starten
                    time.sleep(timer)

                    # controleer of er een error opgetreden is tijdens current
                    if self.error_event.is_set():
                        print(f"Worker: error_event tijdens 'current' bij index {gui_index}")
                        # markeer deze als unsuccessful en stop de run
                        self.update_box_status.emit(gui_index, "unsuccessful")
                        break

                    # MARKER: succes
                    self.update_box_status.emit(gui_index, "succes")
                    time.sleep(timer)

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