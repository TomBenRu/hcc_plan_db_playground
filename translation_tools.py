import os
import subprocess
import sys
from typing import List, Optional
from PySide6.QtCore import QLibraryInfo


class TranslationManager:
    def __init__(self, project_dir: str = "."):
            
        # Translations-Verzeichnis ist jetzt im source-Ordner
        self.translations_dir = os.path.join('gui', "translations")
        self.languages = ["en", "de"]
        
        # Get venv path for Qt tools, relativ zum Projektverzeichnis
        self.venv_pyside_dir = os.path.join(".venv", "Lib", "site-packages", "PySide6")
        
        # Find lupdate and lrelease executables
        self.lupdate_path = os.path.join(self.venv_pyside_dir, "lupdate.exe")
        self.lrelease_path = os.path.join(self.venv_pyside_dir, "lrelease.exe")
        
        # Verify tools exist
        if not os.path.exists(self.lupdate_path):
            print(f"Error: lupdate not found at {self.lupdate_path}")
            self.lupdate_path = None
            
        if not os.path.exists(self.lrelease_path):
            print(f"Error: lrelease not found at {self.lrelease_path}")
            self.lrelease_path = None

    def update_translations(self):
        """Updates all .ts files with new translations from source code while preserving existing translations"""
        if not self.lupdate_path:
            print("Error: lupdate tool not found. Cannot update translations.")
            return
        
        os.makedirs(self.translations_dir, exist_ok=True)
        python_files = self._find_python_files()
        
        print(f"Found {len(python_files)} Python files to process")
        print(f"Using lupdate from: {self.lupdate_path}")

        for lang in self.languages:
            ts_file = os.path.join(self.translations_dir, f"translations_{lang}.ts")
            if not os.path.exists(ts_file):
                self._create_ts_file(ts_file, lang)

            try:
                cmd = [
                    self.lupdate_path,
                    *python_files,
                    "-ts",
                    ts_file,
                    "-no-recursive",  # Verhindert Suche in Unterverzeichnissen
                    "-no-obsolete",   # Entfernt nicht mehr verwendete Übersetzungen
                    "-locations", "absolute"  # Verwendet absolute Pfade für Locations
                ]
                print(f"\nExecuting command:\n{' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                print(f"Command output:\n{result.stdout}")
                print(f"Updated translations for {lang}")
            except subprocess.CalledProcessError as e:
                print(f"Error updating translations for {lang}:")
                print(f"Command failed with return code {e.returncode}")
                print(f"Output: {e.output}")
                print(f"Error: {e.stderr}")

    def compile_translations(self):
        """Compiles all .ts files to .qm files"""
        if not self.lrelease_path:
            print("Error: lrelease tool not found. Cannot compile translations.")
            return
            
        for file in os.listdir(self.translations_dir):
            if file.endswith(".ts"):
                ts_file = os.path.join(self.translations_dir, file)
                qm_file = os.path.join(self.translations_dir, file.replace(".ts", ".qm"))
                try:
                    cmd = [
                        self.lrelease_path,
                        ts_file,
                        "-qm",
                        qm_file
                    ]
                    print(f"\nExecuting command:\n{' '.join(cmd)}")
                    
                    result = subprocess.run(
                        cmd,
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    print(f"Command output:\n{result.stdout}")
                    print(f"Compiled {file} to {os.path.basename(qm_file)}")
                except subprocess.CalledProcessError as e:
                    print(f"Error compiling {file}:")
                    print(f"Command failed with return code {e.returncode}")
                    print(f"Output: {e.output}")
                    print(f"Error: {e.stderr}")

    def _find_python_files(self) -> List[str]:
        """Recursively finds all Python files in the project directory"""
        python_files = []
        for root, _, files in os.walk(os.path.dirname(__file__)):
            if "venv" in root or ".git" in root:  # Skip virtual environment and git directories
                continue
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))
        return python_files

    def _create_ts_file(self, ts_file: str, lang: str):
        """Creates a new .ts file for the specified language"""
        with open(ts_file, 'w', encoding='utf-8') as f:
            f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="{lang}">
</TS>''')


def main():
    manager = TranslationManager()

    if input("Update translations? (y/n): ").lower() == "y":
        print("Updating translation files...")
        manager.update_translations()
        print("Translation files updated.")
    elif input("Compile translations? (y/n): ").lower() == "y":
        print("\nCompiling translation files...")
        manager.compile_translations()
        print("Translation files compiled.")


if __name__ == "__main__":
    main()