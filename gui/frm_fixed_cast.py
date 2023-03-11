from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QGridLayout, QComboBox

from database import db_services
from database.enums import Gender


class FrmFixedCast(QDialog):
    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent)
        self.setWindowTitle('Fixed Cast')

        self.persons = sorted(db_services.get_persons_of_team(team_id), key=lambda p: p.f_name)

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.bt_new = QPushButton(QIcon('resources/toolbar_icons/icons/plus.png'), None)
        self.bt_new.setObjectName('add_row')
        self.bt_new.clicked.connect(self.new_row)
        self.layout.addWidget(self.bt_new, 0, 0)

    def new_row(self):
        """füg eine neue Reihe mit Zwischenoperator-Auswahl hinzu"""
        widget = self.sender()
        print(f'{widget=}')
        r, c, _, _ = self.layout.getItemPosition(self.layout.indexOf(widget))
        print(f'{r=}, {c=}')
        # print(f'{self.layout.itemAtPosition(r, c).widget().objectName()}')

        '''neue reihen werden angelegt'''
        if r == 0:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = QComboBox()
            cb_actors.addItems(['Actor1', 'Actor2'])
            self.layout.addWidget(cb_actors, r, c + 1)
            bt_add_inner_operator = QPushButton(QIcon('resources/toolbar_icons/icons/plus-circle.png'), None,
                                                clicked=self.add_actor)
            bt_add_inner_operator.setObjectName('bt_inner_operator')
            self.layout.addWidget(bt_add_inner_operator, r, c + 2)
            '''add-row-button wird um 1 nach unten verschoben'''
            self.layout.addWidget(self.bt_new, r+1, c)
            '''neuer row-delete-button wird erzeugt'''
            self.bt_del_row = QPushButton(QIcon('resources/toolbar_icons/icons/minus.png'), None)
            self.bt_del_row.setObjectName('del_row')
            self.bt_del_row.clicked.connect(self.delete_row)
            self.layout.addWidget(self.bt_del_row, r, c)
        else:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = QComboBox()
            cb_actors.addItems(['Actor1', 'Actor2'])
            self.layout.addWidget(cb_actors, r+1, c + 1)
            bt_add_inner_operator = QPushButton(QIcon('resources/toolbar_icons/icons/plus-circle.png'), None,
                                                clicked=self.add_actor)
            bt_add_inner_operator.setObjectName('bt_inner_operator')
            self.layout.addWidget(bt_add_inner_operator, r+1, c + 2)
            '''add-row-button wird um 2 nach unten verschoben'''
            self.layout.addWidget(self.bt_new, r+2, c)
            '''combo operator betw. rows wird erzeugt'''
            combo_op_betw_rows = QComboBox()
            combo_op_betw_rows.addItems(['and', 'or'])
            combo_op_betw_rows.setObjectName('operator_betw_rows')
            self.layout.addWidget(combo_op_betw_rows, r, 1)
            '''row-delete-button wird um 2 nach unten verschoben'''
            self.layout.addWidget(self.bt_del_row, r+1, c)


    def delete_row(self):
        ...

    def add_actor(self):
        """fügt eine neue Operator-Auswahl mit nachfolgender Actor-Auswahl hinzu"""
        add_operator_widget = self.sender()
        r, c, _, _ = self.layout.getItemPosition(self.layout.indexOf(add_operator_widget))
        self.layout.addWidget(add_operator_widget, r, c+2)
        cb_operator = QComboBox()
        cb_operator.setObjectName('inner_operator')
        cb_operator.addItems(['and', 'or'])
        self.layout.addWidget(cb_operator, r, c)

        cb_actor = QComboBox()
        cb_actor.addItems(['actor1', 'actor2'])
        self.layout.addWidget(cb_actor, r, c+1)





        """for actor in self.persons:
            bt_actor = QPushButton(QIcon('resources/toolbar_icons/icons/user.png'), f'{actor.f_name} {actor.l_name}',
                                   clicked=lambda actor_id=actor.id: self.put_actor_to_cast(actor_id=actor_id))
            # bt_actor.clicked.connect(lambda e=None, actor_id=actor.id: self.put_actor_to_cast(actor_id))
            self.layout_actors.addWidget(bt_actor)

    def put_actor_to_cast(self, actor_id: UUID):
        print(f'{actor_id=}')"""

