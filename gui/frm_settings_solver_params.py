from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QFormLayout, QDialogButtonBox, QLineEdit, \
    QGroupBox, QGridLayout, QSlider, QPushButton

from configfiguration.solver import solver_configs
from gui.tools.custom_validators import IntAndFloatValidator, IntValidator
from gui.tools.custom_widgets.slider_with_press_event import SliderWithPressEvent


class DlgSettingsSolverParams(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)

        self.setWindowTitle('Solver-Parameter')

        self.solver_configs = solver_configs

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.lb_description = QLabel('Solver-Parameter')
        font_lb_description = self.lb_description.font()
        font_lb_description.setPointSize(16)
        font_lb_description.setBold(True)
        self.lb_description.setFont(font_lb_description)
        self.layout.addWidget(self.lb_description)

        self.group_minimize_params = QGroupBox('Optimierungsgewichtungen')
        self.layout.addWidget(self.group_minimize_params)
        self.group_constraints_multiplier = QGroupBox('Constraint-Multiplikatoren')
        self.layout.addWidget(self.group_constraints_multiplier)

        self.slider_scale_factors: dict[str, int] = {}
        self.layout_params = QFormLayout()
        self.group_minimize_params.setLayout(self.layout_params)
        self.layout_constraints_multiplier = QFormLayout()
        self.group_constraints_multiplier.setLayout(self.layout_constraints_multiplier)

        self.le_unsigned = QLineEdit()
        self.le_unsigned.setValidator(IntAndFloatValidator())
        self.layout_params.addRow('Unbesetzt:', self.le_unsigned)

        self.slider_loc_pref = SliderWithPressEvent(Qt.Orientation.Horizontal)
        self.layout_constraints_multiplier.addRow('Einrichtungspräferenz:', self.slider_loc_pref)

        self.fill_layout_constraints_multiplier()

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                           | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.update_widgets = False

    def fill_layout_constraints_multiplier(self):
        for field_name, params in self.solver_configs.constraints_multipliers:
            widget = QWidget()
            layout_widget = QGridLayout()
            widget.setLayout(layout_widget)
            for row, (slider_val, multiplier) in enumerate(params.items()):
                widget_slider_value = QLabel(str(slider_val))
                le_value = QLineEdit()
                le_value.setAlignment(Qt.AlignmentFlag.AlignRight)
                le_value.setFixedWidth(120)
                le_value.setValidator(IntValidator())
                slider = SliderWithPressEvent(Qt.Orientation.Horizontal)
                slider.setObjectName(f'{field_name}-{slider_val}')
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
                bt_reset.clicked.connect(partial(self.reset_le_value, le_value, slider))
                layout_widget.addWidget(widget_slider_value, row, 0)
                layout_widget.addWidget(slider, row, 1)
                layout_widget.addWidget(le_value, row, 2)
                layout_widget.addWidget(bt_reset, row, 3)

            self.layout_constraints_multiplier.addRow(field_name, widget)

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

    def reset_le_value(self, le: QLineEdit, slider: SliderWithPressEvent):
        field_name, slider_val = slider.objectName().split('-')
        saved_value = self.solver_configs.constraints_multipliers.__getattribute__(field_name)[float(slider_val)]
        le.setText(str(saved_value))

    def round_up_to_power_of_ten(self, number) -> tuple[int, int]:
        """
        Rounds the given decimal integer up to the nearest power of ten.
        Handles both positive and negative numbers correctly.

        Args:
        number (int): The decimal integer to be rounded up.

        Returns:
        int: The number rounded up to the nearest power of ten and the next power of ten.
        """
        import math

        if number == 0:
            return 1, 1

        # Calculate the absolute value of the number
        abs_number = abs(number)

        # Calculate the logarithm (base 10) of the absolute number
        log10_number = math.log10(abs_number)

        # Calculate the next integer (ceiling of the logarithm)
        next_power_of_ten = math.ceil(log10_number)

        # Calculate 10 to the power of the next integer
        result = 10 ** next_power_of_ten

        # If the original number was negative, make the result negative
        if number < 0:
            result = -result

        return result, next_power_of_ten

