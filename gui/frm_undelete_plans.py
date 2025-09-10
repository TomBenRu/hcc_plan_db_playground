from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QCheckBox, QDialogButtonBox, \
    QListWidget, QTableWidget, QHeaderView, QTableWidgetItem
from PySide6.QtCore import Qt

from database import db_services, schemas
from tools.helper_functions import date_to_string, time_to_string


class SortableTableWidgetItem(QTableWidgetItem):
    """Erweitert die Standard-QTableWidgetItem um die Möglichkeit, nach UserRole-Daten zu sortieren."""
    def __init__(self, text: str, data = None, sort_data = None,
                 user_role_data: Qt.ItemDataRole = Qt.ItemDataRole.UserRole,
                 user_role_sort_data: Qt.ItemDataRole = Qt.ItemDataRole.UserRole + 1):
        super().__init__()
        self.setText(text)
        self.setData(user_role_data, data)
        self.setData(user_role_sort_data, sort_data)
        self.user_role_data = user_role_data
        self.user_role_sort_data = user_role_sort_data

    def __lt__(self, other):
        self_data = self.data(self.user_role_sort_data)
        other_data = other.data(self.user_role_sort_data)
        if self_data is not None and other_data is not None:
            return self_data < other_data
        return self.text() < other.text()



class DlgUndeletePlans(QDialog):
    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent=parent)

        self.team_id = team_id
        self.selected_plan_ids: set[UUID] = set()

        self._setup_ui()
        self._fill_in_plans_table()
        self._adjust_dialog_width_to_table()

    def _setup_ui(self):
        self.setWindowTitle(self.tr("Undelete Plans"))

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(self.tr("Select the plans you want to undelete:"))
        self.layout_head.addWidget(self.lb_description)

        self._setup_plans_table()

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_plans_table(self):
        self.table_plans = QTableWidget()
        table_columns = [self.tr("Name"), self.tr("Start"), self.tr("End"), self.tr("Deleted")]
        self.table_plans.setColumnCount(len(table_columns))
        self.table_plans.setHorizontalHeaderLabels(table_columns)
        self.table_plans.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_plans.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        self.table_plans.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_plans.setAlternatingRowColors(True)
        self.table_plans.setSortingEnabled(True)
        self.table_plans.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.layout_body.addWidget(self.table_plans)
        self.table_plans.itemSelectionChanged.connect(self._on_selection_changed)
        self.lb_selected_count = QLabel(self.tr("Selected: 0"))
        self.layout_body.addWidget(self.lb_selected_count)

    def _fill_in_plans_table(self):
        plan_ids = db_services.Plan.get_prep_deleted_from__team(self.team_id)
        self.table_plans.setRowCount(len(plan_ids))
        for row, plan_id in enumerate(plan_ids):
            plan: schemas.Plan = db_services.Plan.get(plan_id, small=True)
            item_name = SortableTableWidgetItem(plan.name, plan_id)
            self.table_plans.setItem(row, 0, item_name)
            date_start = date_to_string(plan.plan_period.start)
            date_end = date_to_string(plan.plan_period.end)
            date_deleted = date_to_string(plan.prep_delete.date())
            time_deleted = time_to_string(plan.prep_delete.time())
            date_time_deleted = f"{date_deleted} {time_deleted}"
            item_date_start = SortableTableWidgetItem(date_start, None, plan.plan_period.start)
            item_date_end = SortableTableWidgetItem(date_end, None, plan.plan_period.end)
            item_date_deleted = SortableTableWidgetItem(date_time_deleted, None, plan.prep_delete)
            self.table_plans.setItem(row, 1, item_date_start)
            self.table_plans.setItem(row, 2, item_date_end)
            self.table_plans.setItem(row, 3, item_date_deleted)

    def _on_selection_changed(self):
        self.lb_selected_count.setText(self.tr("Selected: {}").format(len(self.get_selected_plan_ids())))

    def _adjust_dialog_width_to_table(self):
        # Calculate the total width of the table
        table_width = self.table_plans.verticalHeader().width()  # The width of the vertical header
        for column in range(self.table_plans.columnCount()):
            table_width += self.table_plans.columnWidth(column)  # The width of each column

        # Adding the width of the vertical scroll bar if present
        if self.table_plans.verticalScrollBar().isVisible():
            table_width += self.table_plans.verticalScrollBar().width()

        # Adding padding
        table_width += 70

        # Set the width of the dialog to the width of the table
        self.setMinimumWidth(table_width)

    def get_selected_plan_ids(self) -> set[UUID]:
        return {self.table_plans.item(row, 0).data(Qt.ItemDataRole.UserRole)
                for row in range(self.table_plans.rowCount())
                if self.table_plans.item(row, 0).isSelected()}

    def accept(self) -> None:
        self.selected_plan_ids = self.get_selected_plan_ids()
        super().accept()
