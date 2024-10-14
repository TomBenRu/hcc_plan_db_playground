import logging
import os.path
import sys
import time
import winreg

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import QApplication, QMessageBox

from gui.custom_widgets.splash_screen import SplashScreen
from tools import proof_only_one_instance
from tools.screen import Screen


def is_windows_dark_mode():
    try:
        # Öffne den Registry-Schlüssel
        registry = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                  r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
        # Lese den Wert von 'AppsUseLightTheme'
        apps_use_light_theme, _ = winreg.QueryValueEx(registry, 'AppsUseLightTheme')
        winreg.CloseKey(registry)

        # Wenn der Wert 1 ist, wird der Lightmode verwendet, bei 0 der Darkmode
        return apps_use_light_theme == 0
    except FileNotFoundError:
        # Falls der Registry-Schlüssel nicht gefunden wird, Lightmode als Standard
        return False


def set_dark_mode(app):
    # Erstelle eine Darkmode-Farbpalette
    dark_palette = QPalette()

    # Allgemeine Farben
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))  # Hintergrundfarbe der Fenster
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)        # Textfarbe
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))    # Hintergrundfarbe von Eingabefeldern
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))  # Alternativer Hintergrund
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)       # Tooltip-Hintergrund
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)       # Tooltip-Text
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)              # Standard Text
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))  # Schaltflächen-Hintergrund
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)        # Schaltflächen-Text
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)          # Hervorhebungen

    # Highlight Farben
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))  # Ausgewählte Elemente
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)    # Text von ausgewählten Elementen

    # Setze die erstellte Darkmode-Palette
    app.setPalette(dark_palette)


app = QApplication(sys.argv)
app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'hcc-dispo_klein.png')))

# Überprüfe, ob der Windows-Darkmode deaktiviert ist
if not is_windows_dark_mode():
    # Setze Darkmode für die Anwendung, falls Windows nicht im Darkmode ist
    set_dark_mode(app)

# proof_only_one_instance:
if not proof_only_one_instance.check():
    QMessageBox.critical(None, "HCC Dispo", "hcc-dispo wird bereits ausgeführt.\n"
                                            "Sie können nur eine Instanz des Programms öffnen.")
    sys.exit(0)

splash = SplashScreen()
splash.show()
splash.simulate_loading()


from gui.main_window import MainWindow

logging.basicConfig(filename='pony.log', level=logging.INFO,
                    format='%(created)f-%(asctime)s\n%(message)s\n')
logging.Formatter.converter = time.gmtime

app.setStyle('Fusion')

Screen.set_screen_size()
window = MainWindow(app, Screen.screen_width, Screen.screen_height)

window.show()
splash.finish(window)
