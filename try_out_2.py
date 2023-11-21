from PySide6.QtWidgets import QApplication, QWidget, QTabWidget
import sys

class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        tab_widget = QTabWidget(self)

        # Fügen Sie Tabs zum QTabWidget hinzu
        tab_widget.addTab(QWidget(), "Tab 1")
        tab_widget.addTab(QWidget(), "Tab 2")
        tab_widget.addTab(QWidget(), "Tab 3")

        # Erhalten Sie den Index des Tabs mit der Beschriftung "Tab 2"
        tab_label = "Tab 2"
        tab_index = next(
            (
                index
                for index in range(tab_widget.count())
                if tab_widget.tabText(index) == tab_label
            ),
            -1,
        )
        print("Index des Tabs:", tab_index)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = MyWidget()
    widget.show()
    sys.exit(app.exec())
