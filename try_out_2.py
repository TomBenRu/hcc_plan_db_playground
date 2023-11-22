from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QHeaderView
import sys

app = QApplication(sys.argv)

table = QTableWidget(5, 3)
table.setHorizontalHeaderLabels(['Spalte 1', 'Spalte 2', 'Spalte 3'])

# Fügen Sie eine zusätzliche Zeile am Anfang der Tabelle hinzu
table.insertRow(0)

# Erstellen Sie ein QTableWidgetItem, das als Überschrift dient
header = QTableWidgetItem("Überschrift über mehrere Spalten")
table.setItem(0, 0, header)

# Verbinden Sie die Zellen in der ersten Zeile
table.setSpan(0, 0, 1, 3)

# Blenden Sie die tatsächlichen Überschriften der Tabelle aus
table.horizontalHeader().setVisible(False)

table.show()
sys.exit(app.exec())
