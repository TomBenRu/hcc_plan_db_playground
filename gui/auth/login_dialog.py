"""Login-Dialog fuer den Desktop-Client.

Wird beim App-Start gezeigt, falls kein gueltiger Silent-Login via
Refresh-Token moeglich ist. Gibt dem User die Option "Angemeldet bleiben",
wodurch der Refresh-Token im OS-Keyring persistiert wird (Standard:
abgewaehlt, d. h. keine Persistenz).
"""

from __future__ import annotations

import os
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gui.api_client.client import ApiAuthError, ApiError, DesktopApiClient


class LoginDialog(QDialog):
    def __init__(self, client: DesktopApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self.setWindowTitle(self.tr("Anmelden"))
        self.setModal(True)
        self.setMinimumWidth(420)

        # ── Server-URL (editierbar; bei DESKTOP_API_URL-Env-Var read-only) ───
        env_override_active = bool(os.environ.get("DESKTOP_API_URL"))
        self._le_server_url = QLineEdit(client.base_url)
        self._le_server_url.setPlaceholderText("https://example.onrender.com")
        if env_override_active:
            self._le_server_url.setReadOnly(True)
            self._le_server_url.setToolTip(
                self.tr(
                    "Per Umgebungsvariable DESKTOP_API_URL festgelegt — "
                    "in dieser Sitzung nicht aenderbar."
                )
            )
        else:
            self._le_server_url.setToolTip(
                self.tr(
                    "Adresse der Web-API (z. B. https://hcc-plan.onrender.com). "
                    "Wird gespeichert und beim naechsten Start vorausgewaehlt."
                )
            )

        # ── Eingabefelder ────────────────────────────────────────────────────
        self._le_email = QLineEdit()
        self._le_email.setPlaceholderText(self.tr("name@firma.de"))
        self._le_password = QLineEdit()
        self._le_password.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow(self.tr("Server:"), self._le_server_url)
        form.addRow(self.tr("E-Mail:"), self._le_email)
        form.addRow(self.tr("Passwort:"), self._le_password)

        self._chk_remember = QCheckBox(self.tr("Angemeldet bleiben"))
        self._chk_remember.setChecked(False)
        self._chk_remember.setToolTip(
            self.tr(
                "Speichert den Refresh-Token im System-Schluesselbund, sodass beim "
                "naechsten Start keine Eingabe noetig ist. Nur auf vertrauten Geraeten aktivieren."
            )
        )

        # ── Passwort-vergessen-Link (oeffnet Web-Reset-Flow im Browser) ──────
        # Wird live aus dem Server-URL-Feld aktualisiert, damit ein User-Wechsel
        # auf einen anderen Server den Reset-Flow gegen den richtigen Host fuehrt.
        self._lbl_forgot = QLabel()
        self._lbl_forgot.setOpenExternalLinks(True)
        self._lbl_forgot.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._le_server_url.textChanged.connect(self._update_forgot_link)
        self._update_forgot_link(self._le_server_url.text())

        # ── Fehlermeldung (nur bei Bedarf sichtbar) ──────────────────────────
        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #c0392b;")
        self._error_label.setVisible(False)

        # ── Buttons ──────────────────────────────────────────────────────────
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Anmelden"))
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Abbrechen"))
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)

        # ── Layout ───────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._chk_remember)
        layout.addWidget(self._lbl_forgot)
        layout.addWidget(self._error_label)
        layout.addWidget(self._buttons)

        self._le_email.setFocus()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _update_forgot_link(self, server_url: str) -> None:
        url = server_url.rstrip("/")
        if not url:
            self._lbl_forgot.setText("")
            return
        forgot_url = escape(f"{url}/auth/forgot-password", quote=True)
        self._lbl_forgot.setText(
            f'<a href="{forgot_url}">{self.tr("Passwort vergessen?")}</a>'
        )

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        server_url = self._le_server_url.text().strip()
        email = self._le_email.text().strip()
        password = self._le_password.text()
        if not server_url:
            self._show_error(self.tr("Bitte Server-URL angeben."))
            return
        if not email or not password:
            self._show_error(self.tr("Bitte E-Mail-Adresse und Passwort angeben."))
            return

        self._set_busy(True)
        try:
            # Falls der User die URL geaendert hat: Client umstellen + persistieren.
            # set_base_url() fuehrt zwingend logout() durch, damit alte Tokens vom
            # vorherigen Server nicht in die neuen Requests gemischt werden.
            if server_url.rstrip("/") != self._client.base_url:
                self._client.set_base_url(server_url)
            self._client.login(email, password, remember=self._chk_remember.isChecked())
        except ApiAuthError:
            self._show_error(self.tr("Ungueltige E-Mail-Adresse oder Passwort."))
            self._le_password.clear()
            self._le_password.setFocus()
            return
        except ApiError as exc:
            self._show_error(self.tr("Anmeldung fehlgeschlagen: %s") % exc.detail)
            return
        except Exception as exc:  # Netzwerk, Server unerreichbar etc.
            self._show_error(
                self.tr("Server nicht erreichbar: %s") % exc
            )
            return
        finally:
            self._set_busy(False)

        self.accept()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _set_busy(self, busy: bool) -> None:
        self._buttons.setEnabled(not busy)
        # Server-URL bleibt bei aktivem env-Override durchgehend read-only;
        # ansonsten waehrend des Login-Requests sperren.
        if not self._le_server_url.isReadOnly():
            self._le_server_url.setEnabled(not busy)
        self._le_email.setEnabled(not busy)
        self._le_password.setEnabled(not busy)
        self._chk_remember.setEnabled(not busy)