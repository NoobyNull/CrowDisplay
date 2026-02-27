"""
Properties Panel: Widget property editor for the WYSIWYG editor.
"""

import os
import logging

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QGroupBox,
    QSpinBox,
    QCheckBox,
    QColorDialog,
    QScrollArea,
    QLineEdit,
    QWidget,
)
from PySide6.QtCore import Qt, Signal

from companion.config_manager import (
    WIDGET_HOTKEY_BUTTON,
    WIDGET_STAT_MONITOR,
    WIDGET_STATUS_BAR,
    WIDGET_CLOCK,
    WIDGET_TEXT_LABEL,
    WIDGET_SEPARATOR,
    WIDGET_TYPE_NAMES,
    ACTION_HOTKEY,
    ACTION_MEDIA_KEY,
    ACTION_LAUNCH_APP,
    ACTION_SHELL_CMD,
    ACTION_OPEN_URL,
    ACTION_PAGE_GOTO,
    ACTION_BRIGHTNESS,
    ACTION_DDC,
    ACTION_PAGE_NEXT,
    ACTION_TYPE_NAMES,
    ENCODER_MODE_NAMES,
    DDC_VCP_NAMES,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    SNAP_GRID,
    WIDGET_MIN_W,
    WIDGET_MIN_H,
    get_default_hardware_buttons,
    get_default_encoder,
)
from companion.ui.icon_picker import IconPicker
from companion.ui.keyboard_recorder import KeyboardRecorder
from companion.ui.no_scroll_combo import NoScrollComboBox
from companion.ui.editor_constants import (
    STAT_TYPE_OPTIONS,
    STAT_TYPE_NAMES,
    MEDIA_KEY_OPTIONS,
)
from companion.ui.editor_utils import (
    _resolve_icon_source,
    _load_icon_pixmap,
    _int_to_qcolor,
    _qcolor_to_int,
)

logger = logging.getLogger(__name__)


