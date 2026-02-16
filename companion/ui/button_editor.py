"""
Button Editor Panel: Side panel for editing button properties

Provides fields for label, color, icon, action type (hotkey/media key),
keyboard shortcut recorder, and media key dropdown.
Changes emit signals for live preview in button grid.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QColorDialog,
    QComboBox,
    QSpinBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from companion.config_manager import ACTION_HOTKEY, ACTION_MEDIA_KEY, MOD_NONE
from companion.ui.icon_picker import IconPicker
from companion.ui.keyboard_recorder import KeyboardRecorder

# Common USB HID consumer control codes for media keys
# Format: (display_name, consumer_code)
MEDIA_KEY_OPTIONS = [
    ("Play/Pause", 0xCD),
    ("Next Track", 0xB5),
    ("Previous Track", 0xB6),
    ("Stop", 0xB7),
    ("Volume Up", 0xE9),
    ("Volume Down", 0xEA),
    ("Mute", 0xE2),
    ("Browser Home", 0x0223),
    ("Browser Back", 0x0224),
]


class ButtonEditor(QWidget):
    """Side panel for editing button properties"""

    # Signal emitted when button properties change
    # Payload: updated button dict
    button_updated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_button = None
        self.current_page_idx = 0
        self.current_button_idx = 0
        self._updating = False  # Flag to prevent recursion during updates

        # Create widgets
        self.label_input = QLineEdit()
        self.label_input.setMaxLength(16)
        self.label_input.setPlaceholderText("Button label")
        self.label_input.textChanged.connect(self._on_label_changed)

        self.description_input = QLineEdit()
        self.description_input.setMaxLength(32)
        self.description_input.setPlaceholderText("Description (e.g., Super+1)")
        self.description_input.textChanged.connect(self._on_description_changed)

        self.color_button = QPushButton("Choose Color")
        self.color_button.setStyleSheet("background-color: #3498DB; color: white;")
        self.color_button.clicked.connect(self._on_color_clicked)
        self.color_display = QLabel()
        self.color_display.setFixedWidth(30)
        self.color_display.setFixedHeight(30)
        self.color_display.setStyleSheet("border: 1px solid #ccc;")

        self.icon_picker = IconPicker()
        self.icon_picker.icon_selected.connect(self._on_icon_changed)

        self.action_type_combo = QComboBox()
        self.action_type_combo.addItem("Hotkey", ACTION_HOTKEY)
        self.action_type_combo.addItem("Media Key", ACTION_MEDIA_KEY)
        self.action_type_combo.currentIndexChanged.connect(self._on_action_type_changed)

        self.keyboard_recorder = KeyboardRecorder()
        self.keyboard_recorder.shortcut_confirmed.connect(self._on_shortcut_confirmed)

        # Media key dropdown
        self.media_key_combo = QComboBox()
        for name, code in MEDIA_KEY_OPTIONS:
            self.media_key_combo.addItem(f"{name} (0x{code:02X})", code)
        self.media_key_combo.currentIndexChanged.connect(self._on_media_key_changed)
        self.media_key_combo.setVisible(False)  # Hidden by default (Hotkey mode)

        # Grid positioning spinboxes
        self.grid_row_spin = QSpinBox()
        self.grid_row_spin.setRange(-1, 2)
        self.grid_row_spin.setValue(-1)
        self.grid_row_spin.setSpecialValueText("Auto")
        self.grid_row_spin.valueChanged.connect(self._on_grid_pos_changed)

        self.grid_col_spin = QSpinBox()
        self.grid_col_spin.setRange(-1, 3)
        self.grid_col_spin.setValue(-1)
        self.grid_col_spin.setSpecialValueText("Auto")
        self.grid_col_spin.valueChanged.connect(self._on_grid_pos_changed)

        # Grid span spinboxes
        self.col_span_spin = QSpinBox()
        self.col_span_spin.setRange(1, 4)
        self.col_span_spin.setValue(1)
        self.col_span_spin.valueChanged.connect(self._on_span_changed)

        self.row_span_spin = QSpinBox()
        self.row_span_spin.setRange(1, 3)
        self.row_span_spin.setValue(1)
        self.row_span_spin.valueChanged.connect(self._on_span_changed)

        self.span_hint_label = QLabel("Spans only apply to explicitly positioned buttons")
        self.span_hint_label.setStyleSheet("color: #888; font-size: 10px;")

        # Pressed color controls
        self.auto_darken_check = QCheckBox("Auto-darken")
        self.auto_darken_check.setChecked(True)
        self.auto_darken_check.stateChanged.connect(self._on_auto_darken_changed)

        self.pressed_color_button = QPushButton("Choose Pressed Color")
        self.pressed_color_button.clicked.connect(self._on_pressed_color_clicked)
        self.pressed_color_button.setVisible(False)
        self.pressed_color_display = QLabel()
        self.pressed_color_display.setFixedWidth(30)
        self.pressed_color_display.setFixedHeight(30)
        self.pressed_color_display.setStyleSheet("background-color: #000000; border: 1px solid #ccc;")
        self.pressed_color_display.setVisible(False)
        self._pressed_color_value = 0x000000

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self._on_apply_clicked)

        # Layout
        layout = QVBoxLayout(self)

        # Label section
        layout.addWidget(QLabel("Label:"))
        layout.addWidget(self.label_input)

        # Description section
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.description_input)

        # Color section
        layout.addWidget(QLabel("Color:"))
        color_layout = QHBoxLayout()
        color_layout.addWidget(self.color_button)
        color_layout.addWidget(self.color_display)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        # Icon section
        layout.addWidget(QLabel("Icon:"))
        layout.addWidget(self.icon_picker)

        # Action type section
        layout.addWidget(QLabel("Action Type:"))
        layout.addWidget(self.action_type_combo)

        # Shortcut section (hotkey mode)
        self.shortcut_label = QLabel("Shortcut:")
        layout.addWidget(self.shortcut_label)
        layout.addWidget(self.keyboard_recorder)

        # Media key section (media key mode)
        self.media_key_label = QLabel("Media Key:")
        self.media_key_label.setVisible(False)
        layout.addWidget(self.media_key_label)
        layout.addWidget(self.media_key_combo)

        # Grid positioning section
        layout.addWidget(QLabel("Grid Position:"))
        grid_pos_layout = QHBoxLayout()
        grid_pos_layout.addWidget(QLabel("Row:"))
        grid_pos_layout.addWidget(self.grid_row_spin)
        grid_pos_layout.addWidget(QLabel("Col:"))
        grid_pos_layout.addWidget(self.grid_col_spin)
        layout.addLayout(grid_pos_layout)
        self.grid_hint_label = QLabel("Both -1 = auto-flow, both >= 0 = explicit")
        self.grid_hint_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.grid_hint_label)

        # Grid span section
        layout.addWidget(QLabel("Grid Span:"))
        span_layout = QHBoxLayout()
        span_layout.addWidget(QLabel("Col Span:"))
        span_layout.addWidget(self.col_span_spin)
        span_layout.addWidget(QLabel("Row Span:"))
        span_layout.addWidget(self.row_span_spin)
        layout.addLayout(span_layout)
        layout.addWidget(self.span_hint_label)

        # Pressed color section
        layout.addWidget(QLabel("Pressed Color:"))
        layout.addWidget(self.auto_darken_check)
        pressed_color_layout = QHBoxLayout()
        pressed_color_layout.addWidget(self.pressed_color_button)
        pressed_color_layout.addWidget(self.pressed_color_display)
        pressed_color_layout.addStretch()
        layout.addLayout(pressed_color_layout)

        # Apply button
        layout.addStretch()
        layout.addWidget(self.apply_button)

        self.setLayout(layout)
        self.setMinimumWidth(280)

    def load_button(self, button_dict: dict, page_idx: int, button_idx: int):
        """Load button data into editor"""
        self._updating = True

        self.current_button = button_dict
        self.current_page_idx = page_idx
        self.current_button_idx = button_idx

        self.label_input.setText(button_dict.get("label", ""))
        self.description_input.setText(button_dict.get("description", ""))

        color = button_dict.get("color", 0x3498DB)
        self._set_color_display(color)

        icon = button_dict.get("icon", "")
        self.icon_picker.set_symbol(icon)

        action_type = button_dict.get("action_type", ACTION_HOTKEY)
        self.action_type_combo.setCurrentIndex(0 if action_type == ACTION_HOTKEY else 1)
        self._update_action_type_visibility(action_type)

        modifiers = button_dict.get("modifiers", MOD_NONE)
        keycode = button_dict.get("keycode", 0)
        self.keyboard_recorder.set_shortcut(modifiers, keycode)

        # Load media key consumer code
        consumer_code = button_dict.get("consumer_code", 0)
        self._set_media_key_combo(consumer_code)

        # Load grid positioning
        self.grid_row_spin.setValue(button_dict.get("grid_row", -1))
        self.grid_col_spin.setValue(button_dict.get("grid_col", -1))

        # Load grid span
        col_span = button_dict.get("col_span", 1)
        row_span = button_dict.get("row_span", 1)
        self.col_span_spin.setValue(col_span)
        self.row_span_spin.setValue(row_span)
        self._update_span_ui()

        # Load pressed color
        pressed_color = button_dict.get("pressed_color", 0x000000)
        self._pressed_color_value = pressed_color
        is_auto = (pressed_color == 0x000000)
        self.auto_darken_check.setChecked(is_auto)
        self.pressed_color_button.setVisible(not is_auto)
        self.pressed_color_display.setVisible(not is_auto)
        if not is_auto:
            self._set_pressed_color_display(pressed_color)

        self._updating = False

    def get_button(self) -> dict:
        """Get current button data from editor"""
        action_type = self.action_type_combo.currentData()

        if action_type == ACTION_MEDIA_KEY:
            # Media key mode: read consumer code from dropdown
            consumer_code = self.media_key_combo.currentData() or 0
            modifiers = 0
            keycode = 0
        else:
            # Hotkey mode: read from keyboard recorder
            consumer_code = 0
            modifiers = self.keyboard_recorder.current_modifiers
            keycode = self.keyboard_recorder.current_keycode

        # Grid positioning
        grid_row = self.grid_row_spin.value()
        grid_col = self.grid_col_spin.value()

        # Grid span (only meaningful for explicit positioning)
        col_span = self.col_span_spin.value() if (grid_row >= 0 and grid_col >= 0) else 1
        row_span = self.row_span_spin.value() if (grid_row >= 0 and grid_col >= 0) else 1

        # Clamp span to grid bounds
        if grid_col >= 0 and grid_col + col_span > 4:
            col_span = 4 - grid_col
        if grid_row >= 0 and grid_row + row_span > 3:
            row_span = 3 - grid_row

        # Pressed color
        pressed_color = 0x000000 if self.auto_darken_check.isChecked() else self._pressed_color_value

        return {
            "label": self.label_input.text(),
            "description": self.description_input.text(),
            "color": self._get_color_value(),
            "icon": self.icon_picker.get_symbol(),
            "action_type": action_type,
            "modifiers": modifiers,
            "keycode": keycode,
            "consumer_code": consumer_code,
            "grid_row": grid_row,
            "grid_col": grid_col,
            "pressed_color": pressed_color,
            "col_span": col_span,
            "row_span": row_span,
        }

    def _set_media_key_combo(self, consumer_code: int):
        """Set media key combo to matching consumer code value."""
        for i in range(self.media_key_combo.count()):
            if self.media_key_combo.itemData(i) == consumer_code:
                self.media_key_combo.setCurrentIndex(i)
                return
        # If not found, just select first item
        if self.media_key_combo.count() > 0:
            self.media_key_combo.setCurrentIndex(0)

    def _update_action_type_visibility(self, action_type: int):
        """Show/hide shortcut recorder vs media key dropdown based on action type."""
        is_hotkey = (action_type == ACTION_HOTKEY)
        self.keyboard_recorder.setVisible(is_hotkey)
        self.shortcut_label.setVisible(is_hotkey)
        self.media_key_combo.setVisible(not is_hotkey)
        self.media_key_label.setVisible(not is_hotkey)

    def _on_label_changed(self):
        """Label text changed"""
        if not self._updating:
            self._emit_update()

    def _on_description_changed(self):
        """Description text changed"""
        if not self._updating:
            self._emit_update()

    def _on_color_clicked(self):
        """Color button clicked - open color dialog"""
        color_val = self._get_color_value()
        qcolor = self._value_to_qcolor(color_val)

        new_color = QColorDialog.getColor(qcolor, self, "Choose Button Color")
        if new_color.isValid():
            color_val = self._qcolor_to_value(new_color)
            self._set_color_display(color_val)
            self._emit_update()

    def _on_icon_changed(self, icon_str: str):
        """Icon picker changed"""
        if not self._updating:
            self._emit_update()

    def _on_action_type_changed(self, index: int):
        """Action type combo changed"""
        action_type = self.action_type_combo.currentData()
        self._update_action_type_visibility(action_type)
        if not self._updating:
            self._emit_update()

    def _on_shortcut_confirmed(self, modifiers: int, keycode: int):
        """Keyboard recorder confirmed shortcut"""
        self._emit_update()

    def _on_media_key_changed(self, index: int):
        """Media key dropdown changed"""
        if not self._updating:
            self._emit_update()

    def _on_grid_pos_changed(self):
        """Grid position spinbox changed"""
        if not self._updating:
            # Validate: warn if partial positioning
            row = self.grid_row_spin.value()
            col = self.grid_col_spin.value()
            if (row >= 0) != (col >= 0):
                self.grid_hint_label.setText("Warning: set both row AND col, or both to Auto")
                self.grid_hint_label.setStyleSheet("color: #E74C3C; font-size: 10px;")
            else:
                self.grid_hint_label.setText("Both -1 = auto-flow, both >= 0 = explicit")
                self.grid_hint_label.setStyleSheet("color: #888; font-size: 10px;")
            self._update_span_ui()
            self._emit_update()

    def _on_span_changed(self):
        """Grid span spinbox changed"""
        if not self._updating:
            self._update_span_ui()
            self._emit_update()

    def _update_span_ui(self):
        """Update span UI: enable/disable based on explicit positioning"""
        row = self.grid_row_spin.value()
        col = self.grid_col_spin.value()
        is_explicit = (row >= 0 and col >= 0)
        self.col_span_spin.setEnabled(is_explicit)
        self.row_span_spin.setEnabled(is_explicit)
        if not is_explicit:
            self.span_hint_label.setText("Position button explicitly to enable spanning")
            self.span_hint_label.setStyleSheet("color: #E67E22; font-size: 10px;")
        else:
            max_col_span = 4 - col
            max_row_span = 3 - row
            self.col_span_spin.setMaximum(max_col_span)
            self.row_span_spin.setMaximum(max_row_span)
            self.span_hint_label.setText(
                f"Max span: {max_col_span}x{max_row_span} from ({row},{col})"
            )
            self.span_hint_label.setStyleSheet("color: #888; font-size: 10px;")

    def _on_auto_darken_changed(self, state: int):
        """Auto-darken checkbox changed"""
        is_auto = self.auto_darken_check.isChecked()
        self.pressed_color_button.setVisible(not is_auto)
        self.pressed_color_display.setVisible(not is_auto)
        if is_auto:
            self._pressed_color_value = 0x000000
        if not self._updating:
            self._emit_update()

    def _on_pressed_color_clicked(self):
        """Pressed color button clicked - open color dialog"""
        qcolor = self._value_to_qcolor(self._pressed_color_value if self._pressed_color_value else 0xFF0000)
        new_color = QColorDialog.getColor(qcolor, self, "Choose Pressed Color")
        if new_color.isValid():
            self._pressed_color_value = self._qcolor_to_value(new_color)
            self._set_pressed_color_display(self._pressed_color_value)
            self._emit_update()

    def _set_pressed_color_display(self, color_val: int):
        """Update pressed color display widget"""
        qcolor = self._value_to_qcolor(color_val)
        self.pressed_color_display.setStyleSheet(
            f"background-color: {qcolor.name()}; border: 1px solid #ccc;"
        )

    def _on_apply_clicked(self):
        """Apply button clicked"""
        button_data = self.get_button()
        self.button_updated.emit(button_data)

    def _emit_update(self):
        """Emit button_updated signal with current data"""
        button_data = self.get_button()
        self.button_updated.emit(button_data)

    def _set_color_display(self, color_val: int):
        """Update color display widget"""
        qcolor = self._value_to_qcolor(color_val)
        self.color_display.setStyleSheet(f"background-color: {qcolor.name()}; border: 1px solid #ccc;")

    def _get_color_value(self) -> int:
        """Get color value from display widget"""
        style = self.color_display.styleSheet()
        # Extract hex color from background-color: #RRGGBB
        if "background-color:" in style:
            hex_str = style.split("background-color:")[1].split(";")[0].strip()
            if hex_str.startswith("#"):
                return int(hex_str[1:], 16)
        return 0x3498DB  # Default fallback

    def _value_to_qcolor(self, color_val: int) -> QColor:
        """Convert RGB hex value to QColor"""
        r = (color_val >> 16) & 0xFF
        g = (color_val >> 8) & 0xFF
        b = color_val & 0xFF
        return QColor(r, g, b)

    def _qcolor_to_value(self, qcolor: QColor) -> int:
        """Convert QColor to RGB hex value"""
        return (qcolor.red() << 16) | (qcolor.green() << 8) | qcolor.blue()
