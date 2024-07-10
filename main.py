from gui import app

'''Alle Pfadangaben müssen für die Verarbeitung mit Pyinstaller besonders definiert werden:
   os.path.join(os.path.dirname(__file__), 'resources')'''

app.app.exec()
