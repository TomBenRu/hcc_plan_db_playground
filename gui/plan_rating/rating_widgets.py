"""
UI-Widgets für die Planbewertungs-Anzeige.

Enthält:
- ScoreRing: Kreisförmige Anzeige des Gesamt-Scores
- ObjectiveCard: Karte für einzelne Kriterien
- PlanRatingWidget: Haupt-Container für das Slide-In-Menu
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont

from gui.widget_styles import plan_rating as styles
from .rating_data import PlanRating, ObjectiveScore


class ScoreRing(QWidget):
    """
    Kreisförmige Score-Anzeige mit farbigem Ring.
    """

    RING_WIDTH = 8
    RING_SIZE = 80

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedSize(self.RING_SIZE, self.RING_SIZE)
        self._score = 0.0
        self._color = 'green'

    def set_score(self, score: float, color: str):
        self._score = score
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRect(
            self.RING_WIDTH // 2,
            self.RING_WIDTH // 2,
            self.width() - self.RING_WIDTH,
            self.height() - self.RING_WIDTH
        )

        # Hintergrund-Ring
        track_pen = QPen(QColor(styles.SCORE_COLORS['track']))
        track_pen.setWidth(self.RING_WIDTH)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        # Fortschritts-Ring
        color_hex = styles.SCORE_COLORS.get(self._color, styles.SCORE_COLORS['green'])
        progress_pen = QPen(QColor(color_hex))
        progress_pen.setWidth(self.RING_WIDTH)
        progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(progress_pen)

        span_angle = int(-self._score * 3.6 * 16)
        painter.drawArc(rect, 90 * 16, span_angle)

        # Score-Text
        painter.setPen(QColor(styles.SCORE_COLORS['text']))
        font = QFont()
        font.setPixelSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self._score:.0f}%")


class ObjectiveCard(QFrame):
    """
    Kompakte Karte für ein einzelnes Bewertungskriterium.
    Horizontales Layout: Icon+Name links, Score rechts.
    """

    def __init__(self, objective: ObjectiveScore, parent: QWidget = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(styles.OBJECTIVE_CARD_STYLE)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)

        # Icon + Name (links)
        self.lb_name = QLabel(f"{objective.icon} {objective.display_name}")
        self.lb_name.setStyleSheet(styles.CARD_HEADER_STYLE)
        layout.addWidget(self.lb_name, 1)

        # Score (rechts)
        self.lb_score = QLabel(f"{objective.normalized_score:.0f}%")
        self.lb_score.setStyleSheet(styles.get_card_score_style(objective.color))
        self.lb_score.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.lb_score)

        # Tooltip
        self.setToolTip(objective.description)

        # Größe
        self.setMinimumHeight(36)
        self.setMaximumHeight(44)


class PlanRatingWidget(QWidget):
    """
    Haupt-Widget für die Planbewertung im Slide-In-Menu.
    """

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._rating: PlanRating | None = None
        self._card_widgets: list[ObjectiveCard] = []
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 10, 5, 10)
        self.main_layout.setSpacing(8)

        # Header
        self.lb_header = QLabel(self.tr("Planbewertung"))
        self.lb_header.setStyleSheet(styles.HEADER_STYLE)
        self.lb_header.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.lb_header)

        # Score Ring (zentriert)
        ring_container = QWidget()
        ring_layout = QHBoxLayout(ring_container)
        ring_layout.setContentsMargins(0, 5, 0, 5)
        self.score_ring = ScoreRing()
        ring_layout.addStretch()
        ring_layout.addWidget(self.score_ring)
        ring_layout.addStretch()
        self.main_layout.addWidget(ring_container)

        # Container für Karten
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(5)
        self.main_layout.addWidget(self.cards_container)

        # Timestamp
        self.lb_timestamp = QLabel()
        self.lb_timestamp.setStyleSheet(styles.TIMESTAMP_STYLE)
        self.lb_timestamp.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.lb_timestamp)

        # Platzhalter "Keine Bewertung"
        self.lb_no_rating = QLabel(self.tr("Noch keine Bewertung.\n\nKlicken Sie auf\n'Bewertung aktualisieren'."))
        self.lb_no_rating.setStyleSheet(styles.NO_RATING_STYLE)
        self.lb_no_rating.setAlignment(Qt.AlignCenter)
        self.lb_no_rating.setWordWrap(True)
        self.main_layout.addWidget(self.lb_no_rating)

        # Stretch
        self.main_layout.addStretch()

        # Initial: Zeige Platzhalter
        self._show_no_rating_state()

    def set_rating(self, rating: PlanRating):
        """Aktualisiert die Anzeige mit neuer Bewertung."""
        self._rating = rating
        self.lb_no_rating.hide()

        # Score Ring
        self.score_ring.set_score(rating.overall_score, rating.overall_color)
        self.score_ring.show()

        # Alte Karten entfernen
        for card in self._card_widgets:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._card_widgets.clear()

        # Neue Karten erstellen
        for obj in rating.objective_scores:
            card = ObjectiveCard(obj)
            self.cards_layout.addWidget(card)
            self._card_widgets.append(card)

        self.cards_container.show()

        # Timestamp
        source = self.tr("Solver") if rating.is_from_solver else self.tr("manuell")
        timestamp_text = rating.calculation_timestamp.strftime("%H:%M:%S")
        self.lb_timestamp.setText(f"{timestamp_text} ({source})")
        self.lb_timestamp.show()

    def clear_rating(self):
        """Löscht die Bewertung."""
        self._rating = None
        self._show_no_rating_state()

    def _show_no_rating_state(self):
        """Zeigt Platzhalter."""
        self.score_ring.hide()
        self.cards_container.hide()
        self.lb_timestamp.hide()
        self.lb_no_rating.show()

    def get_current_rating(self) -> PlanRating | None:
        return self._rating

    def sizeHint(self) -> QSize:
        """Gibt die empfohlene Größe zurück (für Container-Berechnung)."""
        # Header: ~30px, Ring: ~90px, 4 Karten: 4*44px, Timestamp: ~20px, Spacing: ~50px
        height = 30 + 90 + (4 * 44) + 20 + 50
        return QSize(250, height)

    def minimumSizeHint(self) -> QSize:
        """Minimale Größe."""
        return QSize(200, 300)
