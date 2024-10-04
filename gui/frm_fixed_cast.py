import datetime
import itertools
import os
import re
from abc import ABC, abstractmethod
from functools import partial
from typing import Literal, Callable, TypeAlias
from uuid import UUID

import sympy
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import (QDialog, QWidget, QHBoxLayout, QPushButton, QGridLayout, QComboBox, QLabel, QVBoxLayout,
                               QDialogButtonBox, QDateEdit, QMenu, QMessageBox)
from sympy.logic.boolalg import BooleanFunction, simplify_logic

from database import db_services, schemas
from database.special_schema_requests import get_persons_of_team_at_date, get_curr_team_of_location_at_date
from tools.actions import MenuToolbarAction
from commands import command_base_classes
from commands.database_commands import cast_group_commands, location_plan_period_commands, location_of_work_commands
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import backtranslate_eval_str

object_with_fixed_cast_type: TypeAlias = (schemas.LocationOfWorkShow |
                                          schemas.LocationPlanPeriodShow |
                                          schemas.CastGroupShow)


class DlgFixedCastBuilderABC(ABC):
    def __init__(self, parent: QWidget, object_with_fixed_cast: schemas.ModelWithFixedCast,
                 location_plan_period: schemas.LocationPlanPeriodShow | None = None):

        self.object_with_fixed_cast: (object_with_fixed_cast_type | None) = object_with_fixed_cast.model_copy()
        self.location_plan_period: schemas.LocationPlanPeriodShow | None = location_plan_period
        self.parent_widget = parent
        self.parent_fixed_cast: str | None = None
        self.location_of_work: schemas.LocationOfWorkShow | None = None
        self.title_text: str | None = None
        self.info_text: str | None = None
        self.make_reset_menu: bool = False
        self.fixed_date: datetime.date | None = None
        self.warning_text: str = ''
        self.object_with_fixed_cast__refresh_func: Callable[[], schemas.ModelWithFixedCast] | None = None
        self.update_command: Callable[[str | None], command_base_classes.Command] | None = None
        self._generate_field_values()

    @abstractmethod
    def _generate_field_values(self):
        """self.title_text = ...

        self.location_of_work = ...

        self.info_text = ...

        self.make_reset_menu: bool = (delete if False)

        self.fixed_date = (delete if None)

        self.parent_fixed_cast = (delete if None)

        self.update_command = ... partial function, which generates the fixed_cast update command with parameter = fixed_cast_str

        self.object_with_fixed_cast__refresh_func = ..."""

    @abstractmethod
    def method_date_changed(self, date: datetime.date) -> list[schemas.Person]:
        ...

    def build(self) -> 'DlgFixedCast':
        return DlgFixedCast(self.parent_widget, self)


class DlgFixedCastBuilderLocationOfWork(DlgFixedCastBuilderABC):
    def __init__(self, parent, location_of_work: schemas.LocationOfWorkShow):
        super().__init__(parent=parent, object_with_fixed_cast=location_of_work)

    def _generate_field_values(self):
        self.title_text = 'Feste Besetzung einer Einrichtung'
        self.location_of_work = self.object_with_fixed_cast.model_copy()
        self.info_text = f'die Einrichtung "{self.object_with_fixed_cast.name}"'
        self.update_command = partial(location_of_work_commands.UpdateFixedCast, self.object_with_fixed_cast.id)
        self.object_with_fixed_cast__refresh_func = partial(db_services.LocationOfWork.get,
                                                            self.object_with_fixed_cast.id)

    def method_date_changed(self, date: datetime.date) -> list[schemas.Person]:
        team = get_curr_team_of_location_at_date(self.object_with_fixed_cast, date)
        return sorted(get_persons_of_team_at_date(team.id, date), key=lambda x: x.f_name)


