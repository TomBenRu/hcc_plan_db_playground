import math
from functools import partial
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QFormLayout, QDialogButtonBox, QLineEdit, \
    QGroupBox, QGridLayout, QSlider, QPushButton, QHBoxLayout, QLayout
from pydantic import BaseModel

from configuration.solver import curr_config_handler
from gui.tools.custom_validators import IntAndFloatValidator, IntValidator
from gui.tools.custom_widgets.slider_with_press_event import SliderWithPressEvent


class DlgSettingsSolverParams(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)

        self.setWindowTitle('Solver-Parameter')

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.solver_configs = curr_config_handler.get_solver_config()
        self.form_layouts: dict[str, QFormLayout] = {}
        self.slider_scale_factors: dict[str, int] = {}

        self.setup_ui()

        self.update_widgets = False

    def setup_ui(self):
        self.add_description()
        self.add_group_box('Optimization Weights', self.solver_configs.minimization_weights,
                           self.add_minimization_weight_row)
        self.add_group_box('Constraint Multipliers', self.solver_configs.constraints_multipliers,
                           self.add_constraints_multiplier_row)
        self.add_button_box()

    def add_description(self):
        self.lb_description = QLabel('Solver Parameters')
        font_lb_description = self.lb_description.font()
        font_lb_description.setPointSize(16)
        font_lb_description.setBold(True)
        self.lb_description.setFont(font_lb_description)
        self.layout.addWidget(self.lb_description)

    def add_group_box(self, title: str, config_data: BaseModel,
                      add_row_function: Callable[[QFormLayout, str, dict | float], None]):
        group_box = QGroupBox(title)
        group_box.setStyleSheet("QGroupBox::title {color: rgb(0, 0, 255)}")
        layout = QFormLayout()
        self.form_layouts[title] = layout
        group_box.setLayout(layout)
        for field_name, data in config_data:
            add_row_function(layout, field_name, data)
        self.layout.addWidget(group_box)

    def add_minimization_weight_row(self, layout: QFormLayout, field_name: str, val: float):
        widget = QWidget()
        widget.setLayout(QHBoxLayout())
        widget.layout().setContentsMargins(0, 0, 0, 0)
        le_val = QLineEdit(str(val))
        le_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        le_val.setValidator(IntAndFloatValidator())
        le_val.setObjectName(f'le-{field_name}')
        widget.layout().addWidget(le_val)
        button_reset = QPushButton('Reset')
        button_reset.clicked.connect(partial(self.reset_le_minimization_weight, le_val))
        widget.layout().addWidget(button_reset)
        layout.addRow(f'{field_name}:', widget)

    def add_constraints_multiplier_row(self, layout: QFormLayout, field_name: str, params: dict[float, int]):
        widget = QWidget()
        layout_widget = QGridLayout()
        widget.setLayout(layout_widget)
        for row, (slider_val, multiplier) in enumerate(params.items()):
            widget_slider_value = QLabel(str(slider_val))
            le_value = QLineEdit()
            le_value.setObjectName(f'le-{field_name}-{slider_val}')
            le_value.setAlignment(Qt.AlignmentFlag.AlignRight)
            le_value.setFixedWidth(120)
            le_value.setValidator(IntValidator())
            slider = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider.setObjectName(f'scale-{field_name}-{slider_val}')
            _, next_power_of_ten = self.round_up_to_power_of_ten(multiplier)
            self.slider_scale_factors[slider.objectName()] = next_power_of_ten - 1
            slider.setMaximum(10)
            slider.setMinimum(-10)
            slider.setMinimumWidth(200)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.setValue(multiplier / 10 ** (next_power_of_ten - 1))
            slider.valueChanged.connect(partial(self.set_text_of_le_value, le_value, slider))
            le_value.setText(str(multiplier))
            le_value.textChanged.connect(partial(self.set_value_of_slider, slider))
            bt_reset = QPushButton('Reset')
            bt_reset.clicked.connect(partial(self.reset_le_constraints_value, le_value))
            layout_widget.addWidget(widget_slider_value, row, 0)
            layout_widget.addWidget(slider, row, 1)
            layout_widget.addWidget(le_value, row, 2)
            layout_widget.addWidget(bt_reset, row, 3)

        layout.addRow(f'{field_name}:', widget)

    def add_button_box(self):
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def set_text_of_le_value(self, le: QLineEdit, slider: SliderWithPressEvent, val: int):
        if self.update_widgets:
            return
        self.update_widgets = True
        le.setText(str(val * 10 ** self.slider_scale_factors[slider.objectName()]))
        self.update_widgets = False

    def set_value_of_slider(self, slider: SliderWithPressEvent, val: str):
        if self.update_widgets:
            return
        self.slider_scale_factors[slider.objectName()] = self.round_up_to_power_of_ten(int(val))[1] - 1
        self.update_widgets = True
        slider.setValue(int(val) / 10 ** (self.slider_scale_factors[slider.objectName()]))
        self.update_widgets = False

    def reset_le_constraints_value(self, le: QLineEdit):
        field_name, slider_val = le.objectName().split('-')[1:]
        saved_value = self.solver_configs.constraints_multipliers.__getattribute__(field_name)[float(slider_val)]
        le.setText(str(saved_value))

    def reset_le_minimization_weight(self, le: QLineEdit):
        field_name = le.objectName().split('-')[1]
        le.setText(str(self.solver_configs.minimization_weights.__getattribute__(field_name)))

    def round_up_to_power_of_ten(self, number) -> tuple[int, int]:
        if number == 0:
            return 1, 1

        abs_number = abs(number)
        log10_number = math.log10(abs_number)
        next_power_of_ten = math.ceil(log10_number)
        result = 10 ** next_power_of_ten
        if number < 0:
            result = -result

        return result, next_power_of_ten

    def accept(self):
        self.update_minimization_weights()
        self.update_constraints_multipliers()
        curr_config_handler.save_config_to_file(self.solver_configs)

        super().accept()

    def update_minimization_weights(self):
        line_edits: list[QLineEdit] = self.get_line_edits('Optimization Weights')
        for le in line_edits:
            field_name = le.objectName().split('-')[1]
            self.solver_configs.minimization_weights.__setattr__(field_name, float(le.text()))

    def update_constraints_multipliers(self):
        line_edits: list[QLineEdit] = self.get_line_edits('Constraint Multipliers')
        for le in line_edits:
            field_name, slider_val = le.objectName().split('-')[1:]
            self.solver_configs.constraints_multipliers.__getattribute__(field_name)[float(slider_val)] = int(le.text())

    def get_line_edits(self, layout_name: str) -> list[QLineEdit]:
        line_edits = []
        layout = self.form_layouts[layout_name]
        for i in range(layout.count()):
            if layout_values := layout.itemAt(i).widget().layout():
                for j in range(layout_values.count()):
                    if isinstance(layout_values.itemAt(j).widget(), QLineEdit):
                        line_edits.append(layout_values.itemAt(j).widget())
        return line_edits
