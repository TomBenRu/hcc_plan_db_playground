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
        widget = self.sender()
        print(f'{widget=}')
        print(f'{self.layout.indexOf(widget)=}')
        print(f'{self.layout.getItemPosition(self.layout.indexOf(widget))=}')
        r, c, _, _ = self.layout.getItemPosition(self.layout.indexOf(widget))

        print(f'{self.layout.itemAtPosition(r, c).widget().objectName()}')
        self.layout.addWidget(self.bt_new, r+1, c)
        if r == 0:
            bt_del_row = QPushButton(QIcon('resources/toolbar_icons/icons/minus.png'), None)
            bt_del_row.setObjectName('del_row')
            bt_del_row.clicked.connect(self.delete_row)
            self.layout.addWidget(bt_del_row, r, c)
        else:
            w = self.layout.itemAtPosition(r-1, c).widget()
            self.layout.addWidget(w, r, c)

        cb_actors = QComboBox()
        self.layout.addWidget(cb_actors, r, c+1)

    def delete_row(self):
        ...




        """for actor in self.persons:
            bt_actor = QPushButton(QIcon('resources/toolbar_icons/icons/user.png'), f'{actor.f_name} {actor.l_name}',
                                   clicked=lambda actor_id=actor.id: self.put_actor_to_cast(actor_id=actor_id))
            # bt_actor.clicked.connect(lambda e=None, actor_id=actor.id: self.put_actor_to_cast(actor_id))
            self.layout_actors.addWidget(bt_actor)

    def put_actor_to_cast(self, actor_id: UUID):
        print(f'{actor_id=}')"""