class PropertiesPanel(QScrollArea):
    """Right sidebar for editing selected widget properties."""

    widget_updated = Signal(str, dict)  # widget_id, updated widget_dict
    hw_config_updated = Signal()  # hardware input config changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)
        self._updating = False
        self._widget_idx = -1
        self._widget_id = ""
        self._widget_dict = None

        container = QWidget()
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(4, 4, 4, 4)

        # Type label
        self.type_label = QLabel("No widget selected")
        self.type_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFD700;")
        self.main_layout.addWidget(self.type_label)

        # Position group
        self.pos_group = QGroupBox("Position && Size")
        pos_group = self.pos_group
        pos_layout = QGridLayout()
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, DISPLAY_WIDTH)
        self.x_spin.setSingleStep(SNAP_GRID)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, DISPLAY_HEIGHT)
        self.y_spin.setSingleStep(SNAP_GRID)
        self.w_spin = QSpinBox()
        self.w_spin.setRange(WIDGET_MIN_W, DISPLAY_WIDTH)
        self.w_spin.setSingleStep(SNAP_GRID)
        self.h_spin = QSpinBox()
        self.h_spin.setRange(WIDGET_MIN_H, DISPLAY_HEIGHT)
        self.h_spin.setSingleStep(SNAP_GRID)
        pos_layout.addWidget(QLabel("X:"), 0, 0)
        pos_layout.addWidget(self.x_spin, 0, 1)
        pos_layout.addWidget(QLabel("Y:"), 0, 2)
        pos_layout.addWidget(self.y_spin, 0, 3)
        pos_layout.addWidget(QLabel("W:"), 1, 0)
        pos_layout.addWidget(self.w_spin, 1, 1)
        pos_layout.addWidget(QLabel("H:"), 1, 2)
        pos_layout.addWidget(self.h_spin, 1, 3)
        pos_group.setLayout(pos_layout)
        self.main_layout.addWidget(pos_group)

        for spin in (self.x_spin, self.y_spin, self.w_spin, self.h_spin):
            spin.valueChanged.connect(self._on_position_changed)
            spin.setFocusPolicy(Qt.StrongFocus)

        # Common group: label + color
        self.common_group = QGroupBox("Common")
        common_group = self.common_group
        common_layout = QVBoxLayout()

        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Label:"))
        self.show_label_cb = QCheckBox("Show")
        self.show_label_cb.setChecked(True)
        self.show_label_cb.stateChanged.connect(self._on_property_changed)
        label_row.addStretch()
        label_row.addWidget(self.show_label_cb)
        common_layout.addLayout(label_row)
        self.label_input = QLineEdit()
        self.label_input.setMaxLength(32)
        self.label_input.textChanged.connect(self._on_property_changed)
        common_layout.addWidget(self.label_input)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(40, 24)
        self.color_btn.clicked.connect(self._on_color_clicked)
        color_row.addWidget(self.color_btn)
        color_row.addWidget(QLabel("BG:"))
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(40, 24)
        self.bg_color_btn.clicked.connect(self._on_bg_color_clicked)
        color_row.addWidget(self.bg_color_btn)
        self.bg_transparent_cb = QCheckBox("Transparent")
        self.bg_transparent_cb.stateChanged.connect(self._on_bg_transparent_changed)
        color_row.addWidget(self.bg_transparent_cb)
        color_row.addStretch()
        common_layout.addLayout(color_row)

        common_group.setLayout(common_layout)
        self.main_layout.addWidget(common_group)

        # Hotkey Button group
        self.hotkey_group = QGroupBox("Hotkey Button")
        hotkey_layout = QVBoxLayout()

        # Action Type first — drives which fields are shown
        hotkey_layout.addWidget(QLabel("Action Type:"))
        self.action_type_combo = NoScrollComboBox()
        for action_id, action_name in ACTION_TYPE_NAMES.items():
            self.action_type_combo.addItem(action_name, action_id)
        self.action_type_combo.currentIndexChanged.connect(self._on_action_type_changed)
        hotkey_layout.addWidget(self.action_type_combo)

        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("Description:"))
        self.show_description_cb = QCheckBox("Show")
        self.show_description_cb.setChecked(True)
        self.show_description_cb.stateChanged.connect(self._on_property_changed)
        desc_row.addStretch()
        desc_row.addWidget(self.show_description_cb)
        hotkey_layout.addLayout(desc_row)
        self.description_input = QLineEdit()
        self.description_input.setMaxLength(32)
        self.description_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.description_input)

        hotkey_layout.addWidget(QLabel("Icon:"))
        self.icon_picker = IconPicker()
        self.icon_picker.icon_selected.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.icon_picker)

        # Icon image picker (overrides symbol icon)
        hotkey_layout.addWidget(QLabel("Icon Image:"))
        img_row = QHBoxLayout()
        self.icon_image_btn = QPushButton("Browse...")
        self.icon_image_btn.clicked.connect(self._on_icon_image_browse)
        img_row.addWidget(self.icon_image_btn)
        self.icon_image_clear_btn = QPushButton("Clear")
        self.icon_image_clear_btn.clicked.connect(self._on_icon_image_clear)
        self.icon_image_clear_btn.setVisible(False)
        img_row.addWidget(self.icon_image_clear_btn)
        hotkey_layout.addLayout(img_row)
        self.icon_image_label = QLabel("")
        self.icon_image_label.setStyleSheet("color: #888; font-size: 11px;")
        self.icon_image_label.setWordWrap(True)
        hotkey_layout.addWidget(self.icon_image_label)
        self.icon_image_preview = QLabel()
        self.icon_image_preview.setFixedSize(64, 64)
        self.icon_image_preview.setAlignment(Qt.AlignCenter)
        self.icon_image_preview.setStyleSheet("border: 1px solid #444; background: #1a1a2e;")
        self.icon_image_preview.setVisible(False)
        hotkey_layout.addWidget(self.icon_image_preview)

        # Icon source cache: widget_id -> resolved filesystem path (for preview)
        self._icon_source_cache = {}

        # Page number spinner (for ACTION_PAGE_GOTO)
        self.page_goto_label = QLabel("Target Page:")
        self.page_goto_label.setVisible(False)
        hotkey_layout.addWidget(self.page_goto_label)
        self.page_goto_spin = QSpinBox()
        self.page_goto_spin.setRange(1, 16)
        self.page_goto_spin.setValue(1)
        self.page_goto_spin.setFocusPolicy(Qt.StrongFocus)
        self.page_goto_spin.setVisible(False)
        self.page_goto_spin.valueChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.page_goto_spin)

        self.shortcut_label = QLabel("Shortcut:")
        hotkey_layout.addWidget(self.shortcut_label)
        self.keyboard_recorder = KeyboardRecorder()
        self.keyboard_recorder.shortcut_confirmed.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.keyboard_recorder)

        self.media_key_label = QLabel("Media Key:")
        self.media_key_label.setVisible(False)
        hotkey_layout.addWidget(self.media_key_label)
        self.media_key_combo = NoScrollComboBox()
        for name, code in MEDIA_KEY_OPTIONS:
            self.media_key_combo.addItem(f"{name} (0x{code:02X})", code)
        self.media_key_combo.currentIndexChanged.connect(self._on_property_changed)
        self.media_key_combo.setVisible(False)
        hotkey_layout.addWidget(self.media_key_combo)

        # Launch App section
        self.launch_app_label = QLabel("Application:")
        self.launch_app_label.setVisible(False)
        hotkey_layout.addWidget(self.launch_app_label)
        self.app_picker_combo = NoScrollComboBox()
        self.app_picker_combo.setVisible(False)
        self.app_picker_combo.currentIndexChanged.connect(self._on_app_picker_changed)
        hotkey_layout.addWidget(self.app_picker_combo)
        self._apps_loaded = False

        self.launch_cmd_label = QLabel("Launch Command:")
        self.launch_cmd_label.setVisible(False)
        hotkey_layout.addWidget(self.launch_cmd_label)
        self.launch_cmd_input = QLineEdit()
        self.launch_cmd_input.setPlaceholderText("Exec command (auto-filled)")
        self.launch_cmd_input.setVisible(False)
        self.launch_cmd_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.launch_cmd_input)

        self.launch_wm_class_label = QLabel("WM_CLASS:")
        self.launch_wm_class_label.setVisible(False)
        hotkey_layout.addWidget(self.launch_wm_class_label)
        self.launch_wm_class_input = QLineEdit()
        self.launch_wm_class_input.setPlaceholderText("WM_CLASS (for focus-or-launch)")
        self.launch_wm_class_input.setVisible(False)
        self.launch_wm_class_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.launch_wm_class_input)

        self.focus_or_launch_check = QCheckBox("Focus existing window if running")
        self.focus_or_launch_check.setChecked(True)
        self.focus_or_launch_check.setVisible(False)
        self.focus_or_launch_check.stateChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.focus_or_launch_check)

        # Steam game toggle
        self.steam_game_check = QCheckBox("Steam Game")
        self.steam_game_check.setVisible(False)
        self.steam_game_check.stateChanged.connect(self._on_steam_game_toggled)
        hotkey_layout.addWidget(self.steam_game_check)

        self.steam_appid_label = QLabel("Steam App ID:")
        self.steam_appid_label.setVisible(False)
        hotkey_layout.addWidget(self.steam_appid_label)
        self.steam_appid_input = QLineEdit()
        self.steam_appid_input.setPlaceholderText("e.g., 1808500")
        self.steam_appid_input.setVisible(False)
        self.steam_appid_input.textChanged.connect(self._on_steam_appid_changed)
        hotkey_layout.addWidget(self.steam_appid_input)

        # Shell Command section
        self.shell_cmd_label = QLabel("Shell Command:")
        self.shell_cmd_label.setVisible(False)
        hotkey_layout.addWidget(self.shell_cmd_label)
        self.shell_cmd_input = QLineEdit()
        self.shell_cmd_input.setPlaceholderText("e.g., notify-send 'Hello'")
        self.shell_cmd_input.setVisible(False)
        self.shell_cmd_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.shell_cmd_input)

        # Open URL section
        self.url_label = QLabel("URL:")
        self.url_label.setVisible(False)
        hotkey_layout.addWidget(self.url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.setVisible(False)
        self.url_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.url_input)

        # DDC Monitor Control section
        self.ddc_section_label = QLabel("DDC Monitor Control:")
        self.ddc_section_label.setVisible(False)
        hotkey_layout.addWidget(self.ddc_section_label)

        self.ddc_vcp_combo = NoScrollComboBox()
        for vcp_code, vcp_name in DDC_VCP_NAMES.items():
            self.ddc_vcp_combo.addItem(vcp_name, vcp_code)
        self.ddc_vcp_combo.setVisible(False)
        self.ddc_vcp_combo.currentIndexChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.ddc_vcp_combo)

        ddc_val_row = QHBoxLayout()
        ddc_val_row.addWidget(QLabel("Value:"))
        self.ddc_value_spin = QSpinBox()
        self.ddc_value_spin.setRange(0, 65535)
        self.ddc_value_spin.setFocusPolicy(Qt.StrongFocus)
        self.ddc_value_spin.setVisible(False)
        self.ddc_value_spin.valueChanged.connect(self._on_property_changed)
        ddc_val_row.addWidget(self.ddc_value_spin)
        self.ddc_value_label = QLabel("")
        self.ddc_value_label.setVisible(False)
        ddc_val_row.addWidget(self.ddc_value_label)
        hotkey_layout.addLayout(ddc_val_row)

        ddc_adj_row = QHBoxLayout()
        ddc_adj_row.addWidget(QLabel("Adjustment:"))
        self.ddc_adjustment_spin = QSpinBox()
        self.ddc_adjustment_spin.setRange(-100, 100)
        self.ddc_adjustment_spin.setFocusPolicy(Qt.StrongFocus)
        self.ddc_adjustment_spin.setVisible(False)
        self.ddc_adjustment_spin.valueChanged.connect(self._on_property_changed)
        ddc_adj_row.addWidget(self.ddc_adjustment_spin)
        hotkey_layout.addLayout(ddc_adj_row)

        ddc_disp_row = QHBoxLayout()
        ddc_disp_row.addWidget(QLabel("Display #:"))
        self.ddc_display_spin = QSpinBox()
        self.ddc_display_spin.setRange(0, 8)
        self.ddc_display_spin.setSpecialValueText("Auto")
        self.ddc_display_spin.setFocusPolicy(Qt.StrongFocus)
        self.ddc_display_spin.setVisible(False)
        self.ddc_display_spin.valueChanged.connect(self._on_property_changed)
        ddc_disp_row.addWidget(self.ddc_display_spin)
        hotkey_layout.addLayout(ddc_disp_row)

        self.ddc_info_label = QLabel("adj!=0: relative (+/-), adj=0: absolute value")
        self.ddc_info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.ddc_info_label.setWordWrap(True)
        self.ddc_info_label.setVisible(False)
        hotkey_layout.addWidget(self.ddc_info_label)

        pressed_row = QHBoxLayout()
        self.auto_darken_check = QCheckBox("Auto-darken")
        self.auto_darken_check.setChecked(True)
        self.auto_darken_check.stateChanged.connect(self._on_auto_darken_changed)
        pressed_row.addWidget(self.auto_darken_check)
        self.pressed_color_btn = QPushButton()
        self.pressed_color_btn.setFixedSize(40, 24)
        self.pressed_color_btn.setVisible(False)
        self.pressed_color_btn.clicked.connect(self._on_pressed_color_clicked)
        pressed_row.addWidget(self.pressed_color_btn)
        pressed_row.addStretch()
        hotkey_layout.addLayout(pressed_row)

        self.hotkey_group.setLayout(hotkey_layout)
        self.main_layout.addWidget(self.hotkey_group)

        # Stat Monitor group
        self.stat_group = QGroupBox("Stat Monitor")
        stat_layout = QVBoxLayout()
        stat_layout.addWidget(QLabel("Stat Type:"))
        self.stat_type_combo = NoScrollComboBox()
        for name, tid in STAT_TYPE_OPTIONS:
            self.stat_type_combo.addItem(name, tid)
        self.stat_type_combo.currentIndexChanged.connect(self._on_stat_type_changed)
        stat_layout.addWidget(self.stat_type_combo)
        vpos_row = QHBoxLayout()
        vpos_row.addWidget(QLabel("Value Position:"))
        self.value_position_combo = NoScrollComboBox()
        self.value_position_combo.addItem("Inline", 0)
        self.value_position_combo.addItem("Value Top", 1)
        self.value_position_combo.addItem("Value Bottom", 2)
        self.value_position_combo.currentIndexChanged.connect(self._on_property_changed)
        vpos_row.addWidget(self.value_position_combo)
        stat_layout.addLayout(vpos_row)
        self.stat_group.setLayout(stat_layout)
        self.main_layout.addWidget(self.stat_group)

        # Status Bar group
        self.status_bar_group = QGroupBox("Status Bar")
        sb_layout = QVBoxLayout()
        self.show_time_check = QCheckBox("Show Time")
        self.show_time_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_time_check)
        self.show_brightness_check = QCheckBox("Show Brightness")
        self.show_brightness_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_brightness_check)
        self.show_settings_check = QCheckBox("Show Settings")
        self.show_settings_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_settings_check)
        self.show_pc_check = QCheckBox("Show PC Status")
        self.show_pc_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_pc_check)
        self.show_wifi_check = QCheckBox("Show WiFi")
        self.show_wifi_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_wifi_check)
        spacing_row = QHBoxLayout()
        spacing_row.addWidget(QLabel("Icon Spacing:"))
        self.icon_spacing_spin = QSpinBox()
        self.icon_spacing_spin.setRange(2, 20)
        self.icon_spacing_spin.setValue(8)
        self.icon_spacing_spin.setSuffix("px")
        self.icon_spacing_spin.valueChanged.connect(self._on_property_changed)
        spacing_row.addWidget(self.icon_spacing_spin)
        sb_layout.addLayout(spacing_row)
        self.status_bar_group.setLayout(sb_layout)
        self.main_layout.addWidget(self.status_bar_group)

        # Clock group
        self.clock_group = QGroupBox("Clock")
        clock_layout = QVBoxLayout()
        self.clock_analog_check = QCheckBox("Analog clock")
        self.clock_analog_check.stateChanged.connect(self._on_property_changed)
        clock_layout.addWidget(self.clock_analog_check)
        self.clock_group.setLayout(clock_layout)
        self.main_layout.addWidget(self.clock_group)

        # Text Label group
        self.text_group = QGroupBox("Text Label")
        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel("Font Size:"))
        self.font_size_combo = NoScrollComboBox()
        for size in [12, 14, 16, 20, 22, 28, 40]:
            self.font_size_combo.addItem(str(size), size)
        self.font_size_combo.currentIndexChanged.connect(self._on_property_changed)
        text_layout.addWidget(self.font_size_combo)
        text_layout.addWidget(QLabel("Alignment:"))
        self.text_align_combo = NoScrollComboBox()
        self.text_align_combo.addItem("Left", 0)
        self.text_align_combo.addItem("Center", 1)
        self.text_align_combo.addItem("Right", 2)
        self.text_align_combo.currentIndexChanged.connect(self._on_property_changed)
        text_layout.addWidget(self.text_align_combo)
        self.text_group.setLayout(text_layout)
        self.main_layout.addWidget(self.text_group)

        # Separator group
        self.separator_group = QGroupBox("Separator")
        sep_layout = QVBoxLayout()
        self.sep_vertical_check = QCheckBox("Vertical")
        self.sep_vertical_check.stateChanged.connect(self._on_property_changed)
        sep_layout.addWidget(self.sep_vertical_check)
        sep_layout.addWidget(QLabel("Thickness:"))
        self.thickness_spin = QSpinBox()
        self.thickness_spin.setRange(1, 8)
        self.thickness_spin.setValue(2)
        self.thickness_spin.setFocusPolicy(Qt.StrongFocus)
        self.thickness_spin.valueChanged.connect(self._on_property_changed)
        sep_layout.addWidget(self.thickness_spin)
        self.separator_group.setLayout(sep_layout)
        self.main_layout.addWidget(self.separator_group)

        # Hardware Input group (for encoder rotation mode)
        self.hw_encoder_group = QGroupBox("Encoder Rotation")
        enc_layout = QVBoxLayout()
        enc_layout.addWidget(QLabel("Rotation Mode:"))
        self.encoder_mode_combo = NoScrollComboBox()
        for mode_id, mode_name in ENCODER_MODE_NAMES.items():
            self.encoder_mode_combo.addItem(mode_name, mode_id)
        self.encoder_mode_combo.currentIndexChanged.connect(self._on_hw_property_changed)
        enc_layout.addWidget(self.encoder_mode_combo)
        self.encoder_mode_info = QLabel("")
        self.encoder_mode_info.setStyleSheet("color: #888; font-size: 10px;")
        self.encoder_mode_info.setWordWrap(True)
        enc_layout.addWidget(self.encoder_mode_info)

        # Encoder DDC fields (visible when mode == 5)
        self.enc_ddc_vcp_label = QLabel("DDC VCP Code:")
        self.enc_ddc_vcp_label.setVisible(False)
        enc_layout.addWidget(self.enc_ddc_vcp_label)
        self.enc_ddc_vcp_combo = NoScrollComboBox()
        for vcp_code, vcp_name in DDC_VCP_NAMES.items():
            self.enc_ddc_vcp_combo.addItem(vcp_name, vcp_code)
        self.enc_ddc_vcp_combo.setVisible(False)
        self.enc_ddc_vcp_combo.currentIndexChanged.connect(self._on_hw_property_changed)
        enc_layout.addWidget(self.enc_ddc_vcp_combo)

        self.enc_ddc_step_label = QLabel("Step per click:")
        self.enc_ddc_step_label.setVisible(False)
        enc_layout.addWidget(self.enc_ddc_step_label)
        self.enc_ddc_step_spin = QSpinBox()
        self.enc_ddc_step_spin.setRange(1, 50)
        self.enc_ddc_step_spin.setValue(10)
        self.enc_ddc_step_spin.setFocusPolicy(Qt.StrongFocus)
        self.enc_ddc_step_spin.setVisible(False)
        self.enc_ddc_step_spin.valueChanged.connect(self._on_hw_property_changed)
        enc_layout.addWidget(self.enc_ddc_step_spin)

        self.enc_ddc_display_label = QLabel("Display #:")
        self.enc_ddc_display_label.setVisible(False)
        enc_layout.addWidget(self.enc_ddc_display_label)
        self.enc_ddc_display_spin = QSpinBox()
        self.enc_ddc_display_spin.setRange(0, 8)
        self.enc_ddc_display_spin.setSpecialValueText("Auto")
        self.enc_ddc_display_spin.setFocusPolicy(Qt.StrongFocus)
        self.enc_ddc_display_spin.setVisible(False)
        self.enc_ddc_display_spin.valueChanged.connect(self._on_hw_property_changed)
        enc_layout.addWidget(self.enc_ddc_display_spin)

        self.hw_encoder_group.setLayout(enc_layout)
        self.main_layout.addWidget(self.hw_encoder_group)

        # Hardware action group (reuses action type combo for hw buttons/encoder push)
        self.hw_action_group = QGroupBox("Action")
        hw_action_layout = QVBoxLayout()
        hw_action_layout.addWidget(QLabel("Action Type:"))
        self.hw_action_type_combo = NoScrollComboBox()
        for action_id, action_name in ACTION_TYPE_NAMES.items():
            self.hw_action_type_combo.addItem(action_name, action_id)
        self.hw_action_type_combo.currentIndexChanged.connect(self._on_hw_action_type_changed)
        hw_action_layout.addWidget(self.hw_action_type_combo)

        hw_action_layout.addWidget(QLabel("Label:"))
        self.hw_label_input = QLineEdit()
        self.hw_label_input.setMaxLength(32)
        self.hw_label_input.textChanged.connect(self._on_hw_property_changed)
        hw_action_layout.addWidget(self.hw_label_input)

        # Page goto for hardware
        self.hw_page_goto_label = QLabel("Target Page:")
        self.hw_page_goto_label.setVisible(False)
        hw_action_layout.addWidget(self.hw_page_goto_label)
        self.hw_page_goto_spin = QSpinBox()
        self.hw_page_goto_spin.setRange(1, 16)
        self.hw_page_goto_spin.setValue(1)
        self.hw_page_goto_spin.setFocusPolicy(Qt.StrongFocus)
        self.hw_page_goto_spin.setVisible(False)
        self.hw_page_goto_spin.valueChanged.connect(self._on_hw_property_changed)
        hw_action_layout.addWidget(self.hw_page_goto_spin)

        # HW button DDC fields (visible when action_type == ACTION_DDC)
        self.hw_ddc_vcp_label = QLabel("DDC VCP Code:")
        self.hw_ddc_vcp_label.setVisible(False)
        hw_action_layout.addWidget(self.hw_ddc_vcp_label)
        self.hw_ddc_vcp_combo = NoScrollComboBox()
        for vcp_code, vcp_name in DDC_VCP_NAMES.items():
            self.hw_ddc_vcp_combo.addItem(vcp_name, vcp_code)
        self.hw_ddc_vcp_combo.setVisible(False)
        self.hw_ddc_vcp_combo.currentIndexChanged.connect(self._on_hw_property_changed)
        hw_action_layout.addWidget(self.hw_ddc_vcp_combo)

        self.hw_ddc_value_label = QLabel("Value:")
        self.hw_ddc_value_label.setVisible(False)
        hw_action_layout.addWidget(self.hw_ddc_value_label)
        self.hw_ddc_value_spin = QSpinBox()
        self.hw_ddc_value_spin.setRange(0, 65535)
        self.hw_ddc_value_spin.setFocusPolicy(Qt.StrongFocus)
        self.hw_ddc_value_spin.setVisible(False)
        self.hw_ddc_value_spin.valueChanged.connect(self._on_hw_property_changed)
        hw_action_layout.addWidget(self.hw_ddc_value_spin)

        self.hw_ddc_adj_label = QLabel("Adjustment:")
        self.hw_ddc_adj_label.setVisible(False)
        hw_action_layout.addWidget(self.hw_ddc_adj_label)
        self.hw_ddc_adj_spin = QSpinBox()
        self.hw_ddc_adj_spin.setRange(-100, 100)
        self.hw_ddc_adj_spin.setFocusPolicy(Qt.StrongFocus)
        self.hw_ddc_adj_spin.setVisible(False)
        self.hw_ddc_adj_spin.valueChanged.connect(self._on_hw_property_changed)
        hw_action_layout.addWidget(self.hw_ddc_adj_spin)

        self.hw_ddc_display_label = QLabel("Display #:")
        self.hw_ddc_display_label.setVisible(False)
        hw_action_layout.addWidget(self.hw_ddc_display_label)
        self.hw_ddc_display_spin = QSpinBox()
        self.hw_ddc_display_spin.setRange(0, 8)
        self.hw_ddc_display_spin.setSpecialValueText("Auto")
        self.hw_ddc_display_spin.setFocusPolicy(Qt.StrongFocus)
        self.hw_ddc_display_spin.setVisible(False)
        self.hw_ddc_display_spin.valueChanged.connect(self._on_hw_property_changed)
        hw_action_layout.addWidget(self.hw_ddc_display_spin)

        self.hw_action_group.setLayout(hw_action_layout)
        self.main_layout.addWidget(self.hw_action_group)

        self.main_layout.addStretch()
        self.setWidget(container)

        # Hardware input state
        self._hw_mode = False  # True when showing hardware input properties
        self._hw_type = None   # "button" or "encoder"
        self._hw_index = -1
        self._hw_config_manager = None

        # Initially hide all type-specific groups
        self._hide_all_groups()

    def _hide_all_groups(self):
        self.pos_group.setVisible(False)
        self.common_group.setVisible(False)
        self.hotkey_group.setVisible(False)
        self.stat_group.setVisible(False)
        self.status_bar_group.setVisible(False)
        self.clock_group.setVisible(False)
        self.text_group.setVisible(False)
        self.separator_group.setVisible(False)
        self.hw_encoder_group.setVisible(False)
        self.hw_action_group.setVisible(False)

    def clear_selection(self):
        """Clear the properties panel (no widget selected)."""
        self._widget_idx = -1
        self._widget_id = ""
        self._widget_dict = None
        self.type_label.setText("No widget selected")
        self._hide_all_groups()

    def load_widget(self, widget_dict, widget_idx):
        """Load widget data into the properties panel."""
        self._updating = True
        self._widget_dict = widget_dict
        self._widget_idx = widget_idx
        self._widget_id = widget_dict.get("widget_id", "")

        wtype = widget_dict.get("widget_type", WIDGET_HOTKEY_BUTTON)
        type_name = WIDGET_TYPE_NAMES.get(wtype, f"Type {wtype}")
        self.type_label.setText(f"{type_name} (#{widget_idx})")

        # Position
        self.x_spin.setValue(widget_dict.get("x", 0))
        self.y_spin.setValue(widget_dict.get("y", 0))
        self.w_spin.setValue(widget_dict.get("width", 180))
        self.h_spin.setValue(widget_dict.get("height", 100))

        # Common
        self.label_input.setText(widget_dict.get("label", ""))
        self.show_label_cb.setChecked(widget_dict.get("show_label", True))
        self._set_color_btn(self.color_btn, widget_dict.get("color", 0xFFFFFF))
        bg_val = widget_dict.get("bg_color", 0)
        self._set_color_btn(self.bg_color_btn, bg_val)
        self.bg_transparent_cb.setChecked(bg_val == 0)
        self.bg_color_btn.setEnabled(bg_val != 0)

        # Show/hide type-specific groups
        self._hide_all_groups()
        self.pos_group.setVisible(True)
        self.common_group.setVisible(True)

        if wtype == WIDGET_HOTKEY_BUTTON:
            self.hotkey_group.setVisible(True)
            self.description_input.setText(widget_dict.get("description", ""))
            self.show_description_cb.setChecked(widget_dict.get("show_description", True))
            self.icon_picker.set_symbol(widget_dict.get("icon", ""))

            # Restore icon source state
            icon_source = widget_dict.get("icon_source", "")
            icon_source_type = widget_dict.get("icon_source_type", "")
            if icon_source:
                source_path = _resolve_icon_source(widget_dict)
                if source_path:
                    display_name = os.path.basename(source_path) if icon_source_type == "file" else icon_source
                    self.icon_image_label.setText(display_name)
                    self.icon_image_clear_btn.setVisible(True)
                    # Show preview thumbnail
                    pixmap = _load_icon_pixmap(source_path, 64, 64)
                    if pixmap:
                        self.icon_image_preview.setPixmap(
                            pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        )
                        self.icon_image_preview.setVisible(True)
                    else:
                        self.icon_image_preview.setVisible(False)
                else:
                    self.icon_image_label.setText(f"{icon_source} (not found)")
                    self.icon_image_clear_btn.setVisible(True)
                    self.icon_image_preview.setVisible(False)
            else:
                self.icon_image_label.setText("")
                self.icon_image_clear_btn.setVisible(False)
                self.icon_image_preview.setVisible(False)
                self.icon_image_preview.clear()

            action_type = widget_dict.get("action_type", ACTION_HOTKEY)
            # Find correct index by matching itemData
            for i in range(self.action_type_combo.count()):
                if self.action_type_combo.itemData(i) == action_type:
                    self.action_type_combo.setCurrentIndex(i)
                    break
            self._update_action_visibility(action_type)
            self.keyboard_recorder.set_shortcut(
                widget_dict.get("modifiers", 0), widget_dict.get("keycode", 0)
            )
            self._set_media_key_combo(widget_dict.get("consumer_code", 0))

            # Load launch app fields
            launch_cmd = widget_dict.get("launch_command", "")
            self.launch_cmd_input.setText(launch_cmd)
            self.launch_wm_class_input.setText(widget_dict.get("launch_wm_class", ""))
            self.focus_or_launch_check.setChecked(widget_dict.get("launch_focus_or_launch", True))
            # Detect Steam game from launch command
            is_steam = "steam://rungameid/" in launch_cmd
            self.steam_game_check.setChecked(is_steam)
            if is_steam:
                appid = launch_cmd.split("rungameid/")[-1].strip()
                self.steam_appid_input.setText(appid)

            # Load shell command
            self.shell_cmd_input.setText(widget_dict.get("shell_command", ""))

            # Load URL
            self.url_input.setText(widget_dict.get("url", ""))

            # Load DDC fields
            if action_type == ACTION_DDC:
                vcp = widget_dict.get("ddc_vcp_code", 0x10)
                for i in range(self.ddc_vcp_combo.count()):
                    if self.ddc_vcp_combo.itemData(i) == vcp:
                        self.ddc_vcp_combo.setCurrentIndex(i)
                        break
                self.ddc_value_spin.setValue(widget_dict.get("ddc_value", 0))
                self.ddc_adjustment_spin.setValue(widget_dict.get("ddc_adjustment", 0))
                self.ddc_display_spin.setValue(widget_dict.get("ddc_display", 0))

            pressed = widget_dict.get("pressed_color", 0)
            self.auto_darken_check.setChecked(pressed == 0)
            self.pressed_color_btn.setVisible(pressed != 0)
            if pressed != 0:
                self._set_color_btn(self.pressed_color_btn, pressed)

        elif wtype == WIDGET_STAT_MONITOR:
            self.stat_group.setVisible(True)
            st = widget_dict.get("stat_type", 0x01)
            for i in range(self.stat_type_combo.count()):
                if self.stat_type_combo.itemData(i) == st:
                    self.stat_type_combo.setCurrentIndex(i)
                    break
            vp = widget_dict.get("value_position", 0)
            self.value_position_combo.setCurrentIndex(min(vp, 2))

        elif wtype == WIDGET_STATUS_BAR:
            self.status_bar_group.setVisible(True)
            self.show_wifi_check.setChecked(widget_dict.get("show_wifi", True))
            self.show_pc_check.setChecked(widget_dict.get("show_pc", True))
            self.show_settings_check.setChecked(widget_dict.get("show_settings", True))
            self.show_brightness_check.setChecked(widget_dict.get("show_brightness", True))
            self.show_time_check.setChecked(widget_dict.get("show_time", True))
            self.icon_spacing_spin.setValue(widget_dict.get("icon_spacing", 8))

        elif wtype == WIDGET_CLOCK:
            self.clock_group.setVisible(True)
            self.clock_analog_check.setChecked(widget_dict.get("clock_analog", False))

        elif wtype == WIDGET_TEXT_LABEL:
            self.text_group.setVisible(True)
            fs = widget_dict.get("font_size", 16)
            for i in range(self.font_size_combo.count()):
                if self.font_size_combo.itemData(i) == fs:
                    self.font_size_combo.setCurrentIndex(i)
                    break
            ta = widget_dict.get("text_align", 1)
            self.text_align_combo.setCurrentIndex(ta)

        elif wtype == WIDGET_SEPARATOR:
            self.separator_group.setVisible(True)
            self.sep_vertical_check.setChecked(widget_dict.get("separator_vertical", False))
            self.thickness_spin.setValue(widget_dict.get("thickness", 2))

        self._hw_mode = False
        self._updating = False

    def load_hardware_input(self, config_manager, hw_type, index):
        """Load hardware button or encoder properties into the panel."""
        self._updating = True
        self._hw_mode = True
        self._hw_type = hw_type
        self._hw_index = index
        self._hw_config_manager = config_manager
        self._widget_dict = None
        self._widget_idx = -1
        self._widget_id = ""

        self._hide_all_groups()

        if hw_type == "button":
            buttons = config_manager.config.get("hardware_buttons", get_default_hardware_buttons())
            if index < len(buttons):
                btn_cfg = buttons[index]
            else:
                btn_cfg = get_default_hardware_buttons()[0]

            self.type_label.setText(f"Hardware Button {index + 1}")
            self.hw_action_group.setVisible(True)

            # Set action type
            action_type = btn_cfg.get("action_type", ACTION_PAGE_NEXT)
            for i in range(self.hw_action_type_combo.count()):
                if self.hw_action_type_combo.itemData(i) == action_type:
                    self.hw_action_type_combo.setCurrentIndex(i)
                    break
            self._update_hw_action_visibility(action_type)

            # Set label
            self.hw_label_input.setText(btn_cfg.get("label", ""))

            # Page goto
            self.hw_page_goto_spin.setValue(btn_cfg.get("keycode", 0) + 1)

            # DDC fields for hw button
            if action_type == ACTION_DDC:
                vcp = btn_cfg.get("ddc_vcp_code", 0x10)
                for i in range(self.hw_ddc_vcp_combo.count()):
                    if self.hw_ddc_vcp_combo.itemData(i) == vcp:
                        self.hw_ddc_vcp_combo.setCurrentIndex(i)
                        break
                self.hw_ddc_value_spin.setValue(btn_cfg.get("ddc_value", 0))
                self.hw_ddc_adj_spin.setValue(btn_cfg.get("ddc_adjustment", 0))
                self.hw_ddc_display_spin.setValue(btn_cfg.get("ddc_display", 0))

        elif hw_type == "encoder":
            encoder = config_manager.config.get("encoder", get_default_encoder())

            self.type_label.setText("Rotary Encoder")
            self.hw_action_group.setVisible(True)
            self.hw_encoder_group.setVisible(True)

            # Set push action type
            push_action = encoder.get("push_action", ACTION_BRIGHTNESS)
            for i in range(self.hw_action_type_combo.count()):
                if self.hw_action_type_combo.itemData(i) == push_action:
                    self.hw_action_type_combo.setCurrentIndex(i)
                    break
            self._update_hw_action_visibility(push_action)

            # Set push label
            self.hw_label_input.setText(encoder.get("push_label", ""))

            # Set encoder mode
            enc_mode = encoder.get("encoder_mode", 0)
            for i in range(self.encoder_mode_combo.count()):
                if self.encoder_mode_combo.itemData(i) == enc_mode:
                    self.encoder_mode_combo.setCurrentIndex(i)
                    break
            self._update_encoder_mode_info(enc_mode)

            # Page goto
            self.hw_page_goto_spin.setValue(encoder.get("push_keycode", 0) + 1)

            # Encoder DDC fields
            enc_mode = encoder.get("encoder_mode", 0)
            if enc_mode == 5:
                vcp = encoder.get("ddc_vcp_code", 0x10)
                for i in range(self.enc_ddc_vcp_combo.count()):
                    if self.enc_ddc_vcp_combo.itemData(i) == vcp:
                        self.enc_ddc_vcp_combo.setCurrentIndex(i)
                        break
                self.enc_ddc_step_spin.setValue(encoder.get("ddc_step", 10))
                self.enc_ddc_display_spin.setValue(encoder.get("ddc_display", 0))

        self._updating = False

    def _update_hw_action_visibility(self, action_type):
        """Show/hide hardware action fields based on action type."""
        is_goto = (action_type == ACTION_PAGE_GOTO)
        self.hw_page_goto_label.setVisible(is_goto)
        self.hw_page_goto_spin.setVisible(is_goto)

        is_ddc = (action_type == ACTION_DDC)
        self.hw_ddc_vcp_label.setVisible(is_ddc)
        self.hw_ddc_vcp_combo.setVisible(is_ddc)
        self.hw_ddc_value_label.setVisible(is_ddc)
        self.hw_ddc_value_spin.setVisible(is_ddc)
        self.hw_ddc_adj_label.setVisible(is_ddc)
        self.hw_ddc_adj_spin.setVisible(is_ddc)
        self.hw_ddc_display_label.setVisible(is_ddc)
        self.hw_ddc_display_spin.setVisible(is_ddc)

    def _update_encoder_mode_info(self, mode):
        """Show informational text about what encoder rotation does in each mode."""
        info_texts = {
            0: "CW: Next page, CCW: Previous page",
            1: "CW: Volume up, CCW: Volume down",
            2: "CW: Brighter, CCW: Dimmer",
            3: "CW: Next widget, CCW: Previous widget, Push: Activate",
            4: "CW: Next mode, CCW: Previous mode",
            5: "CW: DDC value +step, CCW: DDC value -step",
        }
        self.encoder_mode_info.setText(info_texts.get(mode, ""))

        # Show/hide encoder DDC fields
        is_ddc_mode = (mode == 5)
        self.enc_ddc_vcp_label.setVisible(is_ddc_mode)
        self.enc_ddc_vcp_combo.setVisible(is_ddc_mode)
        self.enc_ddc_step_label.setVisible(is_ddc_mode)
        self.enc_ddc_step_spin.setVisible(is_ddc_mode)
        self.enc_ddc_display_label.setVisible(is_ddc_mode)
        self.enc_ddc_display_spin.setVisible(is_ddc_mode)

    def _on_hw_action_type_changed(self):
        action_type = self.hw_action_type_combo.currentData()
        self._update_hw_action_visibility(action_type)
        if not self._updating:
            self._save_hw_config()

    def _on_hw_property_changed(self, *args):
        if not self._updating:
            self._save_hw_config()
            # Update encoder mode info
            if self._hw_type == "encoder":
                mode = self.encoder_mode_combo.currentData()
                if mode is not None:
                    self._update_encoder_mode_info(mode)

    def _save_hw_config(self):
        """Write hardware input changes back to config dict."""
        if not self._hw_mode or self._hw_config_manager is None:
            return

        if self._hw_type == "button":
            buttons = self._hw_config_manager.config.get("hardware_buttons", get_default_hardware_buttons())
            if self._hw_index < len(buttons):
                btn = buttons[self._hw_index]
                btn["action_type"] = self.hw_action_type_combo.currentData() or ACTION_PAGE_NEXT
                btn["label"] = self.hw_label_input.text()
                if btn["action_type"] == ACTION_PAGE_GOTO:
                    btn["keycode"] = self.hw_page_goto_spin.value() - 1
                if btn["action_type"] == ACTION_DDC:
                    btn["ddc_vcp_code"] = self.hw_ddc_vcp_combo.currentData() or 0x10
                    btn["ddc_value"] = self.hw_ddc_value_spin.value()
                    btn["ddc_adjustment"] = self.hw_ddc_adj_spin.value()
                    btn["ddc_display"] = self.hw_ddc_display_spin.value()
                self._hw_config_manager.config["hardware_buttons"] = buttons

        elif self._hw_type == "encoder":
            encoder = self._hw_config_manager.config.get("encoder", get_default_encoder())
            encoder["push_action"] = self.hw_action_type_combo.currentData() or ACTION_BRIGHTNESS
            encoder["push_label"] = self.hw_label_input.text()
            encoder["encoder_mode"] = self.encoder_mode_combo.currentData() or 0
            if encoder["push_action"] == ACTION_PAGE_GOTO:
                encoder["push_keycode"] = self.hw_page_goto_spin.value() - 1
            if encoder["encoder_mode"] == 5:
                encoder["ddc_vcp_code"] = self.enc_ddc_vcp_combo.currentData() or 0x10
                encoder["ddc_step"] = self.enc_ddc_step_spin.value()
                encoder["ddc_display"] = self.enc_ddc_display_spin.value()
            self._hw_config_manager.config["encoder"] = encoder

        self._hw_config_manager._emit_changed()
        self.hw_config_updated.emit()

    def update_position(self, x, y, w, h):
        """Update position spinboxes without triggering property changed."""
        self._updating = True
        self.x_spin.setValue(x)
        self.y_spin.setValue(y)
        self.w_spin.setValue(w)
        self.h_spin.setValue(h)
        self._updating = False

    def _get_widget_dict(self):
        """Build widget dict from current panel state."""
        if self._widget_dict is None:
            return None

        d = dict(self._widget_dict)
        d["x"] = self.x_spin.value()
        d["y"] = self.y_spin.value()
        d["width"] = self.w_spin.value()
        d["height"] = self.h_spin.value()
        d["label"] = self.label_input.text()
        d["show_label"] = self.show_label_cb.isChecked()
        d["color"] = self.color_btn.property("color_value") or 0xFFFFFF
        d["bg_color"] = 0 if self.bg_transparent_cb.isChecked() else (self.bg_color_btn.property("color_value") or 0)

        wtype = d.get("widget_type", WIDGET_HOTKEY_BUTTON)

        if wtype == WIDGET_HOTKEY_BUTTON:
            d["description"] = self.description_input.text()
            d["show_description"] = self.show_description_cb.isChecked()
            d["icon"] = self.icon_picker.get_symbol()
            # icon_source and icon_source_type are already in the widget dict
            # (set by _on_app_selected or _on_icon_image_browse)
            action_type = self.action_type_combo.currentData()
            d["action_type"] = action_type
            if action_type == ACTION_MEDIA_KEY:
                d["consumer_code"] = self.media_key_combo.currentData() or 0
                d["modifiers"] = 0
                d["keycode"] = 0
            elif action_type == ACTION_HOTKEY:
                d["consumer_code"] = 0
                d["modifiers"] = self.keyboard_recorder.current_modifiers
                d["keycode"] = self.keyboard_recorder.current_keycode
            elif action_type == ACTION_DDC:
                d["consumer_code"] = 0
                d["modifiers"] = 0
                d["keycode"] = 0
                d["ddc_vcp_code"] = self.ddc_vcp_combo.currentData() or 0x10
                d["ddc_value"] = self.ddc_value_spin.value()
                d["ddc_adjustment"] = self.ddc_adjustment_spin.value()
                d["ddc_display"] = self.ddc_display_spin.value()
            else:
                d["consumer_code"] = 0
                d["modifiers"] = 0
                d["keycode"] = 0

            # Always include all action-type fields
            d["launch_command"] = self.launch_cmd_input.text()
            d["launch_wm_class"] = self.launch_wm_class_input.text()
            d["launch_focus_or_launch"] = self.focus_or_launch_check.isChecked()
            d["shell_command"] = self.shell_cmd_input.text()
            d["url"] = self.url_input.text()

            d["pressed_color"] = 0 if self.auto_darken_check.isChecked() else (
                self.pressed_color_btn.property("color_value") or 0xFF0000
            )

        elif wtype == WIDGET_STAT_MONITOR:
            d["stat_type"] = self.stat_type_combo.currentData() or 0x01
            d["value_position"] = self.value_position_combo.currentData() or 0

        elif wtype == WIDGET_STATUS_BAR:
            d["show_wifi"] = self.show_wifi_check.isChecked()
            d["show_pc"] = self.show_pc_check.isChecked()
            d["show_settings"] = self.show_settings_check.isChecked()
            d["show_brightness"] = self.show_brightness_check.isChecked()
            d["show_time"] = self.show_time_check.isChecked()
            d["icon_spacing"] = self.icon_spacing_spin.value()

        elif wtype == WIDGET_CLOCK:
            d["clock_analog"] = self.clock_analog_check.isChecked()

        elif wtype == WIDGET_TEXT_LABEL:
            d["font_size"] = self.font_size_combo.currentData() or 16
            d["text_align"] = self.text_align_combo.currentData()

        elif wtype == WIDGET_SEPARATOR:
            d["separator_vertical"] = self.sep_vertical_check.isChecked()
            d["thickness"] = self.thickness_spin.value()

        return d

    def _on_position_changed(self):
        if not self._updating:
            self._emit_update()

    def _on_property_changed(self, *args):
        if not self._updating:
            self._emit_update()

    def _on_stat_type_changed(self, *args):
        """When stat type changes, auto-update label to match the stat name."""
        if not self._updating:
            stat_id = self.stat_type_combo.currentData()
            if stat_id is not None:
                new_label = STAT_TYPE_NAMES.get(stat_id, "Stat")
                # Only auto-set if label is empty or matches a known stat name
                current = self.label_input.text().strip()
                if not current or current in STAT_TYPE_NAMES.values():
                    self._updating = True
                    self.label_input.setText(new_label)
                    self._updating = False
            self._emit_update()

    def _on_action_type_changed(self):
        action_type = self.action_type_combo.currentData()
        self._update_action_visibility(action_type)
        if not self._updating:
            self._emit_update()

    def _update_action_visibility(self, action_type):
        """Show/hide action-specific widgets based on selected action type."""
        # Shortcut section
        is_hotkey = (action_type == ACTION_HOTKEY)
        self.keyboard_recorder.setVisible(is_hotkey)
        self.shortcut_label.setVisible(is_hotkey)

        # Media key section
        is_media = (action_type == ACTION_MEDIA_KEY)
        self.media_key_combo.setVisible(is_media)
        self.media_key_label.setVisible(is_media)

        # Launch app section
        is_launch = (action_type == ACTION_LAUNCH_APP)
        self.launch_app_label.setVisible(is_launch)
        self.app_picker_combo.setVisible(is_launch)
        self.launch_cmd_label.setVisible(is_launch)
        self.launch_cmd_input.setVisible(is_launch)
        self.launch_wm_class_label.setVisible(is_launch)
        self.launch_wm_class_input.setVisible(is_launch)
        self.focus_or_launch_check.setVisible(is_launch)
        self.steam_game_check.setVisible(is_launch)
        is_steam = is_launch and self.steam_game_check.isChecked()
        self.steam_appid_label.setVisible(is_steam)
        self.steam_appid_input.setVisible(is_steam)
        if is_launch:
            self._ensure_apps_loaded()

        # Shell command section
        is_shell = (action_type == ACTION_SHELL_CMD)
        self.shell_cmd_label.setVisible(is_shell)
        self.shell_cmd_input.setVisible(is_shell)

        # URL section
        is_url = (action_type == ACTION_OPEN_URL)
        self.url_label.setVisible(is_url)
        self.url_input.setVisible(is_url)

        # Page goto section
        is_goto = (action_type == ACTION_PAGE_GOTO)
        self.page_goto_label.setVisible(is_goto)
        self.page_goto_spin.setVisible(is_goto)

        # DDC section
        is_ddc = (action_type == ACTION_DDC)
        self.ddc_section_label.setVisible(is_ddc)
        self.ddc_vcp_combo.setVisible(is_ddc)
        self.ddc_value_spin.setVisible(is_ddc)
        self.ddc_adjustment_spin.setVisible(is_ddc)
        self.ddc_display_spin.setVisible(is_ddc)
        self.ddc_info_label.setVisible(is_ddc)

    def _ensure_apps_loaded(self):
        """Lazy-load applications list into app_picker_combo."""
        if self._apps_loaded:
            return
        self._apps_loaded = True
        self.app_picker_combo.clear()
        self.app_picker_combo.addItem("(Custom)", None)
        try:
            from companion.app_scanner import scan_applications
            apps = scan_applications()
            for app in apps:
                self.app_picker_combo.addItem(app.name, app)
        except Exception:
            pass

    def _on_app_picker_changed(self, index):
        """App picker dropdown changed -- auto-fill ALL fields from app."""
        if self._updating:
            return
        app = self.app_picker_combo.currentData()
        if app is None:
            return
        self._updating = True

        # Label & description
        self.label_input.setText(app.name[:20])
        desc = app.comment[:32] if app.comment else ""
        self.description_input.setText(desc)

        # Launch command & WM_CLASS
        self.launch_cmd_input.setText(app.exec_cmd)
        wm_class = app.wm_class if app.wm_class else app.name
        self.launch_wm_class_input.setText(wm_class)

        # Icon from freedesktop theme — clear symbol icon since image takes over
        if app.icon_name and self._widget_dict is not None:
            self.icon_picker.set_symbol("")
            self._widget_dict["icon_source"] = app.icon_name
            self._widget_dict["icon_source_type"] = "freedesktop"
            self.icon_image_label.setText(app.icon_name)
            self.icon_image_clear_btn.setVisible(True)
            source_path = _resolve_icon_source(self._widget_dict)
            if source_path:
                pixmap = _load_icon_pixmap(source_path, 64, 64)
                if pixmap:
                    self.icon_image_preview.setPixmap(
                        pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                    self.icon_image_preview.setVisible(True)
                else:
                    self.icon_image_preview.setVisible(False)
            else:
                self.icon_image_preview.setVisible(False)

        self._updating = False
        self._emit_update()

    def _on_steam_game_toggled(self, state):
        """Toggle Steam Game mode — show/hide app ID input."""
        is_steam = bool(state)
        self.steam_appid_label.setVisible(is_steam)
        self.steam_appid_input.setVisible(is_steam)
        if is_steam:
            # Hide the regular app picker when in Steam mode
            self.launch_app_label.setVisible(False)
            self.app_picker_combo.setVisible(False)
            # Pre-fill app ID from existing launch command if possible
            cmd = self.launch_cmd_input.text()
            if "rungameid/" in cmd:
                appid = cmd.split("rungameid/")[-1].strip()
                self.steam_appid_input.setText(appid)
        else:
            self.launch_app_label.setVisible(True)
            self.app_picker_combo.setVisible(True)

    def _on_steam_appid_changed(self, text):
        """Auto-fill launch command and icon from Steam App ID."""
        if self._updating:
            return
        appid = text.strip()
        if not appid.isdigit():
            return
        self._updating = True
        self.launch_cmd_input.setText(f"steam steam://rungameid/{appid}")
        self.launch_wm_class_input.setText("steam")
        # Set Steam icon
        icon_name = f"steam_icon_{appid}"
        if self._widget_dict is not None:
            self.icon_picker.set_symbol("")
            self._widget_dict["icon_source"] = icon_name
            self._widget_dict["icon_source_type"] = "freedesktop"
            self.icon_image_label.setText(icon_name)
            self.icon_image_clear_btn.setVisible(True)
            source_path = _resolve_icon_source(self._widget_dict)
            if source_path:
                pixmap = _load_icon_pixmap(source_path, 64, 64)
                if pixmap:
                    self.icon_image_preview.setPixmap(
                        pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                    self.icon_image_preview.setVisible(True)
                else:
                    self.icon_image_preview.setVisible(False)
            else:
                self.icon_image_preview.setVisible(False)
        self._updating = False
        self._emit_update()

    def _on_icon_image_browse(self):
        """Open file dialog to pick an icon image file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg)"
        )
        if not path:
            return

        self._widget_dict["icon_source"] = path
        self._widget_dict["icon_source_type"] = "file"

        self.icon_image_label.setText(os.path.basename(path))
        self.icon_image_clear_btn.setVisible(True)

        # Show preview thumbnail
        pixmap = _load_icon_pixmap(path, 64, 64)
        if pixmap:
            self.icon_image_preview.setPixmap(
                pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.icon_image_preview.setVisible(True)
        else:
            self.icon_image_preview.setVisible(False)

        if not self._updating:
            self._emit_update()

    def _on_icon_image_clear(self):
        """Clear selected icon image, revert to symbol."""
        self._widget_dict["icon_source"] = ""
        self._widget_dict["icon_source_type"] = ""
        self.icon_image_label.setText("")
        self.icon_image_clear_btn.setVisible(False)
        self.icon_image_preview.setVisible(False)
        self.icon_image_preview.clear()
        if not self._updating:
            self._emit_update()

    def _on_auto_darken_changed(self):
        is_auto = self.auto_darken_check.isChecked()
        self.pressed_color_btn.setVisible(not is_auto)
        if not self._updating:
            self._emit_update()

    def _on_color_clicked(self):
        current = self.color_btn.property("color_value") or 0xFFFFFF
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Widget Color")
        if new_color.isValid():
            self._set_color_btn(self.color_btn, _qcolor_to_int(new_color))
            if not self._updating:
                self._emit_update()

    def _on_bg_color_clicked(self):
        current = self.bg_color_btn.property("color_value") or 0
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Background Color")
        if new_color.isValid():
            self._set_color_btn(self.bg_color_btn, _qcolor_to_int(new_color))
            if not self._updating:
                self._emit_update()

    def _on_bg_transparent_changed(self, state):
        checked = state == Qt.Checked.value if hasattr(Qt.Checked, 'value') else state == 2
        self.bg_color_btn.setEnabled(not checked)
        if checked:
            self._set_color_btn(self.bg_color_btn, 0)
        if not self._updating:
            self._emit_update()

    def _on_pressed_color_clicked(self):
        current = self.pressed_color_btn.property("color_value") or 0xFF0000
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Pressed Color")
        if new_color.isValid():
            self._set_color_btn(self.pressed_color_btn, _qcolor_to_int(new_color))
            if not self._updating:
                self._emit_update()

    def _set_color_btn(self, btn, color_val):
        qc = _int_to_qcolor(color_val)
        btn.setStyleSheet(f"background-color: {qc.name()}; border: 1px solid #555;")
        btn.setProperty("color_value", color_val)

    def _set_media_key_combo(self, consumer_code):
        for i in range(self.media_key_combo.count()):
            if self.media_key_combo.itemData(i) == consumer_code:
                self.media_key_combo.setCurrentIndex(i)
                return
        if self.media_key_combo.count() > 0:
            self.media_key_combo.setCurrentIndex(0)

    def _emit_update(self):
        if self._widget_id:
            d = self._get_widget_dict()
            if d is not None:
                self.widget_updated.emit(self._widget_id, d)


# ============================================================
# Settings Tab (replaces canvas when Settings page is active)
