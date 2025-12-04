from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QMainWindow, QStackedWidget, QMessageBox
)

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal, QPropertyAnimation, QEvent, QTimer

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QGridLayout


class Page1(QWidget):
    # nieuw signal dat uitgezonden wordt als Start wordt geklikt
    start_clicked = Signal()
    # nieuw signal voor scan request
    scan_requested = Signal()

    def __init__(self, switch_callback):
        super().__init__()

        layout = QVBoxLayout(self)

        # Statusbox
        self.status_box = QLabel("Status: Scan productsoort barcode")
        self.status_box.setAlignment(Qt.AlignCenter)
        self.status_box.setStyleSheet("""
            background-color: #00AEFF;
            color: black;
            padding: 15px;
            border-radius: 8px;
            font-size: 22px;
            font-weight: bold;
        """)
        self.status_box.setFixedSize(1280, 310)
        layout.addWidget(self.status_box)
        layout.setAlignment(self.status_box, Qt.AlignHCenter)

        # Start Scan knop (nieuw)
        self.startScanButton = QPushButton("Start Scan")
        self.startScanButton.setStyleSheet("""
            QPushButton {
                background-color: #8bc34a;
                color: black;
                padding: 12px;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #b8b8b8;
                color: #6d6d6d;
            }
        """)
        self.startScanButton.setFixedSize(300, 80)
        self.startScanButton.setEnabled(True)  # standaard enabled
        layout.addWidget(self.startScanButton)
        layout.setAlignment(self.startScanButton, Qt.AlignHCenter)
        # verbind startScanButton naar scan_requested
        self.startScanButton.clicked.connect(lambda: self.scan_requested.emit())

        # Buttons
        self.startButton = QPushButton("Start")
        self.startButton.setStyleSheet("""
            QPushButton {
                background-color: #e39487;
                color: black;
                padding: 15px;
                border-radius: 8px;
                font-size: 22px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #b8b8b8;
                color: #6d6d6d;
            }
        """)
        self.startButton.setFixedSize(300, 100)
        self.startButton.setEnabled(False)

        layout.addWidget(self.startButton)
        layout.setAlignment(self.startButton, Qt.AlignHCenter)

        # Emit start_clicked when button pressed.
        # main() verbindt start_clicked -> start_event.set en -> switch_callback in de gewenste volgorde
        self.startButton.clicked.connect(lambda: self.start_clicked.emit())

    def enable_start(self):
        self.startButton.setEnabled(True)

    def update_status(self, text):
        self.status_box.setText(text)


