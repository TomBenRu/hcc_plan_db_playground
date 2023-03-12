from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QHBoxLayout, QPushButton, QGridLayout, QComboBox, QLabel

from database import db_services


class FrmFixedCast(QDialog):
    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent)
        self.setWindowTitle('Fixed Cast')
        self.col_operator_betw_rows = 2
        self.width_cb_actors = 150
        self.width_bt_new_row = 30
        self.width_inner_operator = 50
        self.width_container__add_inner_operator = 60
        self.width_operator_betw_rows = 50

        self.persons = sorted(db_services.get_persons_of_team(team_id), key=lambda p: p.f_name)

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.bt_new_row = QPushButton(QIcon('resources/toolbar_icons/icons/plus.png'), None, clicked=self.new_row)
        self.bt_new_row.setObjectName('bt_new_row')
        self.bt_new_row.setFixedWidth(self.width_bt_new_row)
        self.layout.addWidget(self.bt_new_row, 0, 0)

        self.spacer_widget = QLabel('')
        self.spacer_widget.setObjectName('spacer_widget')
        self.layout.addWidget(self.spacer_widget, self.layout.rowCount(), self.layout.columnCount())

    def new_row(self):
        """füg eine neue Reihe mit Zwischenoperator-Auswahl hinzu"""
        r, c, _, _ = self.layout.getItemPosition(self.layout.indexOf(self.bt_new_row))

        '''neue reihen werden angelegt'''
        if r == 0:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = QComboBox()
            cb_actors.setFixedWidth(self.width_cb_actors)
            cb_actors.addItems(['Actor1', 'Actor2'])
            self.layout.addWidget(cb_actors, r, c + 1)

            container_add_inner_operator = self.create_widget__add_inner_operater()
            container_add_inner_operator.setObjectName('container_add_inner_operator')
            self.layout.addWidget(container_add_inner_operator, r, c+2)

            '''add-row-button wird um 1 nach unten verschoben'''
            self.layout.addWidget(self.bt_new_row, r + 1, c)
        else:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = QComboBox()
            cb_actors.setFixedWidth(self.width_cb_actors)
            cb_actors.addItems(['Actor1', 'Actor2'])
            self.layout.addWidget(cb_actors, r+1, c + 1)

            container_add_inner_operator = self.create_widget__add_inner_operater()
            container_add_inner_operator.setObjectName('container_add_inner_operator')
            self.layout.addWidget(container_add_inner_operator, r+1, c + 2)

            '''add-row-button wird um 2 nach unten verschoben'''
            self.layout.addWidget(self.bt_new_row, r + 2, c)
            '''combo operator betw. rows wird erzeugt'''
            combo_op_betw_rows = QComboBox()
            combo_op_betw_rows.setFixedWidth(self.width_operator_betw_rows)
            combo_op_betw_rows.addItems(['and', 'or'])
            combo_op_betw_rows.setObjectName('operator_betw_rows')
            self.layout.addWidget(combo_op_betw_rows, r, self.col_operator_betw_rows)

        self.layout.addWidget(self.spacer_widget, self.layout.rowCount(), self.layout.columnCount())

    def add_actor(self):
        """fügt eine neue Operator-Auswahl mit nachfolgender Actor-Auswahl hinzu"""
        add_operator_widget = self.sender().parentWidget()

        r, c, _, _ = self.layout.getItemPosition(self.layout.indexOf(add_operator_widget))
        self.layout.addWidget(add_operator_widget, r, c+2)
        cb_operator = QComboBox()
        cb_operator.setFixedWidth(self.width_inner_operator)
        cb_operator.setObjectName('inner_operator')
        cb_operator.addItems(['and', 'or'])
        self.layout.addWidget(cb_operator, r, c)

        cb_actor = QComboBox()
        cb_actor.setFixedWidth(self.width_cb_actors)
        cb_actor.setObjectName('actor')
        cb_actor.addItems(['actor1', 'actor2'])
        self.layout.addWidget(cb_actor, r, c+1)

        self.layout.addWidget(self.spacer_widget, self.layout.rowCount(), self.layout.columnCount())

    def del_actor(self):
        delete_operator_widget = self.sender().parentWidget()
        r, c, _, _ = self.layout.getItemPosition(self.layout.indexOf(delete_operator_widget))

        combo_actors = self.layout.itemAtPosition(r, c-1).widget()
        combo_actors.deleteLater()
        if c > 2:  # Reihe wird nach dem Löschen nicht leer sein
            combo_operator = self.layout.itemAtPosition(r, c-2).widget()
            combo_operator.deleteLater()
            self.layout.addWidget(delete_operator_widget, r, c-2)
        else:
            delete_operator_widget.deleteLater()
            delta = 1  # um diesen Wert werden die Reihen unterhalb noch oben verschoben
            if cb_operator_between_rows := self.layout.itemAtPosition(r+1, self.col_operator_betw_rows):  # mehr als 1 reihe vorhanden
                cb_operator_between_rows.widget().deleteLater()  # delete Operater between rows
                delta = 2
            elif r > 1:
                delta = 2
                cb_operator_between_rows_above = self.layout.itemAtPosition(r-1, self.col_operator_betw_rows)
                cb_operator_between_rows_above.widget().deleteLater()
            for col in range(self.layout.columnCount() + 1):
                for row in range(r+1, self.layout.columnCount() + 1):
                    if cell := self.layout.itemAtPosition(row, col):
                        self.layout.addWidget(cell.widget(), row-delta, col)

        self.layout.addWidget(self.spacer_widget, self.layout.rowCount(), self.layout.columnCount())

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






        """for actor in self.persons:
            bt_actor = QPushButton(QIcon('resources/toolbar_icons/icons/user.png'), f'{actor.f_name} {actor.l_name}',
                                   clicked=lambda actor_id=actor.id: self.put_actor_to_cast(actor_id=actor_id))
            # bt_actor.clicked.connect(lambda e=None, actor_id=actor.id: self.put_actor_to_cast(actor_id))
            self.layout_actors.addWidget(bt_actor)

    def put_actor_to_cast(self, actor_id: UUID):
        print(f'{actor_id=}')"""

