import datetime
from typing import Literal
from uuid import UUID

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QDialog, QWidget, QHBoxLayout, QPushButton, QGridLayout, QComboBox, QLabel, QVBoxLayout, \
    QDialogButtonBox, QMessageBox, QDateEdit

from database import db_services, schemas
from database.special_schema_requests import get_curr_team_of_location, get_curr_persons_of_team, \
    get_persons_of_team_at_date, get_curr_team_of_location_at_date
from .tools.qcombobox_find_data import QComboBoxToFindData


class FrmFixedCast(QDialog):
    def __init__(self, parent: QWidget, schema_with_fixed_cast_field: schemas.ModelWithFixedCast,
                 location_of_work: schemas.LocationOfWorkShow):
        super().__init__(parent)
        self.setWindowTitle('Fixed Cast')
        self.col_operator_betw_rows = 2
        self.width_cb_actors = 150
        self.width_bt_new_row = 30
        self.width_inner_operator = 50
        self.width_container__add_inner_operator = 60
        self.width_operator_betw_rows = 50

        self.object_with_fixed_cast = schema_with_fixed_cast_field
        self.locatin_of_work = location_of_work

        self.object_name_actors = 'actors'
        self.object_name_inner_operator = 'inner_operator'
        self.object_name_operatior_between_rows = 'operator_between_rows'
        self.data_text_operator = {'and': 'und', 'or': 'oder'}

        self.persons: list[schemas.Person] = []

        self.layout = QVBoxLayout(self)

        if isinstance(schema_with_fixed_cast_field, (schemas.LocationOfWork, schemas.Event)):
            additional_text = f'die Einrichtung "{schema_with_fixed_cast_field.name}"'
        elif isinstance(schema_with_fixed_cast_field, schemas.LocationPlanPeriod):
            additional_text = f'die Planungsperiode "{schema_with_fixed_cast_field.start}-{schema_with_fixed_cast_field.end}"'
        else:
            raise TypeError(f'{type(schema_with_fixed_cast_field)} ist kein erlaubtes Schema.')

        self.lb_title = QLabel(f'Hier können Sie definieren, welche Besetzung für {additional_text} '
                               f'grundsätzlich erforderlich ist.\n'
                               f'Zum starten bitte auf das Plus-Symbol klicken\n'
                               f'Die Besetzung gilt allgemein datumsunabhängig, egal welches Datum ausgewählt ist.\n'
                               f'Die Auswahl des Datums ist dafür da, dass in sich in naher Zukunft ändernde '
                               f'Personalien berücksichtigt werden können.')
        self.lb_title.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lb_title.setFixedHeight(40)
        self.layout.addWidget(self.lb_title)

        self.layout_date = QHBoxLayout()
        self.layout_date.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.addLayout(self.layout_date)
        self.layout_grid = QGridLayout()
        self.layout.addLayout(self.layout_grid)

        self.bt_new_row = QPushButton(QIcon('resources/toolbar_icons/icons/plus.png'), None, clicked=self.new_row)
        self.bt_new_row.setObjectName('bt_new_row')
        self.bt_new_row.setFixedWidth(self.width_bt_new_row)
        self.layout_grid.addWidget(self.bt_new_row, 0, 0)

        self.spacer_widget = QLabel()
        self.spacer_widget.setObjectName('spacer_widget')
        self.layout_grid.addWidget(self.spacer_widget, self.layout_grid.rowCount(), self.layout_grid.columnCount())

        self.lb_date = QLabel('Datum:')
        self.de_date = QDateEdit()
        self.de_date.setFixedWidth(120)
        self.de_date.dateChanged.connect(self.date_changed)
        self.de_date.setDate(datetime.date.today())
        self.de_date.setMinimumDate(datetime.date.today())
        self.layout_date.addWidget(self.lb_date)
        self.layout_date.addWidget(self.de_date)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_fixed_cast)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        # self.plot_eval_str()

    def date_changed(self):
        date = self.de_date.date().toPython()
        team = get_curr_team_of_location_at_date(self.locatin_of_work, date)
        self.persons = sorted(get_persons_of_team_at_date(team.id, date), key=lambda x: x.f_name)
        self.reset_fixed_cast_plot()

    def save_fixed_cast(self):
        result_list = self.grid_to_list()
        if not result_list:
            self.object_with_fixed_cast.fixed_cast = None
            self.accept()
            return

        result_text = f'{result_list}'.replace('[', '(').replace(']', ')').replace("'", "").replace(',', '')
        self.object_with_fixed_cast.fixed_cast = result_text
        self.accept()

    def grid_to_list(self):
        result_list = []
        for row in range(self.layout_grid.rowCount()):
            for col in range(1, self.layout_grid.columnCount()):
                if not (cell := self.layout_grid.itemAtPosition(row, col)):
                    if (row, col) == (0, 1):
                        return result_list
                    continue
                if (row, col) == (0, 1):
                    result_list.append([])
                cb: QComboBox = cell.widget()
                if cb.objectName() == self.object_name_operatior_between_rows:
                    result_list.extend((cb.currentData(), []))
                if cb.objectName() == self.object_name_actors:
                    result_list[-1].append(f'(UUID("{cb.currentData()}") in team)')
                if cb.objectName() == self.object_name_inner_operator:
                    result_list[-1].append(cb.currentData())
        return result_list

    def new_row(self):
        """füg eine neue Reihe mit Zwischenoperator-Auswahl hinzu"""
        r, c, _, _ = self.layout_grid.getItemPosition(self.layout_grid.indexOf(self.bt_new_row))

        '''neue reihen werden angelegt'''
        if r == 0:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = self.create_combo_actors()
            self.layout_grid.addWidget(cb_actors, r, c + 1)

            container_add_inner_operator = self.create_widget__add_inner_operater()
            self.layout_grid.addWidget(container_add_inner_operator, r, c + 2)

            '''add-row-button wird um 1 nach unten verschoben'''
            self.layout_grid.addWidget(self.bt_new_row, r + 1, c)
        else:
            '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
            cb_actors = self.create_combo_actors()
            self.layout_grid.addWidget(cb_actors, r + 1, c + 1)

            container_add_inner_operator = self.create_widget__add_inner_operater()
            self.layout_grid.addWidget(container_add_inner_operator, r + 1, c + 2)

            '''add-row-button wird um 2 nach unten verschoben'''
            self.layout_grid.addWidget(self.bt_new_row, r + 2, c)
            '''combo operator betw. rows wird erzeugt'''
            combo_op_betw_rows = self.create_combo_operator('between')
            self.layout_grid.addWidget(combo_op_betw_rows, r, self.col_operator_betw_rows)

        self.layout_grid.addWidget(self.spacer_widget, self.layout_grid.rowCount(), self.layout_grid.columnCount())

    def add_actor(self):
        """fügt eine neue Operator-Auswahl mit nachfolgender Actor-Auswahl hinzu"""
        add_operator_widget = self.sender().parentWidget()

        r, c, _, _ = self.layout_grid.getItemPosition(self.layout_grid.indexOf(add_operator_widget))
        self.layout_grid.addWidget(add_operator_widget, r, c + 2)
        cb_operator = self.create_combo_operator('inner')
        self.layout_grid.addWidget(cb_operator, r, c)

        cb_actors = self.create_combo_actors()
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

    def create_combo_actors(self):
        cb_actors = QComboBoxToFindData()
        cb_actors.setObjectName(self.object_name_actors)
        cb_actors.setFixedWidth(self.width_cb_actors)
        self.fill_cb_actors(cb_actors)
        return cb_actors

    def create_combo_operator(self, typ: Literal['inner', 'between']):
        cb_operator = QComboBox()
        cb_operator.setObjectName(self.object_name_inner_operator if typ == 'inner'
                                  else self.object_name_operatior_between_rows)
        cb_operator.setFixedWidth(self.width_inner_operator)
        if typ == 'inner':
            cb_operator.setStyleSheet('background: #d9e193')
        else:
            cb_operator.setStyleSheet('background: #8ddee1')

        self.fill_cb_operator(cb_operator)

        return cb_operator

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
        container.setObjectName('add_inner_operator')
        container.setFixedWidth(self.width_container__add_inner_operator)

        return container

    def fill_cb_actors(self, cb_actors: QComboBox):
        for person in self.persons:
            cb_actors.addItem(QIcon('resources/toolbar_icons/icons/user.png'), f'{person.f_name} {person.l_name}',
                              person.id)

    def fill_cb_operator(self, combo_operator: QComboBox):
        for data, text in self.data_text_operator.items():
            combo_operator.addItem(text, data)

    def reset_fixed_cast_plot(self):
        for i in range(self.layout_grid.count()):
            self.layout_grid.itemAt(i).widget().deleteLater()
        self.plot_eval_str()

    def plot_eval_str(self):
        if not self.object_with_fixed_cast.fixed_cast:
            return
        form = self.backtranslate_eval_str()
        form_cleaned = self.proof_form_to_not_assigned_persons(form)

        for row_idx, row in enumerate(form_cleaned):
            if type(row) == str:
                cb_operator = self.create_combo_operator('between')
                cb_operator.setCurrentIndex(cb_operator.findData(row))
                self.layout_grid.addWidget(cb_operator, row_idx, self.col_operator_betw_rows)
            else:
                self.layout_grid.addWidget(self.create_widget__add_inner_operater(), row_idx, len(row)+1)
                for col_idx, element in enumerate(row):
                    if type(element) == str:
                        cb_operator = self.create_combo_operator('inner')
                        cb_operator.setCurrentIndex(cb_operator.findData(element))
                        self.layout_grid.addWidget(cb_operator, row_idx, col_idx+1)
                    else:
                        cb_actors = self.create_combo_actors()
                        cb_actors.setCurrentIndex(cb_actors.findData(element))
                        self.layout_grid.addWidget(cb_actors, row_idx, col_idx+1)

        self.layout_grid.addWidget(self.bt_new_row, len(form), 0)
        self.layout_grid.addWidget(self.spacer_widget, self.layout_grid.rowCount(), self.layout_grid.columnCount())

    def backtranslate_eval_str(self, str_for_team: str = 'team'):
        form = []
        eval_str = self.object_with_fixed_cast.fixed_cast
        if not eval_str:
            return
        e_s = eval_str.replace('and', ',"and",').replace('or', ',"or",').replace(f'in {str_for_team}', '')
        e_s = eval(e_s)
        if type(e_s) != tuple:
            e_s = (e_s,)
        for element in e_s:
            if type(element) == tuple:
                break
        else:
            e_s = [e_s]
        for val in e_s:
            if type(val) in [int, UUID]:
                form.append([val])
            elif type(val) == str:
                form.append(val)
            else:
                form.append(list(val))
        return form

    def proof_form_to_not_assigned_persons(self, form: list[list | str]):
        person_ids = [p.id for p in self.persons]
        for i, expression in enumerate(form):
            if isinstance(expression, str):
                continue
            for j, value in enumerate(expression):
                if isinstance(value, UUID) and value not in person_ids:
                    expression[j] = None
                    if j > 0:
                        expression[j - 1] = None
            form[i] = [v for v in expression if v is not None]
            if form[i] and isinstance(form[i][0], str):
                form[i].pop(0)
        for i, expression in enumerate(form):
            if isinstance(expression, list) and not expression:
                form[i] = None
                if i > 0:
                    form[i - 1] = None
        form = [e for e in form if e is not None]
        if isinstance(form[0], str):
            form.pop(0)
        return form


