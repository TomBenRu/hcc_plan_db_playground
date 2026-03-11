# tools/translation_tool_gui.py
import os
import re
import subprocess
import sys
from typing import List, Optional

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QFileDialog,
    QGroupBox,
)


class TranslationLogic:
    """Reine Logik ohne Qt-Abhängigkeit – vollständig testbar."""

    def __init__(self, project_dir: str, translations_dir: str):
        self.project_dir = project_dir
        self.translations_dir = translations_dir

    def scan_languages(self) -> List[str]:
        """Liest alle Sprachen aus vorhandenen translations_XX.ts-Dateien."""
        if not os.path.isdir(self.translations_dir):
            return []
        languages = []
        for fname in os.listdir(self.translations_dir):
            m = re.match(r"translations_([a-z]{2,5})\.ts$", fname)
            if m:
                languages.append(m.group(1))
        return sorted(languages)

    def find_python_files(self) -> List[str]:
        """Findet rekursiv alle .py-Dateien im Projektverzeichnis."""
        py_files = []
        skip_dirs = {".venv", "venv", ".git", "__pycache__"}
        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))
        return py_files

    def create_ts_file(self, ts_path: str, lang: str) -> None:
        """Erstellt ein neues leeres .ts-File für die angegebene Sprache."""
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n'
                    f'<!DOCTYPE TS>\n'
                    f'<TS version="2.1" language="{lang}">\n'
                    f'</TS>\n')

    def find_lupdate(self) -> Optional[str]:
        path = os.path.join(self.project_dir, ".venv", "Lib",
                            "site-packages", "PySide6", "lupdate.exe")
        return path if os.path.exists(path) else None

    def find_lrelease(self) -> Optional[str]:
        path = os.path.join(self.project_dir, ".venv", "Lib",
                            "site-packages", "PySide6", "lrelease.exe")
        return path if os.path.exists(path) else None

    def run_update(self, no_obsolete: bool) -> tuple[bool, str]:
        """Führt lupdate aus. Gibt (success, output) zurück."""
        lupdate = self.find_lupdate()
        if not lupdate:
            return False, "Fehler: lupdate nicht gefunden."

        os.makedirs(self.translations_dir, exist_ok=True)
        py_files = self.find_python_files()
        if not py_files:
            return False, "Fehler: Keine Python-Dateien gefunden."

        languages = self.scan_languages()
        if not languages:
            return False, "Keine Sprachen gefunden. Bitte erst eine Sprache anlegen."

        output_parts = []
        success = True
        for lang in languages:
            ts_file = os.path.join(self.translations_dir, f"translations_{lang}.ts")
            if not os.path.exists(ts_file):
                self.create_ts_file(ts_file, lang)

            cmd = [lupdate, *py_files, "-ts", ts_file,
                   "-no-recursive", "-locations", "absolute"]
            if no_obsolete:
                cmd.append("-no-obsolete")

            output_parts.append(f"Ausführen: lupdate für '{lang}'...")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output_parts.append(result.stdout or f"'{lang}' erfolgreich aktualisiert.")
            except subprocess.CalledProcessError as e:
                output_parts.append(
                    f"FEHLER bei '{lang}' (Code {e.returncode}):\n{e.stderr}")
                success = False

        return success, "\n".join(output_parts)

    def run_compile(self) -> tuple[bool, str]:
        """Führt lrelease aus. Gibt (success, output) zurück."""
        lrelease = self.find_lrelease()
        if not lrelease:
            return False, "Fehler: lrelease nicht gefunden."

        if not os.path.isdir(self.translations_dir):
            return False, f"Fehler: Translations-Ordner nicht gefunden: {self.translations_dir}"

        output_parts = []
        success = True
        for fname in os.listdir(self.translations_dir):
            if not fname.endswith(".ts"):
                continue
            ts_file = os.path.join(self.translations_dir, fname)
            qm_file = ts_file.replace(".ts", ".qm")
            cmd = [lrelease, ts_file, "-qm", qm_file]
            output_parts.append(f"Kompiliere: {fname}...")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                output_parts.append(result.stdout or f"{fname} → {os.path.basename(qm_file)} OK")
            except subprocess.CalledProcessError as e:
                output_parts.append(
                    f"FEHLER bei {fname} (Code {e.returncode}):\n{e.stderr}")
                success = False

        return success, "\n".join(output_parts)