class DlgFixedCastBuilderLocationPlanPeriod(DlgFixedCastBuilderABC):
    def __init__(self, parent, location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent, object_with_fixed_cast=location_plan_period)

    def _generate_field_values(self):
        self.title_text = 'Feste Besetzung einer Planungsperiode'
        self.location_of_work = db_services.LocationOfWork.get(
            self.object_with_fixed_cast.location_of_work.id
        )
        self.parent_fixed_cast = self.location_of_work.fixed_cast
        self.info_text = (f'die Planungsperiode "{self.object_with_fixed_cast.plan_period.start}-'
                          f'{self.object_with_fixed_cast.plan_period.end}"')
        self.make_reset_menu = True
        self.fixed_date = self.object_with_fixed_cast.plan_period.start
        self.update_command = partial(location_plan_period_commands.UpdateFixedCast,
                                      self.object_with_fixed_cast.id)
        self.object_with_fixed_cast__refresh_func = partial(db_services.LocationPlanPeriod.get,
                                                            self.object_with_fixed_cast.id)

    def method_date_changed(self, date: datetime.date = None) -> list[schemas.Person]:
        return self.union_persons(self.object_with_fixed_cast.plan_period)

    def union_persons(self, plan_period: schemas.PlanPeriod):
        days_of_plan_period = [
            plan_period.start + datetime.timedelta(delta)
            for delta in range((plan_period.end - plan_period.start).days + 1)
        ]
        person_ids = set()
        same_person_over_period = True
        for day in days_of_plan_period:
            person_ids_at_day = {p.id for p in get_persons_of_team_at_date(plan_period.team.id, day)}
            if day != days_of_plan_period[0] and person_ids_at_day != person_ids:
                same_person_over_period = False
            person_ids |= person_ids_at_day
        if not same_person_over_period:
            self.warning_text = 'Achtung: Mögliche Besetzungen sind nicht an allen Tagen gleich!'
        return sorted((db_services.Person.get(p_id) for p_id in person_ids), key=lambda x: x.f_name)


class DlgFixedCastBuilderCastGroup(DlgFixedCastBuilderABC):
    def __init__(self, parent, cast_group: schemas.CastGroupShow,
                 location_plan_period: schemas.LocationPlanPeriodShow = None):
        super().__init__(parent=parent, object_with_fixed_cast=cast_group, location_plan_period=location_plan_period)
        self.object_with_fixed_cast: schemas.CastGroupShow = cast_group.model_copy()

    def _generate_field_values(self):
        self.title_text = ('Feste Besetzung eines Events' if self.object_with_fixed_cast.event
                           else 'Feste Besetzung einer Besetzungsgruppe')
        self.parent_fixed_cast = self.location_plan_period.fixed_cast
        self.info_text = (f'''das Event am "{self.object_with_fixed_cast.event.date.strftime('%d.%m.%y')}"'''
                          if self.object_with_fixed_cast.event else 'die Besetzungsgruppe')
        self.make_reset_menu = bool(self.location_plan_period)
        self.fixed_date = (self.object_with_fixed_cast.event.date if self.object_with_fixed_cast.event
                           else self.object_with_fixed_cast.plan_period.start)
        # fixme: für cast_groups ohne event sollte die leave_cast_group mit event mit dem kleinsten date
        #  verwendet werden.
        self.update_command = partial(cast_group_commands.UpdateFixedCast, self.object_with_fixed_cast.id)
        self.object_with_fixed_cast__refresh_func = partial(db_services.CastGroup.get, self.object_with_fixed_cast.id)

    def method_date_changed(self, date: datetime.date = None) -> list[schemas.Person]:
        if self.object_with_fixed_cast.event:
            location_of_work = db_services.LocationOfWork.get(
                self.object_with_fixed_cast.event.location_plan_period.location_of_work.id)
            team = get_curr_team_of_location_at_date(location_of_work, self.object_with_fixed_cast.event.date)
            return get_persons_of_team_at_date(team.id, date)
        return self.union_persons()

    def union_persons(self):
        events: list[schemas.Event] = []

        def find_recursive(cast_group: schemas.CastGroup):
            cast_group = db_services.CastGroup.get(cast_group.id)
            for child_group in cast_group.child_groups:
                if child_group.event:
                    events.append(child_group.event)
                else:
                    find_recursive(child_group)

        find_recursive(self.object_with_fixed_cast)
        person_ids = set()
        same_person_over_period = True
        for event in events:
            location_of_work = db_services.LocationOfWork.get(event.location_plan_period.location_of_work.id)
            team = get_curr_team_of_location_at_date(location_of_work, event.date)
            person_ids_at_day = {p.id for p in get_persons_of_team_at_date(team.id, event.date)}
            if event != events[0] and person_ids_at_day != person_ids:
                same_person_over_period = False
            person_ids |= person_ids_at_day
        if not same_person_over_period:
            self.warning_text = 'Achtung: Mögliche Besetzungen sind nicht an allen Tagen gleich!'
        return sorted((db_services.Person.get(p_id) for p_id in person_ids), key=lambda x: x.f_name)