class Page2(QWidget):
    restart_requested = Signal()

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        self.Errormsg = QMessageBox(self)

        self.blink_timers = {}

        self.status_box = QLabel("Status: Inpakken gestart")
        self.status_box.setAlignment(Qt.AlignCenter)
        self.status_box.setStyleSheet("""
                            background-color: #82B2C0;
                            color: black;
                            padding: 15px;
                            border-radius: 8px;
                            font-size: 22px;
                            font-weight: bold;
                        """)
        self.status_box.setFixedSize(1280, 310)
        layout.addWidget(self.status_box)
        layout.setAlignment(self.status_box, Qt.AlignHCenter)

        self.wallet_statusbox = []

        self.wallet_errorcount = 0
        self.wallet_errorStatus = QLabel("Aantal Errors: "
                                         f"{self.wallet_errorcount}")
        self.wallet_errorStatus.setAlignment(Qt.AlignCenter)
        self.wallet_errorStatus.setStyleSheet("""
                                    background-color: #F1B8A4;
                                    color: black;
                                    padding: 15px;
                                    border-radius: 8px;
                                    font-size: 22px;
                                    font-weight: bold;
                                """)
        self.wallet_errorStatus.setFixedSize(300, 300)

        self.wallet_container = QWidget()
        self.wallet_container_layout = QGridLayout()
        self.wallet_container_layout.setSpacing(5)
        self.wallet_container_layout.setContentsMargins(0, 0, 0, 0)
        self.wallet_container.setLayout(self.wallet_container_layout)

        row_layout = QHBoxLayout()
        row_layout.addWidget(self.wallet_container, alignment=Qt.AlignHCenter)
        row_layout.addWidget(self.wallet_errorStatus, alignment=Qt.AlignHCenter)

        layout.addLayout(row_layout)

        self.create_wallets(50, per_row=5)
        self.current_Wallet = 0

        self.restartButton = QPushButton("Opnieuw starten")
        self.restartButton.setFixedSize(300, 100)
        self.restartButton.setStyleSheet("""
            QPushButton {
                background-color: #e39487;
                color: black;
                padding: 15px;
                border-radius: 8px;
                font-size: 22px;
                font-weight: bold;
            }
        """)
        self.restartButton.hide()
        layout.addWidget(self.restartButton, alignment=Qt.AlignHCenter)
        self.restartButton.clicked.connect(self.restart_requested)
        self.error_event = None

    def set_error_event(self, event):
        self.error_event = event

    def errorCount(self):
        self.wallet_errorcount += 1
        self.wallet_errorStatus.setText("Aantal Errors: "
                                        f"{self.wallet_errorcount}"
                                        )
        if self.wallet_errorcount > 3:
            if self.error_event:
                self.error_event.set()
            self.errorwindow("Er zijn te veel fout gelinkte portemonnees, proces beëindigd")

    def create_wallets(self, number_of_wallets, per_row=5):
        for lbl in self.wallet_statusbox:
            self.wallet_container_layout.removeWidget(lbl)
            lbl.deleteLater()
        self.wallet_statusbox = []

        for i in range(number_of_wallets):
            row = i // per_row
            col = i % per_row
            lbl = QLabel()
            lbl.setFixedSize(30, 30)
            lbl.setText(str(i+1))
            lbl.setStyleSheet("""
                        background-color: white;
                        border: 1px solid black;
                        color: black;
                        padding: 6px;
                        font-size: 11px;
                        font-weight: bold;
                    """)
            self.wallet_container_layout.addWidget(lbl, row, col)
            self.wallet_statusbox.append(lbl)

    def update_wallet_status(self, index, status):
        index -= 1
        if index < 0 or index >= len(self.wallet_statusbox):
            return

        self.stop_blink(index)
        self.current_Wallet = index + 1

        if status == "current":
            self.wallet_statusbox[index].setStyleSheet("background-color: rgb(200,200,200); border: 1px solid black; color: black; padding: 6px;font-size: 11px;font-weight: bold;")
            self.start_blink(index)
            return

        color_map = {
            "unhandled": "white",
            "succes": "green",
            "unsuccessful": "red"
        }

        color = color_map.get(status, "white")
        self.wallet_statusbox[index].setStyleSheet(f"background-color: {color}; border: 1px solid black; color: black; padding: 6px;font-size: 11px;font-weight: bold;")
        if status == "unsuccessful":
            self.errorCount()

        if self.current_Wallet == len(self.wallet_statusbox):
            self.doneState()

    def start_blink(self, index):
        label = self.wallet_statusbox[index]

        if index in self.blink_timers:
            self.stop_blink(index)

        timer = QTimer(self)
        timer.setInterval(350)

        def toggle():
            current = label.styleSheet()
            if "rgb(200" in current:
                label.setStyleSheet("background-color: rgb(120,120,120); border: 1px solid black; color: black; padding: 6px;font-size: 11px;font-weight: bold;")
            else:
                label.setStyleSheet("background-color: rgb(200,200,200); border: 1px solid black; color: black; padding: 6px;font-size: 11px;font-weight: bold;")

        timer.timeout.connect(toggle)
        timer.start()
        self.blink_timers[index] = timer

    def stop_blink(self, index):
        if index in self.blink_timers:
            self.blink_timers[index].stop()
            self.blink_timers[index].deleteLater()
            del self.blink_timers[index]

    def errorwindow(self, errorMSG):
        error = self.Errormsg
        error.setWindowTitle("ERROR")
        error.setText(f"{errorMSG}")
        error.setStyleSheet("""
        QMessageBox {
            background-color: white;
            border: 3px solid black;
        }
        QLabel {
            color: black;
            font-size: 22px;
            font-weight: bold;
        }
        QPushButton {
            background-color: white;
            color: black;
            padding: 10px;
            min-width: 80px;
            border-radius: 6px;
            font-size: 18px;
        }
        QPushButton:hover {
            background-color: #e6e6e6;
        }
    """)
        error.setIcon(QMessageBox.Icon.Critical)
        error.setStandardButtons(QMessageBox.StandardButton.Ok)

        button = error.exec()
        if button == QMessageBox.StandardButton.Ok:
            button = QMessageBox.StandardButton.RestoreDefaults
            self.okErrorPressed()

    def doneState(self):
        print("done")
        self.restartButton.show()

    def okErrorPressed(self):
        print("restart")
        self.restartButton.show()


class mainWindow(QMainWindow):
    page2_shown = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secrid Robot")
        self.resize(1920, 1080)
        self.setStyleSheet("background-color: #F2F1ED;")

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Maak pagina's
        self.page1 = Page1(self.switch_to_page2)
        self.page2 = Page2()

        # Voeg toe aan stack
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)

        # Start op Page1
        self.stack.setCurrentWidget(self.page1)

        self.page2.restart_requested.connect(self.go_to_page1)
        self.installEventFilter(self)

        # flag: start-knop werd gedrukt (wordt gezet door switch_to_page2 als start=True)
        self.start_was_pressed = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            text = event.text().lower()
            if text == "s":  # als iemand 's' indrukt (barcode scanner → "start")
                print("Scanner: start ontvangen")
                self.page1.enable_start()
        return super().eventFilter(obj, event)

    def switch_to_page2(self, start=False):
        # start argument is gezet door Page1 via start_clicked
        self.start_was_pressed = start
        self.stack.setCurrentWidget(self.page2)
        self.page2_shown.emit()

    def go_to_page1(self):
        # Reset Page1 UI
        self.page1.update_status("Status: Scan productsoort barcode")
        self.page1.startButton.setEnabled(False)

        # Reset Page2 error count en wallets
        self.page2.wallet_errorcount = 0
        self.page2.wallet_errorStatus.setText("Aantal Errors: 0")
        self.page2.restartButton.hide()

        for lbl in self.page2.wallet_statusbox:
            lbl.setStyleSheet("""
                background-color: white;
                border: 1px solid black;
                color: black;
                padding: 6px;
                font-size: 11px;
                font-weight: bold;
            """)

        # Switch page
        self.stack.setCurrentWidget(self.page1)