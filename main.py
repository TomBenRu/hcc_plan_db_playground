import os

from configuration import project_paths
from gui import app

'''Alle Pfadangaben müssen für die Verarbeitung mit Pyinstaller besonders definiert werden:
   os.path.join(os.path.dirname(__file__), 'resources')'''

r_path = os.path.dirname(__file__)
print(r_path)
project_paths.Paths.root_path = r_path
app.app.exec()
