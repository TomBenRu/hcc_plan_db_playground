
def main():
    import logging
    import os
    import platform
    import sys
    import traceback

    from PySide6.QtWidgets import QApplication, QMessageBox

    from gui.custom_widgets.splash_screen import SplashScreen, InitializationProgressCallback
    from gui.app_initialization import initialize_application_with_progress

    # Einmalige OS-Erkennung (Best Practice)
    is_windows_os = platform.system() == "Windows"

    # Windows 11 Dark Mode: Umgebungsvariablen setzen BEVOR Qt initialisiert wird
    if is_windows_os:
        os.environ['QT_QPA_PLATFORM'] = 'windows:darkmode=2'
        os.environ['QT_STYLE_OVERRIDE'] = 'Fusion'

    # Minimales Logging für frühe App-Phase (detailliertes Logging erfolgt in initialize_system_infrastructure)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Application starting...")

    app = QApplication(sys.argv)

    # === Auth vor allem anderen ===
    # Silent-Login via Keyring-Refresh-Token; sonst LoginDialog. Abbruch → Exit.
    from gui.auth.bootstrap import ensure_authenticated
    if not ensure_authenticated():
        logging.info("Login abgebrochen — App wird beendet.")
        sys.exit(0)

    # === Splash Screen Setup ===
    try:
        splash = SplashScreen(minimum_display_time=2.0)  # Option A: 2s Minimum-Display-Time
        splash.show()

        # Progress-Callback erstellen für echte Fortschrittsanzeige
        progress_callback = InitializationProgressCallback(splash)
        progress_callback.update_progress("QApplication setup")  # Initial 5%

    except Exception as e:
        logging.error(f"Splash screen error: {e}")
        splash = None
        progress_callback = None

    # === Hauptinitialisierung ===
    try:
        if progress_callback:
            logging.info("Initializing with progress updates")
        else:
            logging.warning("Initializing without progress updates (splash screen failed)")

        window = initialize_application_with_progress(app, progress_callback, splash_screen=splash, is_windows_os=is_windows_os)

        # Splash-Screen mit Minimum-Display-Time beenden
        if splash:
            splash.finish_when_ready(window)  # NEU: Respektiert 2s Minimum-Display-Time

    except Exception as e:
        logging.critical(f"Failed to initialize application: {e}")
        logging.critical(f"Stack trace:\n{traceback.format_exc()}")
        if splash:
            splash.close()
        QMessageBox.critical(None, "Startup Error", f"Failed to start application:\n{e}")
        sys.exit(1)

    return app
