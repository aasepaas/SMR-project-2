import sys
from PyQt6.QtWidgets import QApplication
from window import MainWindow
from pathlib import Path


def main():
    app = QApplication(sys.argv)
    
    app.setStyleSheet(Path("Style.qss").read_text())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

    

if __name__ == "__main__":
    main()