class SimplifyFixedCastAndInfo:
    def __init__(self, fixed_cast: str):
        self.fixed_cast = fixed_cast
        self.simplified_fixed_cast: str = ''
        self.min_nr_actors: int = 0
        self.symbols = {}
        self.simplify()
        self.find_min_nr_actors()

    def fixed_cast_to_logical_sentence(self) -> str:
        def replacement(match):
            self.symbols[match.group(1).replace('"', '')] = sympy.symbols(match.group(1).replace('"', ''))
            return f'symbols[{match.group(1)}]'

        new_string = re.sub(r'UUID\((.+?)\)', replacement, self.fixed_cast)
        new_string = new_string.replace('in team', '')
        new_string = new_string.replace('not ', '~ ').replace('and ', '& ').replace('or ', '| ')

        return new_string

    def simplify_to_boolean_function(self, sentence: str) -> BooleanFunction:
        # form='cnf' oder form=None produziert bei der Constraint-Erstellung falsche Ergebnisse.
        return simplify_logic(eval(sentence, {'symbols': self.symbols}), form='dnf', force=True)

    def back_translate_to_fixed_cast(self, expr: BooleanFunction) -> str:
        expr_str = str(expr).replace('(', '( ').replace(')', ' )')
        exclude = {'~': ' not ', '&': ' and ', '|': ' or ', '(': '(', ')': ')'}
        expr_str_list = expr_str.split(' ')

        # alleinstehende ID-Strings werden mit Klammern versehen
        expr_str_list_corr = []
        for i, val in enumerate(expr_str_list):
            if val in self.symbols and (i == 0 or (expr_str_list[i - 1] != '(' and expr_str_list[i + 1 != ')'])):
                expr_str_list_corr.extend(['(', val, ')'])
            else:
                expr_str_list_corr.append(val)

        expr_str_list_res = [f'(UUID("{x}") in team)' if x not in exclude else exclude[x] for x in expr_str_list_corr]
        return '(' + ''.join(expr_str_list_res) + ')'

    def simplify(self):
        logical_sentence = self.fixed_cast_to_logical_sentence()
        simplified_boolean_function = self.simplify_to_boolean_function(logical_sentence)
        self.simplified_fixed_cast = self.back_translate_to_fixed_cast(simplified_boolean_function)

    def find_min_nr_actors(self):
        all_person_ids = {UUID(x) for x in self.symbols}
        for n in range(1, len(all_person_ids) + 1):
            for comb in itertools.combinations(all_person_ids, n):
                if eval(self.simplified_fixed_cast, {'team': comb, 'UUID': UUID}):
                    self.min_nr_actors = n
                    return


