import os
import platform
import subprocess


def open_file_or_folder(path):
    if platform.system() == 'Windows':
        try:
            os.startfile(path)
        except FileNotFoundError as e:
            raise FileNotFoundError(f'{e}') from e
    elif platform.system() == 'Darwin':  # macOS
        subprocess.call(('open', path))
    elif platform.system() == 'Linux':
        # Versuche zuerst xdg-open
        try:
            subprocess.call(('xdg-open', path))
        except FileNotFoundError:
            try:
                # Fallback auf gio open, wenn xdg-open nicht verfügbar ist
                subprocess.call(('gio', 'open', path))
            except FileNotFoundError:
                # Letzter Fallback: gnome-open oder kde-open (für alte Umgebungen)
                if subprocess.call(('gnome-open', path)) != 0:
                    try:
                        subprocess.call(('kde-open', path))
                    except FileNotFoundError as e:
                        raise FileNotFoundError(f'{e}') from e
