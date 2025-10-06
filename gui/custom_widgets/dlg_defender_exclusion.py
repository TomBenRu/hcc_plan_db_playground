"""
Windows Defender Exclusion Dialog

Dialog zur Anfrage, ob die Anwendung vom Windows Defender-Scan ausgeschlossen werden soll.
"""
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpacerItem,
    QSizePolicy
)


class DefenderExclusionResult(Enum):
    """Ergebnis des Defender-Exclusion-Dialogs"""
    ADD_NOW = "add_now"           # Jetzt ausschließen
    LATER = "later"               # Später fragen
    NEVER_ASK = "never_ask"       # Nie wieder fragen


class DlgDefenderExclusion(QDialog):
    """
    Dialog zur Anfrage, ob die Anwendung vom Windows Defender ausgeschlossen werden soll.
    
    Zeigt Informationen über die Funktion und mögliche Sicherheitsimplikationen an.
    Bietet drei Optionen: Jetzt ausschließen, Später, Nie wieder fragen.
    """
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.result = DefenderExclusionResult.LATER  # Default
        self._setup_ui()
        
    def _setup_ui(self):
        """Erstellt die UI-Komponenten"""
        self.setWindowTitle(self.tr("Windows Defender Optimierung"))
        self.setMinimumWidth(500)
        
        # Haupt-Layout
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # === Kopfbereich: Titel und Info-Icon ===
        header_layout = QHBoxLayout()
        
        # Info-Icon (optional - kann später durch echtes Icon ersetzt werden)
        icon_label = QLabel("ℹ️")
        icon_label.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)
        
        # Titel
        title_label = QLabel(self.tr("<h3>Programmstart beschleunigen</h3>"))
        header_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignTop)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # === Informationstext ===
        info_text = self.tr(
            "<p>Der Windows Defender-Scan kann den Start dieser Anwendung verzögern.</p>"
            "<p><b>Sie können die Anwendung vom Defender-Scan ausschließen, um den Start zu beschleunigen.</b></p>"
            "<p>Für diese Aktion sind Administrator-Rechte erforderlich. "
            "Es erscheint ein Bestätigungsdialog, in dem Sie Ihre Credentials eingeben können.</p>"
            "<p style='color: #888;'><i>Hinweis: Das Ausschließen reduziert den Schutz für diese spezifische Anwendung. "
            "Die allgemeine Sicherheit Ihres Systems bleibt davon unberührt.</i></p>"
        )
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info_label)
        
        # Spacer vor Buttons
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # === Button-Bereich ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # "Nie wieder fragen" Button (links)
        self.btn_never_ask = QPushButton(self.tr("Nie wieder fragen"))
        self.btn_never_ask.clicked.connect(self._on_never_ask)
        button_layout.addWidget(self.btn_never_ask)
        
        # Spacer zwischen links und rechts
        button_layout.addStretch()
        
        # "Später" Button
        self.btn_later = QPushButton(self.tr("Später"))
        self.btn_later.clicked.connect(self._on_later)
        button_layout.addWidget(self.btn_later)
        
        # "Jetzt ausschließen" Button (primär/hervorgehoben)
        self.btn_add_now = QPushButton(self.tr("Jetzt ausschließen"))
        self.btn_add_now.setDefault(True)  # Enter-Taste triggert diesen Button
        self.btn_add_now.clicked.connect(self._on_add_now)
        
        # Styling für primären Button (optional - kann später angepasst werden)
        self.btn_add_now.setStyleSheet("""
            QPushButton {
                background-color: #006d6d;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #008080;
            }
            QPushButton:pressed {
                background-color: #005555;
            }
        """)
        
        button_layout.addWidget(self.btn_add_now)
        
        layout.addLayout(button_layout)
        
    def _on_add_now(self):
        """Handler für "Jetzt ausschließen" Button"""
        self.result = DefenderExclusionResult.ADD_NOW
        self.accept()
        
    def _on_later(self):
        """Handler für "Später" Button"""
        self.result = DefenderExclusionResult.LATER
        self.reject()
        
    def _on_never_ask(self):
        """Handler für "Nie wieder fragen" Button"""
        self.result = DefenderExclusionResult.NEVER_ASK
        self.reject()
    
    def get_result(self) -> DefenderExclusionResult:
        """
        Gibt das Ergebnis der Dialog-Interaktion zurück.
        
        Returns:
            DefenderExclusionResult: Die gewählte Option
        """
        return self.result
