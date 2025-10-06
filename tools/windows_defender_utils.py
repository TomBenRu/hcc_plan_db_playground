"""
Windows Defender Utility-Funktionen

Stellt Funktionen bereit, um die Anwendung vom Windows Defender-Scan auszuschließen.
Dies kann den Programmstart beschleunigen, wenn der Virenscan Verzögerungen verursacht.
"""
import ctypes
import logging
import subprocess
import sys
from pathlib import Path


def is_admin() -> bool:
    """
    Prüft, ob die Anwendung mit Administrator-Rechten läuft.
    
    Returns:
        bool: True wenn Admin-Rechte vorhanden, sonst False
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception as e:
        logging.warning(f"Konnte Admin-Status nicht prüfen: {e}")
        return False


def get_executable_path() -> str:
    """
    Ermittelt den Pfad zur ausführbaren Datei.
    
    Unterscheidet zwischen:
    - PyInstaller-Executable (sys.frozen)
    - Entwicklungsumgebung (normales Python-Script)
    
    Returns:
        str: Absoluter Pfad zur .exe oder zum Python-Script
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller-Executable
        return sys.executable
    else:
        # Entwicklungsumgebung - Pfad zum Hauptscript
        return str(Path(sys.argv[0]).resolve())


def check_defender_exclusion(exe_path: str = None) -> bool:
    """
    Prüft, ob der angegebene Pfad bereits vom Windows Defender ausgeschlossen ist.
    
    Args:
        exe_path: Pfad zur Executable. Falls None, wird automatisch ermittelt.
        
    Returns:
        bool: True wenn bereits ausgeschlossen, sonst False
    """
    if exe_path is None:
        exe_path = get_executable_path()
    
    try:
        # PowerShell-Befehl zum Abrufen der Ausnahmeliste
        result = subprocess.run(
            [
                "powershell", 
                "-Command", 
                "Get-MpPreference | Select-Object -ExpandProperty ExclusionPath"
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode == 0:
            # Normalisiere Pfade für Vergleich (Groß-/Kleinschreibung, Backslashes)
            exe_path_normalized = Path(exe_path).resolve().as_posix().lower()
            exclusion_paths = result.stdout.strip().split('\n')
            
            for path in exclusion_paths:
                if path.strip():
                    try:
                        normalized = Path(path.strip()).resolve().as_posix().lower()
                        if normalized == exe_path_normalized:
                            logging.info(f"Anwendung ist bereits vom Defender ausgeschlossen: {exe_path}")
                            return True
                    except Exception:
                        # Ungültige Pfade in der Liste ignorieren
                        continue
            
            logging.info(f"Anwendung ist nicht vom Defender ausgeschlossen: {exe_path}")
            return False
        else:
            logging.warning(f"Fehler beim Abrufen der Defender-Ausnahmen: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logging.error("Timeout beim Abrufen der Defender-Ausnahmen")
        return False
    except Exception as e:
        logging.error(f"Fehler beim Prüfen der Defender-Ausnahmen: {e}")
        return False


def add_defender_exclusion(exe_path: str = None) -> tuple[bool, str]:
    """
    Fügt den angegebenen Pfad zur Windows Defender-Ausnahmeliste hinzu.
    
    Diese Funktion triggert automatisch den UAC-Dialog, wenn keine Admin-Rechte
    vorhanden sind. Der Nutzer kann seine Admin-Credentials eingeben, ohne dass
    die gesamte Anwendung neu gestartet werden muss.
    
    Args:
        exe_path: Pfad zur Executable. Falls None, wird automatisch ermittelt.
        
    Returns:
        tuple[bool, str]: (Erfolg, Nachricht)
            - (True, "Erfolg-Nachricht") bei erfolgreichem Hinzufügen
            - (False, "Fehler-Nachricht") bei Fehler
    """
    if exe_path is None:
        exe_path = get_executable_path()
    
    logging.info(f"=== add_defender_exclusion gestartet für: {exe_path} ===")
    
    # Prüfen ob bereits ausgeschlossen (nur wenn Admin-Rechte vorhanden)
    if is_admin():
        if check_defender_exclusion(exe_path):
            msg = f"Die Anwendung ist bereits vom Defender ausgeschlossen."
            logging.info(msg)
            return True, msg
    
    try:
        # PowerShell-Befehl der mit erhöhten Rechten ausgeführt werden soll
        # Escape single quotes in path for PowerShell
        escaped_path = exe_path.replace("'", "''")
        
        # Wenn wir bereits Admin-Rechte haben, direkt ausführen
        if is_admin():
            logging.info("Admin-Rechte vorhanden - direkte Ausführung")
            ps_command = f"Add-MpPreference -ExclusionPath '{escaped_path}'"
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            # Bei direkter Ausführung mit Admin-Rechten können wir verifizieren
            import time
            time.sleep(1)
            if check_defender_exclusion(exe_path):
                msg = f"Die Anwendung wurde erfolgreich vom Windows Defender ausgeschlossen."
                logging.info(f"{msg}\nPfad: {exe_path}")
                return True, msg
            else:
                msg = "Die Ausnahme konnte nicht hinzugefügt werden."
                logging.error(msg)
                return False, msg
                
        else:
            # Ohne Admin-Rechte: Temporäres PowerShell-Script mit Ergebnis-Datei
            logging.info("Keine Admin-Rechte - verwende UAC mit temporärem Script")
            import tempfile
            import os
            
            # Temporäre Ergebnis-Datei
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as result_file:
                result_file_path = result_file.name
            
            logging.info(f"Ergebnis-Datei: {result_file_path}")
            
            # PowerShell-Script mit Error-Handling und Ergebnis-Ausgabe in Datei
            escaped_result_path = result_file_path.replace("'", "''")
            ps_script_content = f"""
try {{
    Add-MpPreference -ExclusionPath '{escaped_path}' -ErrorAction Stop
    'SUCCESS' | Out-File -FilePath '{escaped_result_path}' -Encoding utf8
}} catch {{
    "ERROR: $($_.Exception.Message)" | Out-File -FilePath '{escaped_result_path}' -Encoding utf8
}}
"""
            
            # Temporäres Script erstellen
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as temp_script:
                temp_script.write(ps_script_content)
                temp_script_path = temp_script.name
            
            logging.info(f"Temporäres Script: {temp_script_path}")
            
            try:
                # PowerShell-Script mit erhöhten Rechten ausführen
                logging.info("Starte PowerShell mit RunAs...")
                subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f"Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','{temp_script_path}' -Verb RunAs -Wait"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False
                )
                
                logging.info("PowerShell-Prozess beendet")
                
                # Warte auf Datei-Erstellung
                import time
                time.sleep(2)
                
                # Prüfe ob Ergebnis-Datei existiert
                logging.info(f"Prüfe Ergebnis-Datei: {result_file_path}")
                
                if os.path.exists(result_file_path):
                    logging.info("Ergebnis-Datei gefunden - lese Inhalt...")
                    
                    try:
                        with open(result_file_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig entfernt BOM
                            result_content = f.read().strip()
                        
                        logging.info(f"Ergebnis-Datei Inhalt: '{result_content}'")
                        
                        if "SUCCESS" in result_content:
                            logging.info("PowerShell-Script meldet SUCCESS")
                            msg = f"Die Anwendung wurde erfolgreich vom Windows Defender ausgeschlossen."
                            logging.info(f"{msg}\nPfad: {exe_path}")
                            return True, msg
                        elif result_content.startswith("ERROR:"):
                            msg = f"Fehler beim Hinzufügen der Ausnahme:\n{result_content}"
                            logging.error(msg)
                            return False, msg
                        else:
                            msg = f"Unerwartete Antwort vom PowerShell-Script: {result_content}"
                            logging.warning(msg)
                            return False, msg
                    except Exception as e:
                        msg = f"Fehler beim Lesen der Ergebnis-Datei: {e}"
                        logging.error(msg)
                        return False, msg
                else:
                    msg = "Der UAC-Dialog wurde abgebrochen."
                    logging.warning(msg)
                    return False, msg
                    
            finally:
                # Aufräumen
                try:
                    os.unlink(temp_script_path)
                    logging.info("Temporäres Script gelöscht")
                except Exception as e:
                    logging.warning(f"Konnte temporäres Script nicht löschen: {e}")
                
                try:
                    if os.path.exists(result_file_path):
                        os.unlink(result_file_path)
                        logging.info("Ergebnis-Datei gelöscht")
                except Exception as e:
                    logging.warning(f"Konnte Ergebnis-Datei nicht löschen: {e}")
            
    except subprocess.CalledProcessError as e:
        msg = f"Fehler beim Hinzufügen der Defender-Ausnahme:\n{e.stderr}"
        logging.error(msg)
        return False, msg
    except subprocess.TimeoutExpired:
        msg = "Timeout beim Hinzufügen der Defender-Ausnahme.\nDer Vorgang dauerte zu lange."
        logging.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Unerwarteter Fehler beim Hinzufügen der Defender-Ausnahme:\n{str(e)}"
        logging.error(msg)
        return False, msg


def run_as_admin() -> None:
    """
    Startet die Anwendung mit Administrator-Rechten neu.
    
    ⚠️ HINWEIS: Diese Funktion wird NICHT im Standard-Flow verwendet!
    
    Im normalen Betrieb ist es besser, nur den spezifischen PowerShell-Befehl
    mit erhöhten Rechten auszuführen (siehe add_defender_exclusion), statt
    die gesamte Anwendung neu zu starten.
    
    Diese Funktion ist nur für spezielle Edge-Cases vorgesehen, wo ein
    kompletter Neustart mit Admin-Rechten tatsächlich erforderlich ist.
    
    Diese Funktion löst den Windows UAC-Dialog aus und startet
    die aktuelle Anwendung mit erhöhten Rechten neu.
    Die aktuelle Instanz wird dabei beendet.
    
    Hinweis: Diese Funktion kehrt nicht zurück, wenn erfolgreich!
    """
    try:
        # ShellExecute mit "runas" verb für UAC-Dialog
        result = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "runas",        # verb (Als Administrator ausführen)
            sys.executable, # file (Python.exe oder hcc-plan.exe)
            " ".join(sys.argv),  # parameters
            None,           # directory
            1               # SW_SHOWNORMAL
        )
        
        # Rückgabewerte von ShellExecuteW:
        # > 32 = Erfolg
        # <= 32 = Fehler
        if result > 32:
            logging.info("Anwendung wird mit Admin-Rechten neu gestartet...")
            sys.exit(0)  # Aktuelle Instanz beenden
        else:
            logging.error(f"Fehler beim Neustart mit Admin-Rechten. Error code: {result}")
            
    except Exception as e:
        logging.error(f"Fehler beim Neustart mit Admin-Rechten: {e}")



def check_and_show_defender_dialog(parent_widget=None) -> None:
    """
    Prüft ob der Defender-Exclusion-Dialog angezeigt werden soll und zeigt ihn ggf. an.
    
    Diese Funktion wird beim App-Start aufgerufen und:
    1. Prüft ob bereits gefragt wurde (defender_settings.exclusion_asked)
    2. Zeigt den Dialog nur beim ersten Start (oder wenn "Später" gewählt wurde)
    3. Führt die gewählte Aktion aus
    4. Speichert die Settings
    
    Args:
        parent_widget: Optional - Parent-Widget für den Dialog
    """
    import logging
    
    try:
        from configuration.general_settings import general_settings_handler
        from PySide6.QtWidgets import QMessageBox
        
        # Settings laden
        settings = general_settings_handler.get_general_settings()
        
        # Prüfen ob bereits gefragt
        if settings.defender_settings.exclusion_asked:
            logging.info("Defender-Dialog: Bereits gefragt - überspringe")
            return
        
        # Dialog importieren (lazy import um Circular Imports zu vermeiden)
        from gui.custom_widgets.dlg_defender_exclusion import DlgDefenderExclusion, DefenderExclusionResult
        
        logging.info("Zeige Defender-Exclusion-Dialog...")
        
        # Dialog anzeigen
        dialog = DlgDefenderExclusion(parent_widget)
        dialog.exec()
        
        result = dialog.get_result()
        logging.info(f"Defender-Dialog Ergebnis: {result.value}")
        
        # Ergebnis verarbeiten
        if result == DefenderExclusionResult.ADD_NOW:
            logging.info("Benutzer möchte Defender-Ausnahme hinzufügen")
            
            # Ausnahme hinzufügen
            success, message = add_defender_exclusion()
            
            if success:
                # Erfolgs-Nachricht anzeigen
                QMessageBox.information(
                    parent_widget,
                    "Windows Defender",
                    message
                )
                logging.info(f"Defender-Ausnahme erfolgreich hinzugefügt: {message}")
            else:
                # Fehler-Nachricht anzeigen
                QMessageBox.warning(
                    parent_widget,
                    "Windows Defender",
                    message
                )
                logging.warning(f"Defender-Ausnahme fehlgeschlagen: {message}")
            
            # Settings aktualisieren (wurde gefragt, unabhängig vom Erfolg)
            settings.defender_settings.exclusion_asked = True
            general_settings_handler.save_to_toml_file(settings)
            
        elif result == DefenderExclusionResult.NEVER_ASK:
            logging.info("Benutzer möchte nie wieder gefragt werden")
            
            # Settings aktualisieren - Dialog wurde gezeigt
            settings.defender_settings.exclusion_asked = True
            general_settings_handler.save_to_toml_file(settings)
            
        elif result == DefenderExclusionResult.LATER:
            logging.info("Benutzer möchte später entscheiden")
            # Keine Änderung an Settings - Dialog wird beim nächsten Start erneut angezeigt
            
    except Exception as e:
        logging.error(f"Fehler beim Anzeigen des Defender-Dialogs: {e}")
        # Fehler nicht weiterwerfen - App soll trotzdem starten
        # Fehler nicht weiterwerfen - App soll trotzdem starten