class DlgFixedCast(QDialog):
    # todo: Handling für den Fall, dass Personen nicht über gesamten Zeitraum einer Planperiode gleich sind.
    # todo: Lösung Union von Personen erstellen, beim aktivieren eines Events fixed_cast
    # todo: automatisch korrigieren und Warnung anzeigen.
    def __init__(self, parent: QWidget, builder: DlgFixedCastBuilderABC):
        super().__init__(parent)

        self.builder = builder

        self.setWindowTitle(self.builder.title_text)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.fixed_cast_simplified: str | None = None

        self.col_operator_between_rows = 2
        self.width_cb_actors = 150
        self.width_bt_new_row = 30
        self.width_inner_operator = 50
        self.width_container__add_inner_operator = 60
        self.width_operator_between_rows = 50

        self.object_with_fixed_cast = self.builder.object_with_fixed_cast

        self.object_name_actors = 'actors'
        self.object_name_inner_operator = 'inner_operator'
        self.object_name_operator_between_rows = 'operator_between_rows'
        self.data_text_operator = {'and': 'und', 'or': 'oder'}

        self.persons: list[schemas.Person] = []

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        additional_text = self.builder.info_text

        self.lb_title = QLabel(f'Hier können Sie definieren, welche Besetzung für {additional_text} '
                               f'grundsätzlich erforderlich ist.\n'
                               f'Zum starten bitte auf das Plus-Symbol klicken\n'
                               f'Die Besetzung gilt allgemein datumsunabhängig, egal welches Datum ausgewählt ist.\n'
                               f'Die Auswahl des Datums ist dafür da, dass in sich in naher Zukunft ändernde '
                               f'Personalien berücksichtigt werden können.')
        self.lb_warning = QLabel()
        self.lb_warning.setForegroundRole(QPalette.Highlight)
        self.layout.addWidget(self.lb_title)
        self.layout.addWidget(self.lb_warning)

        self.layout_date = QHBoxLayout()
        self.layout_date.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.addLayout(self.layout_date)
        self.layout_grid = QGridLayout()
        self.layout_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(self.layout_grid)

        self.layout.addStretch()

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.bt_new_row = QPushButton(QIcon(os.path.join(self.path_to_icons, 'plus.png')),
                                      None, clicked=self.new_row)
        self.bt_new_row.setObjectName('bt_new_row')
        self.bt_new_row.setFixedWidth(self.width_bt_new_row)
        self.layout_grid.addWidget(self.bt_new_row, 0, 0)

        self.lb_date = QLabel('Datum:')
        self.de_date = QDateEdit()
        self.de_date.setFixedWidth(120)
        self.de_date.dateChanged.connect(self.date_changed)
        self.de_date__set_initial_value()
        self.layout_date.addWidget(self.lb_date)
        self.layout_date.addWidget(self.de_date)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.bt_reset = QPushButton('Reset')
        self.reset_menu: QMenu | None = None
        self.bt_reset_make_menu()
        self.bt_undo = QPushButton(QIcon(os.path.join(self.path_to_icons, 'arrow-return-180.png')), 'Undo')
        self.bt_undo.clicked.connect(self.undo)
        self.bt_redo = QPushButton(QIcon(os.path.join(self.path_to_icons, 'arrow-return.png')), 'Redo')
        self.bt_redo.clicked.connect(self.redo)
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.bt_undo, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.bt_redo, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def de_date__set_initial_value(self):
        if self.builder.fixed_date:
            self.de_date.setDate(self.builder.fixed_date)
            self.de_date.setDisabled(True)
        else:
            self.de_date.setDate(datetime.date.today())
            self.de_date.setMinimumDate(datetime.date.today())

    def date_changed(self):
        self.persons = self.builder.method_date_changed(self.de_date.date().toPython())
        self.lb_warning.setText(self.builder.warning_text)
        self.reset_fixed_cast_plot()

    def accept(self) -> None:
        self.object_with_fixed_cast = self.builder.object_with_fixed_cast__refresh_func()
        if self.object_with_fixed_cast.fixed_cast:
            simplifier = SimplifyFixedCastAndInfo(self.object_with_fixed_cast.fixed_cast)
            self.fixed_cast_simplified = simplifier.simplified_fixed_cast
            self.controller.execute(self.builder.update_command(self.fixed_cast_simplified))

            if self.object_with_fixed_cast.nr_actors < simplifier.min_nr_actors:
                # fixme: für cast_groups ohne event
                QMessageBox.warning(self, 'Fixed Cast',
                                    f'Die benötigte Anzahl der Mitarbeiter ({simplifier.min_nr_actors}) übersteigt die '
                                    f'vorgesehene Besetzungsstärke ({self.object_with_fixed_cast.nr_actors}).')
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def undo(self):
        if self.controller.get_undo_stack():
            self.controller.undo()
            self.reset_fixed_cast_plot()

    def redo(self):
        if self.controller.redo_stack:
            self.controller.redo()
            self.reset_fixed_cast_plot()

    def save_plot(self):
        if result_list := self.grid_to_list():
            fixed_cast = f'{result_list}'.replace('[', '(').replace(']', ')').replace("'", "").replace(',', '')
        else:
            fixed_cast = None
        self.controller.execute(self.builder.update_command(fixed_cast))

    def remove_fixed_cast(self):
        self.controller.execute(self.builder.update_command(None))
        self.reset_fixed_cast_plot()

    def reset_to_parent_value(self):
        self.controller.execute(
            self.builder.update_command(self.builder.parent_fixed_cast))
        self.reset_fixed_cast_plot()

    def bt_reset_make_menu(self):
        if self.builder.make_reset_menu:
            self.reset_menu = QMenu()
            self.reset_menu.addAction(
                MenuToolbarAction(self, os.path.join(self.path_to_icons, 'cross.png'), 'Clear', None,
                                  self.remove_fixed_cast))
            self.reset_menu.addAction(
                MenuToolbarAction(self, os.path.join(self.path_to_icons, 'arrow-circle-315-left.png'),
                                  'Reset von übergeordnetem Modell', None, self.reset_to_parent_value))
            self.bt_reset.setMenu(self.reset_menu)
        else:
            self.bt_reset.setText('Clear')
            self.bt_reset.clicked.connect(self.remove_fixed_cast)

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
                if cb.objectName() == self.object_name_operator_between_rows:
                    result_list.extend((cb.currentData(), []))
                if cb.objectName() == self.object_name_actors:
                    result_list[-1].append(f'(UUID("{cb.currentData()}") in team)')
                if cb.objectName() == self.object_name_inner_operator:
                    result_list[-1].append(cb.currentData())
        return result_list

    def new_row(self):
        """füg eine neue Reihe mit Zwischenoperator-Auswahl und combo-actor hinzu"""
        r, c, _, _ = self.layout_grid.getItemPosition(self.layout_grid.indexOf(self.bt_new_row))

        '''neue reihen werden angelegt'''
        if r != 0:
            '''combo operator betw. rows wird erzeugt'''
            combo_op_between_rows = self.create_combo_operator('between')
            combo_op_between_rows.currentIndexChanged.connect(self.save_plot)
            self.layout_grid.addWidget(combo_op_between_rows, r, self.col_operator_between_rows)
            r += 1

        '''aktuelle Zeile wird mit combo-actor und bt_add_inner_operator befüllt'''
        cb_actors = self.create_combo_actors()
        cb_actors.currentIndexChanged.connect(self.save_plot)
        self.layout_grid.addWidget(cb_actors, r, c + 1)

        container_add_inner_operator = self.create_widget__add_inner_operator()
        self.layout_grid.addWidget(container_add_inner_operator, r, c + 2)

        '''add-row-button wird nach unten verschoben'''
        self.layout_grid.addWidget(self.bt_new_row, r + 1, c)

        self.save_plot()

    def add_actor(self):
        """fügt eine neue Operator-Auswahl mit nachfolgender Actor-Auswahl hinzu"""
        add_operator_widget = self.sender().parentWidget()  # plus/minus-Symbol

        r, c, _, _ = self.layout_grid.getItemPosition(self.layout_grid.indexOf(add_operator_widget))
        self.layout_grid.addWidget(add_operator_widget, r, c + 2)  # plus/minus-Symbol wird um 2 nach links verschoben
        cb_operator = self.create_combo_operator('inner')
        cb_operator.currentIndexChanged.connect(self.save_plot)
        self.layout_grid.addWidget(cb_operator, r, c)

        cb_actors = self.create_combo_actors()
        cb_actors.currentIndexChanged.connect(self.save_plot)
        self.layout_grid.addWidget(cb_actors, r, c + 1)

        self.save_plot()

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
            if cb_operator_between_rows := self.layout_grid.itemAtPosition(r + 1, self.col_operator_between_rows):  # mehr als 1 reihe vorhanden
                cb_operator_between_rows.widget().deleteLater()  # delete Operater between rows
                delta = 2
            elif r > 1:
                delta = 2
                cb_operator_between_rows_above = self.layout_grid.itemAtPosition(r - 1, self.col_operator_between_rows)
                cb_operator_between_rows_above.widget().deleteLater()
            for col in range(self.layout_grid.columnCount() + 1):
                for row in range(r+1, self.layout_grid.columnCount() + 1):
                    if cell := self.layout_grid.itemAtPosition(row, col):
                        self.layout_grid.addWidget(cell.widget(), row - delta, col)

        QTimer.singleShot(50, self.save_plot)

    def create_combo_actors(self):
        cb_actors = QComboBoxToFindData()
        cb_actors.setObjectName(self.object_name_actors)
        cb_actors.setFixedWidth(self.width_cb_actors)
        self.fill_cb_actors(cb_actors)
        return cb_actors

    def create_combo_operator(self, typ: Literal['inner', 'between']):
        cb_operator = QComboBox()
        cb_operator.setObjectName(self.object_name_inner_operator if typ == 'inner'
                                  else self.object_name_operator_between_rows)
        cb_operator.setFixedWidth(self.width_inner_operator)
        if typ == 'inner':
            cb_operator.setStyleSheet('background: #d9e193')
        else:
            cb_operator.setStyleSheet('background: #8ddee1')

        self.fill_cb_operator(cb_operator)

        return cb_operator

    def create_widget__add_inner_operator(self):
        container = QWidget()
        container.setFixedWidth(self.width_container__add_inner_operator)
        layout_container = QHBoxLayout()
        layout_container.setSpacing(0)
        container.setLayout(layout_container)

        bt_del_inner_operator = QPushButton(QIcon(os.path.join(self.path_to_icons, 'minus-circle.png')), None,
                                            clicked=self.del_actor)
        bt_add_inner_operator = QPushButton(QIcon(os.path.join(self.path_to_icons, 'plus-circle.png')), None,
                                            clicked=self.add_actor)
        layout_container.addWidget(bt_del_inner_operator)
        layout_container.addWidget(bt_add_inner_operator)
        container.setObjectName('add_inner_operator')
        container.setFixedWidth(self.width_container__add_inner_operator)

        return container

    def fill_cb_actors(self, cb_actors: QComboBox):
        for person in self.persons:
            cb_actors.addItem(QIcon(os.path.join(self.path_to_icons, 'user.png')), f'{person.f_name} {person.l_name}',
                              person.id)

    def fill_cb_operator(self, combo_operator: QComboBox):
        for data, text in self.data_text_operator.items():
            combo_operator.addItem(text, data)

    def reload_object_with_fixed_cast(self):
        self.object_with_fixed_cast = self.builder.object_with_fixed_cast__refresh_func()

    def reset_fixed_cast_plot(self):
        self.reload_object_with_fixed_cast()
        self.clear_plot()
        QTimer.singleShot(20, self.plot_eval_str)

    def clear_plot(self):
        for i in range(self.layout_grid.count()):
            self.layout_grid.itemAt(i).widget().deleteLater()

    def plot_eval_str(self):
        if not self.object_with_fixed_cast.fixed_cast:
            self.layout_grid.addWidget(self.bt_new_row, 0, 0)
            return
        form = backtranslate_eval_str(self.object_with_fixed_cast.fixed_cast)
        form_cleaned = self.proof_form_to_not_assigned_persons(form)

        for row_idx, row in enumerate(form_cleaned):
            if type(row) == str:
                cb_operator = self.create_combo_operator('between')
                cb_operator.setCurrentIndex(cb_operator.findData(row))
                cb_operator.currentIndexChanged.connect(self.save_plot)
                self.layout_grid.addWidget(cb_operator, row_idx, self.col_operator_between_rows)
            else:
                self.layout_grid.addWidget(self.create_widget__add_inner_operator(), row_idx, len(row) + 1)
                for col_idx, element in enumerate(row):
                    if type(element) == str:
                        cb_operator = self.create_combo_operator('inner')
                        cb_operator.setCurrentIndex(cb_operator.findData(element))
                        cb_operator.currentIndexChanged.connect(self.save_plot)
                        self.layout_grid.addWidget(cb_operator, row_idx, col_idx+1)
                    else:
                        cb_actors = self.create_combo_actors()
                        cb_actors.setCurrentIndex(cb_actors.findData(element))
                        cb_actors.currentIndexChanged.connect(self.save_plot)
                        self.layout_grid.addWidget(cb_actors, row_idx, col_idx+1)

        self.layout_grid.addWidget(self.bt_new_row, len(form_cleaned), 0)

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
        if form and isinstance(form[0], str):
            form.pop(0)
        return form
