# tools/translation_tool_gui.py
import os
import re
import subprocess
import sys
from typing import List, Optional


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

        output_parts = []
        success = True
        for lang in self.scan_languages():
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
