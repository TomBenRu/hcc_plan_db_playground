import sys
import winreg
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton
from PySide6.QtGui import QColor, QPalette


def is_dark_mode():
    try:
        # Öffne den Registrierungsschlüssel
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            # Lese den Wert für "AppsUseLightTheme"
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            # Wenn der Wert 0 ist, ist der dunkle Modus aktiviert
            return value == 0
    except Exception as e:
        print(f"Error: {e}")
        return False


def set_widget_colors(widget: QWidget, dark_mode: bool):
    palette = widget.palette()
    if dark_mode:
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, QColor(128, 255, 255))  # Schriftfarbe für Labels
        palette.setColor(QPalette.Button, QColor(53, 53, 53))  # Hintergrundfarbe für Buttons
        palette.setColor(QPalette.ButtonText, QColor(255, 128, 255))  # Schriftfarbe für Buttons
    else:
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.Button, QColor(255, 255, 255))
        palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    widget.setPalette(palette)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        dark_mode = is_dark_mode()
        print(f"Dark mode: {dark_mode}")

        # Setze die Hintergrund- und Schriftfarben
        set_widget_colors(self, dark_mode)

        layout = QVBoxLayout()

        # Erstelle ein Label und setze die Schriftfarbe
        label = QLabel("Hello, World!")
        layout.addWidget(label)

        # Erstelle einen Button und setze die Schriftfarbe
        button = QPushButton("Click Me")
        layout.addWidget(button)

        self.setLayout(layout)
        self.setWindowTitle("PySide6 Windows Mode Detection")
        self.resize(800, 600)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