class TranslationWorker(QThread):
    finished = Signal(bool, str)   # (success, output)

    def __init__(self, logic: TranslationLogic, operation: str,
                 no_obsolete: bool = False):
        super().__init__()
        self.logic = logic
        self.operation = operation      # "update" | "compile"
        self.no_obsolete = no_obsolete

    def run(self):
        if self.operation == "update":
            success, output = self.logic.run_update(self.no_obsolete)
        else:
            success, output = self.logic.run_compile()
        self.finished.emit(success, output)


class TranslationToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Translation Tool")
        self.setMinimumWidth(700)

        # Default-Pfade
        self._project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._translations_dir = os.path.join(self._project_dir, "gui", "translations")

        self._worker: Optional[TranslationWorker] = None
        self._setup_ui()
        self._refresh_languages()
        self._check_tools()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Anleitung ---
        help_group = QGroupBox("Anleitung")
        help_layout = QVBoxLayout(help_group)
        help_text = QLabel(
            "<b>1. Verzeichnisse</b> – Projektroot und Translations-Ordner einstellen.<br>"
            "<b>2. Translations aktualisieren</b> – Durchsucht alle .py-Dateien nach "
            "<code>tr()</code>-Aufrufen und schreibt neue Strings in die .ts-Dateien (lupdate).<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<i>Option &bdquo;Obsolete entfernen&ldquo;</i>: "
            "L&ouml;scht Strings aus den .ts-Dateien, die im Code nicht mehr vorkommen.<br>"
            "<b>3. Translations kompilieren</b> &ndash; Erzeugt aus den .ts-Dateien die "
            "bin&auml;ren .qm-Dateien, die die Anwendung l&auml;dt (lrelease).<br>"
            "<b>4. Neue Sprache</b> &ndash; Legt eine leere .ts-Datei f&uuml;r einen neuen "
            "Sprachcode an (z.B. <code>es</code> f&uuml;r Spanisch). "
            "Danach &bdquo;Translations aktualisieren&ldquo; ausf&uuml;hren."
        )
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.RichText)
        help_layout.addWidget(help_text)
        layout.addWidget(help_group)

        # --- Verzeichnis-Gruppe ---
        dir_group = QGroupBox("Verzeichnisse")
        dir_layout = QVBoxLayout(dir_group)

        # Projektverzeichnis
        proj_row = QHBoxLayout()
        proj_row.addWidget(QLabel("Projektverzeichnis:"))
        self.le_project = QLineEdit(self._project_dir)
        self.le_project.textChanged.connect(self._on_project_dir_changed)
        proj_row.addWidget(self.le_project)
        btn_proj = QPushButton("...")
        btn_proj.setFixedWidth(30)
        btn_proj.clicked.connect(self._browse_project_dir)
        proj_row.addWidget(btn_proj)
        dir_layout.addLayout(proj_row)

        # Translations-Ordner
        trans_row = QHBoxLayout()
        trans_row.addWidget(QLabel("Translations-Ordner:"))
        self.le_translations = QLineEdit(self._translations_dir)
        self.le_translations.textChanged.connect(self._on_translations_dir_changed)
        trans_row.addWidget(self.le_translations)
        btn_trans = QPushButton("...")
        btn_trans.setFixedWidth(30)
        btn_trans.clicked.connect(self._browse_translations_dir)
        trans_row.addWidget(btn_trans)
        dir_layout.addLayout(trans_row)

        layout.addWidget(dir_group)

        # --- Tool-Status ---
        self.lbl_tool_status = QLabel("")
        self.lbl_tool_status.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.lbl_tool_status)

        # --- Sprachen-Anzeige ---
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Erkannte Sprachen:"))
        self.lbl_languages = QLabel("–")
        lang_row.addWidget(self.lbl_languages)
        lang_row.addStretch()
        layout.addLayout(lang_row)

        # --- Aktionen ---
        action_group = QGroupBox("Aktionen")
        action_layout = QVBoxLayout(action_group)

        self.chk_no_obsolete = QCheckBox("Obsolete Übersetzungen entfernen (--no-obsolete)")
        action_layout.addWidget(self.chk_no_obsolete)

        btn_row = QHBoxLayout()
        self.btn_update = QPushButton("Translations aktualisieren (lupdate)")
        self.btn_update.clicked.connect(self._on_update)
        btn_row.addWidget(self.btn_update)

        self.btn_compile = QPushButton("Translations kompilieren (lrelease)")
        self.btn_compile.clicked.connect(self._on_compile)
        btn_row.addWidget(self.btn_compile)
        action_layout.addLayout(btn_row)

        layout.addWidget(action_group)

        # --- Neue Sprache ---
        new_lang_group = QGroupBox("Neue Sprache anlegen")
        new_lang_layout = QHBoxLayout(new_lang_group)
        new_lang_layout.addWidget(QLabel('Sprachcode (z.B. "es"):'))
        self.le_new_lang = QLineEdit()
        self.le_new_lang.setMaximumWidth(80)
        self.le_new_lang.setPlaceholderText("es")
        new_lang_layout.addWidget(self.le_new_lang)
        self.btn_add_lang = QPushButton("Anlegen")
        self.btn_add_lang.clicked.connect(self._on_add_language)
        new_lang_layout.addWidget(self.btn_add_lang)
        new_lang_layout.addStretch()
        layout.addWidget(new_lang_group)

        # --- Ausgabe ---
        output_group = QGroupBox("Ausgabe")
        output_layout = QVBoxLayout(output_group)
        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setMinimumHeight(200)
        output_layout.addWidget(self.txt_output)
        layout.addWidget(output_group)

    # --- Verzeichnis-Callbacks ---
    def _browse_project_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Projektverzeichnis wählen",
                                                self.le_project.text())
        if path:
            self.le_project.setText(path)

    def _browse_translations_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Translations-Ordner wählen",
                                                self.le_translations.text())
        if path:
            self.le_translations.setText(path)

    def _on_project_dir_changed(self, text: str):
        self._project_dir = text
        self._check_tools()

    def _on_translations_dir_changed(self, text: str):
        self._translations_dir = text
        self._refresh_languages()

    # --- Sprachen ---
    def _refresh_languages(self):
        logic = self._make_logic()
        langs = logic.scan_languages()
        self.lbl_languages.setText(", ".join(langs) if langs else "(keine .ts-Dateien gefunden)")

    # --- Tool-Verfügbarkeit ---
    def _check_tools(self):
        logic = self._make_logic()
        lupdate_ok = logic.find_lupdate() is not None
        lrelease_ok = logic.find_lrelease() is not None
        self.btn_update.setEnabled(lupdate_ok)
        self.btn_compile.setEnabled(lrelease_ok)

        warnings = []
        if not lupdate_ok:
            warnings.append("lupdate nicht gefunden")
        if not lrelease_ok:
            warnings.append("lrelease nicht gefunden")

        if warnings:
            self.lbl_tool_status.setText(
                f'<span style="color:orange;">⚠ {", ".join(warnings)}</span>')
        else:
            self.lbl_tool_status.setText(
                '<span style="color:green;">✓ Qt-Tools gefunden</span>')

    # --- Hilfsfunktionen ---
    def _make_logic(self) -> TranslationLogic:
        return TranslationLogic(self._project_dir, self._translations_dir)

    def _set_running(self, running: bool):
        self.btn_update.setEnabled(not running)
        self.btn_compile.setEnabled(not running)
        self.btn_add_lang.setEnabled(not running)

    def _append_output(self, success: bool, text: str):
        if success:
            self.txt_output.append(text)
        else:
            self.txt_output.append(
                f'<span style="color:red;">{text.replace(chr(10), "<br>")}</span>')

    # --- Aktionen ---
    def _on_update(self):
        self._set_running(True)
        self.txt_output.append("→ Translations werden aktualisiert...")
        worker = TranslationWorker(self._make_logic(), "update",
                                   self.chk_no_obsolete.isChecked())
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_compile(self):
        self._set_running(True)
        self.txt_output.append("→ Translations werden kompiliert...")
        worker = TranslationWorker(self._make_logic(), "compile")
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self, success: bool, output: str):
        self._append_output(success, output)
        logic = self._make_logic()
        lupdate_ok = logic.find_lupdate() is not None
        lrelease_ok = logic.find_lrelease() is not None
        self.btn_update.setEnabled(lupdate_ok)
        self.btn_compile.setEnabled(lrelease_ok)
        self.btn_add_lang.setEnabled(True)

    def _on_add_language(self):
        lang = self.le_new_lang.text().strip().lower()
        if not lang or not re.match(r"^[a-z]{2,5}$", lang):
            self._append_output(False, "Fehler: Ungültiger Sprachcode (2-5 Kleinbuchstaben).")
            return
        os.makedirs(self._translations_dir, exist_ok=True)
        ts_path = os.path.join(self._translations_dir, f"translations_{lang}.ts")
        if os.path.exists(ts_path):
            self._append_output(False, f"Fehler: '{os.path.basename(ts_path)}' existiert bereits.")
            return
        logic = self._make_logic()
        logic.create_ts_file(ts_path, lang)
        self.le_new_lang.clear()
        self._refresh_languages()
        self._append_output(True, f"Sprache '{lang}' angelegt: {ts_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TranslationToolWindow()
    window.show()
    sys.exit(app.exec())
