from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QMainWindow
)
from PySide6.QtCore import Qt


class statusWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secrid Robot status scherm")
        self.resize(1920, 1080)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)
        self.setStyleSheet("background-color: #87d6e3;")