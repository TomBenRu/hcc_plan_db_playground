from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget, QMenu
from PySide6.QtCore import Qt, QPoint

class MyTabWidget(QTabWidget):
    def __init__(self):
        super().__init__()
        for i in range(3):
            tab = QWidget()
            self.addTab(tab, f"Tab {i}")
            self.setTabToolTip(i, f"Dies ist Tab {i}")

        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self.showContextMenu)

    def showContextMenu(self, point: QPoint):
        index = self.tabBar().tabAt(point)
        if index >= 0:
            context_menu = QMenu(self)
            action1 = QAction("Aktion 1", self)
            action2 = QAction("Aktion 2", self)
            context_menu.addAction(action1)
            context_menu.addAction(action2)
            context_menu.exec(self.tabBar().mapToGlobal(point))

app = QApplication([])
tab_widget = MyTabWidget()
tab_widget.show()
app.exec()
