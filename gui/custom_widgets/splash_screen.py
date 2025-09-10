import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QSplashScreen


class SplashScreen(QSplashScreen):
    def __init__(self, minimum_display_time: float = 2.0):
        super().__init__()
        
        # Splash Screen immer on top anzeigen
        # self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Font-Setup für professionellen Look
        font = self.font()
        font.setPointSize(16)
        font.setBold(True)
        self.setFont(font)
        
        # Pixmap-Setup
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        pixmap = QPixmap(os.path.join(parent_dir, 'resources', 'hcc-dispo_klein_splash.png'))
        pixmap.setDevicePixelRatio(0.5)
        self.setPixmap(pixmap)
        
        # Progress-Tracking und Timing-Kontrolle
        self.current_step = ""
        self.progress = 0
        self.minimum_display_time = minimum_display_time
        self.start_time = None
        
        # Message-Layout-Konfiguration
        self.alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        self.color = Qt.GlobalColor.darkBlue
    
    def show(self):
        """Überschreibt show() um Start-Zeit zu erfassen"""
        super().show()
        import time
        self.start_time = time.time()
    
    def update_real_progress(self, step_name: str, progress: int):
        """
        Echte Fortschritts-Updates statt fake simulate()
        
        Args:
            step_name: Beschreibung des aktuellen Initialisierungsschritts
            progress: Fortschritt in Prozent (0-100)
        """
        self.current_step = step_name
        self.progress = progress
        
        # Multi-line Message mit Schritt-Info und Progress
        message = f'hcc-plan\n{step_name}...\n{progress}%'
        self.showMessage(message, self.alignment, self.color)
        
        # GUI-Updates forcieren für sofortige Anzeige
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
    
    def finish_when_ready(self, main_window):
        """
        Beendet Splash-Screen unter Berücksichtigung der Minimum-Display-Time
        
        Args:
            main_window: Hauptfenster für finish()-Methode
        """
        import time
        from PySide6.QtCore import QTimer
        
        if self.start_time is None:
            # Fallback: Sofort beenden, wenn start_time nicht gesetzt
            self.finish(main_window)
            return
        
        elapsed_time = time.time() - self.start_time
        
        if elapsed_time >= self.minimum_display_time:
            # Minimum-Zeit erreicht -> sofort beenden
            self.finish(main_window)
        else:
            # Noch warten bis Minimum-Zeit erreicht ist
            remaining_time = self.minimum_display_time - elapsed_time
            remaining_ms = int(remaining_time * 1000)
            
            # Letztes Progress-Update vor dem Beenden
            self.update_real_progress("Finalisierung", 100)
            
            # Timer für verzögerte Beendigung
            QTimer.singleShot(remaining_ms, lambda: self.finish(main_window))


class InitializationProgressCallback:
    """
    Callback-System für echte Fortschritts-Updates während der App-Initialisierung
    
    Verwaltet die Zuordnung von Initialisierungsschritten zu Progress-Prozentsätzen
    und kommuniziert diese an den SplashScreen.
    """
    
    def __init__(self, splash_screen: SplashScreen):
        self.splash = splash_screen
        self.current_step = 0
        
        # Definition der Initialisierungsschritte mit Progress-Gewichtung
        self.initialization_steps = [
            ("QApplication setup", 5),
            ("Logging-System setup", 15),
            ("Theme detection", 20),
            ("Translator setup", 25),
            ("Instance check", 30),
            ("MainWindow creation", 40),
            ("Screen size calculation", 50),
            ("Window display", 55),
            ("Tab restoration", 60),
            ("Finalisierung", 100)
        ]
        
        self.step_lookup = {step_name: progress for step_name, progress in self.initialization_steps}
    
    def update_progress(self, step_name: str):
        """
        Meldet Fortschritt für einen benannten Initialisierungsschritt
        
        Args:
            step_name: Name des Schritts (muss in initialization_steps definiert sein)
        """
        if step_name in self.step_lookup:
            progress = self.step_lookup[step_name]
            self.splash.update_real_progress(step_name, progress)
        else:
            # Fallback für unbekannte Schritte
            self.current_step += 1
            estimated_progress = min(95, self.current_step * 10)
            self.splash.update_real_progress(step_name, estimated_progress)
    
    def update_custom_progress(self, step_name: str, progress: int):
        """
        Ermöglicht custom Progress-Updates außerhalb der Standard-Schritte
        
        Args:
            step_name: Beschreibung des Schritts
            progress: Direkte Prozentangabe (0-100)
        """
        progress = max(0, min(100, progress))  # Sicherheits-Clipping
        self.splash.update_real_progress(step_name, progress)
