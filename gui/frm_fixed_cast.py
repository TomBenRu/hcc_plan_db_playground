from uuid import UUID

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QHBoxLayout, QPushButton, QGridLayout, QComboBox, QLabel, QVBoxLayout, \
    QDialogButtonBox, QMessageBox

from database import db_services, schemas


class FrmFixedCast(QDialog):
    def __init__(self, parent: QWidget, location_of_work: schemas.LocationOfWorkShow):
        super().__init__(parent)
        self.setWindowTitle('Fixed Cast')
        self.col_operator_betw_rows = 2
        self.width_cb_actors = 150
        self.width_bt_new_row = 30
        self.width_inner_operator = 50
        self.width_container__add_inner_operator = 60
        self.width_operator_betw_rows = 50

        self.object_name_actors = 'actors'
        self.object_name_inner_operator = 'inner_operator'
        self.object_name_operatior_between_rows = 'operator_between_rows'

        self.persons = sorted(db_services.get_persons_of_team(location_of_work.team.id), key=lambda p: p.f_name)

        self.result_list = []

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.lb_title = QLabel(f'Hier können Sie definieren, welche Besetzung für die Einrichtung '
                               f'"{location_of_work.name}" grundsätzlich erforderlich ist.\n'
                               f'Zum starten bitte auf das Plus-Symbol klicken')
        self.lb_title.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lb_title.setFixedHeight(40)
        self.layout.addWidget(self.lb_title)

        self.layout_grid = QGridLayout()
        self.layout.addLayout(self.layout_grid)

        self.bt_new_row = QPushButton(QIcon('resources/toolbar_icons/icons/plus.png'), None, clicked=self.new_row)
        self.bt_new_row.setObjectName('bt_new_row')
        self.bt_new_row.setFixedWidth(self.width_bt_new_row)
        self.layout_grid.addWidget(self.bt_new_row, 0, 0)

        self.spacer_widget = QLabel('xxxx')
        self.spacer_widget.setObjectName('spacer_widget')
        self.layout_grid.addWidget(self.spacer_widget, self.layout_grid.rowCount(), self.layout_grid.columnCount())

        self.lb_result = QLabel('Noch keine Besetzung festgelet.')
        self.lb_result.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.layout.addWidget(self.lb_result)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_fixed_cast)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def save_fixed_cast(self):
        self.result_list = []
        for row in range(self.layout_grid.rowCount()):
            for col in range(1, self.layout_grid.columnCount()):
                if not (cell := self.layout_grid.itemAtPosition(row, col)):
                    if (row, col) == (0, 1):
                        QMessageBox.information(self, 'Fixed Cast', 'Sie haben keine Besetung festgelegt.')
                        return
                    continue
                if (row, col) == (0, 1):
                    self.result_list.append([])
                cb: QComboBox = cell.widget()
                if cb.objectName() == self.object_name_operatior_between_rows:
                    self.result_list.append(cb.currentData())
                    self.result_list.append([])
                if cb.objectName() == self.object_name_actors:
                    self.result_list[-1].append(f'UUID("{cb.currentData().id}") in Team')
                if cb.objectName() == self.object_name_inner_operator:
                    self.result_list[-1].append(cb.currentData())
        result_text = f'{self.result_list}'.replace('[', '(').replace(']', ')').replace("'", "").replace(',', '')
        self.lb_result.setText(result_text)

    def new_row(self):
        """füg eine neue Reihe mit Zwischenoperator-Auswahl hinzu"""
        r, c, _, _ = self.layout_grid.getItemPosition(self.layout_grid.indexOf(self.bt_new_row))

        '''neue reihen werden angelegt'''
        if r == 0:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = QComboBox()
            cb_actors.setObjectName(self.object_name_actors)
            cb_actors.setFixedWidth(self.width_cb_actors)
            self.fill_cb_actors(cb_actors)
            self.layout_grid.addWidget(cb_actors, r, c + 1)

            container_add_inner_operator = self.create_widget__add_inner_operater()
            container_add_inner_operator.setObjectName('container_add_inner_operator')
            self.layout_grid.addWidget(container_add_inner_operator, r, c + 2)

            '''add-row-button wird um 1 nach unten verschoben'''
            self.layout_grid.addWidget(self.bt_new_row, r + 1, c)
        else:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = QComboBox()
            cb_actors.setObjectName(self.object_name_actors)
            cb_actors.setFixedWidth(self.width_cb_actors)
            self.fill_cb_actors(cb_actors)
            self.layout_grid.addWidget(cb_actors, r + 1, c + 1)

            container_add_inner_operator = self.create_widget__add_inner_operater()
            container_add_inner_operator.setObjectName('container_add_inner_operator')
            self.layout_grid.addWidget(container_add_inner_operator, r + 1, c + 2)

            '''add-row-button wird um 2 nach unten verschoben'''
            self.layout_grid.addWidget(self.bt_new_row, r + 2, c)
            '''combo operator betw. rows wird erzeugt'''
            combo_op_betw_rows = QComboBox()
            combo_op_betw_rows.setObjectName(self.object_name_operatior_between_rows)
            combo_op_betw_rows.setFixedWidth(self.width_operator_betw_rows)
            self.fill_cb_operator(combo_op_betw_rows)
            combo_op_betw_rows.addItems(['and', 'or'])
            self.layout_grid.addWidget(combo_op_betw_rows, r, self.col_operator_betw_rows)

        self.layout_grid.addWidget(self.spacer_widget, self.layout_grid.rowCount(), self.layout_grid.columnCount())

    def add_actor(self):
        """fügt eine neue Operator-Auswahl mit nachfolgender Actor-Auswahl hinzu"""
        add_operator_widget = self.sender().parentWidget()

        r, c, _, _ = self.layout_grid.getItemPosition(self.layout_grid.indexOf(add_operator_widget))
        self.layout_grid.addWidget(add_operator_widget, r, c + 2)
        cb_operator = QComboBox()
        cb_operator.setObjectName(self.object_name_inner_operator)
        cb_operator.setFixedWidth(self.width_inner_operator)
        self.fill_cb_operator(cb_operator)
        self.layout_grid.addWidget(cb_operator, r, c)

        cb_actors = QComboBox()
        cb_actors.setObjectName(self.object_name_actors)
        cb_actors.setFixedWidth(self.width_cb_actors)
        self.fill_cb_actors(cb_actors)
        self.layout_grid.addWidget(cb_actors, r, c + 1)

        self.layout_grid.addWidget(self.spacer_widget, self.layout_grid.rowCount(), self.layout_grid.columnCount())

    def del_actor(self):
        delete_operator_widget = self.sender().parentWidget()
        r, c, _, _ = self.layout_grid.getItemPosition(self.layout_grid.indexOf(delete_operator_widget))

        combo_actors = self.layout_grid.itemAtPosition(r, c - 1).widget()
        combo_actors.deleteLater()
        if c > 2:  # Reihe wird nach dem Löschen nicht leer sein
            combo_operator = self.layout_grid.itemAtPosition(r, c - 2).widget()
            combo_operator.deleteLater()
            self.layout_grid.addWidget(delete_operator_widget, r, c - 2)
        else:
            delete_operator_widget.deleteLater()
            delta = 1  # um diesen Wert werden die Reihen unterhalb noch oben verschoben
            if cb_operator_between_rows := self.layout_grid.itemAtPosition(r + 1, self.col_operator_betw_rows):  # mehr als 1 reihe vorhanden
                cb_operator_between_rows.widget().deleteLater()  # delete Operater between rows
                delta = 2
            elif r > 1:
                delta = 2
                cb_operator_between_rows_above = self.layout_grid.itemAtPosition(r - 1, self.col_operator_betw_rows)
                cb_operator_between_rows_above.widget().deleteLater()
            for col in range(self.layout_grid.columnCount() + 1):
                for row in range(r+1, self.layout_grid.columnCount() + 1):
                    if cell := self.layout_grid.itemAtPosition(row, col):
                        self.layout_grid.addWidget(cell.widget(), row - delta, col)

        self.layout_grid.addWidget(self.spacer_widget, self.layout_grid.rowCount(), self.layout_grid.columnCount())

    def create_widget__add_inner_operater(self):
        container = QWidget()
        container.setFixedWidth(self.width_container__add_inner_operator)
        layout_container = QHBoxLayout()
        layout_container.setSpacing(0)
        container.setLayout(layout_container)

        bt_del_inner_operator = QPushButton(QIcon('resources/toolbar_icons/icons/minus-circle.png'), None,
                                            clicked=self.del_actor)
        bt_add_inner_operator = QPushButton(QIcon('resources/toolbar_icons/icons/plus-circle.png'), None,
                                            clicked=self.add_actor)
        layout_container.addWidget(bt_del_inner_operator)
        layout_container.addWidget(bt_add_inner_operator)

        return container

    def fill_cb_actors(self, cb_actors: QComboBox):
        for person in self.persons:
            cb_actors.addItem(QIcon('resources/toolbar_icons/icons/user.png'), f'{person.f_name} {person.l_name}',
                              person)

    def fill_cb_operator(self, combo_operator: QComboBox):
        for text, data in [('und', 'and'), ('oder', 'or')]:
            combo_operator.addItem(text, data)
