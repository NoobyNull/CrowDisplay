"""
Canvas Items: CanvasWidgetItem and ResizeHandle for the WYSIWYG editor canvas.
"""

import os
import logging

from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPixmap, QPainter

from companion.config_manager import (
    WIDGET_HOTKEY_BUTTON,
    WIDGET_STAT_MONITOR,
    WIDGET_STATUS_BAR,
    WIDGET_CLOCK,
    WIDGET_TEXT_LABEL,
    WIDGET_SEPARATOR,
    WIDGET_PAGE_NAV,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    SNAP_GRID,
    WIDGET_MIN_W,
    WIDGET_MIN_H,
)
from companion.ui.editor_utils import (
    _int_to_qcolor,
    _resolve_icon_source,
    _load_icon_pixmap,
    _get_fa_font_family,
)
from companion.ui.editor_constants import (
    STAT_PLACEHOLDERS,
    STAT_VALUE_PLACEHOLDERS,
    STAT_NAME_LABELS,
)
from companion.lvgl_symbols import SYMBOL_BY_UTF8

logger = logging.getLogger(__name__)


# ============================================================
# Canvas Widget Item -- represents a widget on the 800x480 canvas
# ============================================================

class CanvasWidgetItem(QGraphicsRectItem):
    """A widget item on the canvas. Movable, selectable, snaps to grid."""

    def __init__(self, widget_dict, widget_idx):
        self._w = max(WIDGET_MIN_W, widget_dict.get("width", 180))
        self._h = max(WIDGET_MIN_H, widget_dict.get("height", 100))
        super().__init__(0, 0, self._w, self._h)

        self.widget_dict = widget_dict
        self.widget_idx = widget_idx
        self.widget_id = widget_dict.get("widget_id", "")
        self._suppress_notify = True
        self._icon_pixmap = None  # QPixmap cache for icon image

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        x = widget_dict.get("x", 0)
        y = widget_dict.get("y", 0)
        self.setPos(x, y)
        self._suppress_notify = False

        self._update_appearance()

    def set_size(self, w, h):
        """Set widget size (called during resize)."""
        w = max(WIDGET_MIN_W, int(w))
        h = max(WIDGET_MIN_H, int(h))
        self._w = w
        self._h = h
        self.setRect(0, 0, w, h)
        self._update_appearance()

    def set_icon_pixmap(self, pixmap):
        """Set a QPixmap to render as the button icon image."""
        self._icon_pixmap = pixmap
        self.update()

    def resolve_icon(self):
        """Resolve icon_source to a pixmap and cache it."""
        source_path = _resolve_icon_source(self.widget_dict)
        if source_path:
            pixmap = _load_icon_pixmap(source_path, self._w, self._h)
            self._icon_pixmap = pixmap
        else:
            self._icon_pixmap = None

    def update_from_dict(self, widget_dict):
        """Update appearance from widget dict (called when properties change)."""
        self._suppress_notify = True
        self.widget_dict = widget_dict
        x = widget_dict.get("x", 0)
        y = widget_dict.get("y", 0)
        w = max(WIDGET_MIN_W, widget_dict.get("width", 180))
        h = max(WIDGET_MIN_H, widget_dict.get("height", 100))
        self.setPos(x, y)
        self._w = w
        self._h = h
        self.setRect(0, 0, w, h)
        self._update_appearance()
        self._suppress_notify = False

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # Snap to grid and clamp to display bounds
            x = round(value.x() / SNAP_GRID) * SNAP_GRID
            y = round(value.y() / SNAP_GRID) * SNAP_GRID
            x = max(0, min(DISPLAY_WIDTH - self._w, x))
            y = max(0, min(DISPLAY_HEIGHT - self._h, y))
            new_pos = QPointF(x, y)

            # Multi-select group move: apply the same delta to other selected items
            if not self._suppress_notify and self.isSelected():
                dx = new_pos.x() - self.pos().x()
                dy = new_pos.y() - self.pos().y()
                if (dx != 0 or dy != 0) and self.scene():
                    for other in self.scene().selectedItems():
                        if other is not self and isinstance(other, CanvasWidgetItem):
                            ox = other.pos().x() + dx
                            oy = other.pos().y() + dy
                            ox = max(0, min(DISPLAY_WIDTH - other._w, round(ox / SNAP_GRID) * SNAP_GRID))
                            oy = max(0, min(DISPLAY_HEIGHT - other._h, round(oy / SNAP_GRID) * SNAP_GRID))
                            other._suppress_notify = True
                            other.setPos(ox, oy)
                            other._suppress_notify = False
                            if hasattr(self.scene(), "on_widget_moved"):
                                self.scene().on_widget_moved(other)

            return new_pos
        if change == QGraphicsItem.ItemPositionHasChanged and not self._suppress_notify:
            scene = self.scene()
            if scene and hasattr(scene, "on_widget_moved"):
                scene.on_widget_moved(self)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            scene = self.scene()
            if scene and hasattr(scene, "on_selection_changed"):
                scene.on_selection_changed()
        return super().itemChange(change, value)

    def _update_appearance(self):
        """Update pen/brush based on widget type."""
        wtype = self.widget_dict.get("widget_type", WIDGET_HOTKEY_BUTTON)
        color = self.widget_dict.get("color", 0xFFFFFF)
        bg_color = self.widget_dict.get("bg_color", 0)
        qcolor = _int_to_qcolor(color)

        if wtype == WIDGET_HOTKEY_BUTTON:
            if bg_color:
                bg_qcolor = _int_to_qcolor(bg_color)
                self.setBrush(QBrush(bg_qcolor))
                self.setPen(QPen(bg_qcolor.darker(130), 2))
            else:
                self.setBrush(QBrush(QColor(0, 0, 0, 0)))
                self.setPen(QPen(QColor("#555"), 1, Qt.DashLine))
        elif wtype == WIDGET_STATUS_BAR:
            bg = _int_to_qcolor(bg_color) if bg_color else QColor("#16213e")
            self.setBrush(QBrush(bg))
            self.setPen(QPen(bg.lighter(130), 1))
        elif wtype == WIDGET_STAT_MONITOR:
            self.setBrush(QBrush(QColor("#1a1f2e")))
            self.setPen(QPen(qcolor, 2))
        elif wtype == WIDGET_CLOCK:
            self.setBrush(QBrush(QColor("#0d1117")))
            self.setPen(QPen(qcolor, 2))
        elif wtype == WIDGET_TEXT_LABEL:
            self.setBrush(QBrush(QColor(0, 0, 0, 0)))
            self.setPen(QPen(QColor("#333"), 1, Qt.DashLine))
        elif wtype == WIDGET_SEPARATOR:
            self.setBrush(QBrush(qcolor))
            self.setPen(QPen(qcolor, 1))
        elif wtype == WIDGET_PAGE_NAV:
            self.setBrush(QBrush(QColor(0, 0, 0, 40)))
            self.setPen(QPen(QColor("#555"), 1, Qt.DashLine))
        else:
            self.setBrush(QBrush(QColor("#333")))
            self.setPen(QPen(QColor("#666"), 1))

    def paint(self, painter, option, widget=None):
        # Draw base rectangle
        super().paint(painter, option, widget)

        wtype = self.widget_dict.get("widget_type", WIDGET_HOTKEY_BUTTON)
        rect = self.rect()
        color = self.widget_dict.get("color", 0xFFFFFF)
        qcolor = _int_to_qcolor(color)

        if wtype == WIDGET_HOTKEY_BUTTON:
            self._paint_hotkey_button(painter, rect, qcolor)
        elif wtype == WIDGET_STAT_MONITOR:
            self._paint_stat_monitor(painter, rect, qcolor)
        elif wtype == WIDGET_STATUS_BAR:
            self._paint_status_bar(painter, rect, qcolor)
        elif wtype == WIDGET_CLOCK:
            self._paint_clock(painter, rect, qcolor)
        elif wtype == WIDGET_TEXT_LABEL:
            self._paint_text_label(painter, rect, qcolor)
        elif wtype == WIDGET_SEPARATOR:
            self._paint_separator(painter, rect, qcolor)
        elif wtype == WIDGET_PAGE_NAV:
            self._paint_page_nav(painter, rect, qcolor)

        # Selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor("#FFD700"), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(-1, -1, 1, 1))

        # Overlap warning: red outline if colliding with another widget
        if self.scene():
            colliders = [
                c for c in self.collidingItems()
                if isinstance(c, CanvasWidgetItem)
            ]
            if colliders:
                painter.setPen(QPen(QColor("#FF4444"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))

    def _paint_hotkey_button(self, painter, rect, qcolor):
        text_color = qcolor  # color field is now the text/foreground color

        label = self.widget_dict.get("label", "") if self.widget_dict.get("show_label", True) else ""

        # If we have an icon pixmap (from image picker), draw it
        if self._icon_pixmap and not self._icon_pixmap.isNull():
            if label:
                # Image on top, label below — reserve space for label then fill rest
                label_h = max(16, int(rect.height() * 0.15))
                icon_w = max(16, int(rect.width() * 0.8))
                icon_h = max(16, int(rect.height() - label_h - 8))
                scaled = self._icon_pixmap.scaled(
                    icon_w, icon_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                img_x = rect.center().x() - scaled.width() / 2
                img_y = rect.top() + 4
                painter.drawPixmap(int(img_x), int(img_y), scaled)
                painter.setPen(text_color)
                font_size = max(8, min(12, int(rect.height() * 0.05)))
                painter.setFont(QFont("Arial", font_size))
                label_rect = QRectF(rect.left(), img_y + scaled.height() + 2,
                                    rect.width(), rect.bottom() - (img_y + scaled.height() + 2))
                painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, label)
            else:
                # Icon-only — use 80% of available space
                icon_w = max(16, int(rect.width() * 0.8))
                icon_h = max(16, int(rect.height() * 0.8))
                scaled = self._icon_pixmap.scaled(
                    icon_w, icon_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                img_x = rect.center().x() - scaled.width() / 2
                img_y = rect.center().y() - scaled.height() / 2
                painter.drawPixmap(int(img_x), int(img_y), scaled)
            return

        # Fall back to symbol icon — render as FontAwesome glyph if available
        icon = self.widget_dict.get("icon", "")
        icon_glyph = ""   # The actual unicode character for FontAwesome rendering
        icon_name = ""    # Fallback text name if FA font not available
        if icon:
            icon_bytes = icon.encode("utf-8")
            if icon_bytes in SYMBOL_BY_UTF8:
                icon_name = SYMBOL_BY_UTF8[icon_bytes][0]
                icon_glyph = icon  # The raw unicode char (e.g., \uf04b)
            else:
                icon_name = "?"

        fa_family = _get_fa_font_family()
        painter.setPen(text_color)
        if (icon_glyph or icon_name) and label:
            icon_size = max(9, int(min(rect.width(), rect.height()) * 0.3))
            if fa_family and icon_glyph:
                painter.setFont(QFont(fa_family, icon_size))
                painter.drawText(rect.adjusted(4, 2, -4, -rect.height() / 3), Qt.AlignCenter, icon_glyph)
            else:
                # Fallback: shrink text name to fit
                max_chars = max(1, int(rect.width() / (icon_size * 0.6)))
                if len(icon_name) > max_chars:
                    icon_size = max(9, int(rect.width() / (len(icon_name) * 0.7)))
                painter.setFont(QFont("Arial", icon_size))
                painter.drawText(rect.adjusted(4, 2, -4, -rect.height() / 3), Qt.AlignCenter, icon_name)
            label_size = max(8, min(13, int(rect.height() * 0.12)))
            painter.setFont(QFont("Arial", label_size))
            painter.drawText(rect.adjusted(4, rect.height() * 2 / 3 - 4, -4, -2), Qt.AlignCenter, label)
        elif label:
            label_size = max(9, min(14, int(min(rect.width(), rect.height()) * 0.15)))
            painter.setFont(QFont("Arial", label_size))
            painter.drawText(rect, Qt.AlignCenter, label)
        elif icon_glyph or icon_name:
            icon_size = max(11, int(min(rect.width(), rect.height()) * 0.45))
            if fa_family and icon_glyph:
                painter.setFont(QFont(fa_family, icon_size))
                painter.drawText(rect, Qt.AlignCenter, icon_glyph)
            else:
                max_chars = max(1, int(rect.width() / (icon_size * 0.6)))
                if len(icon_name) > max_chars:
                    icon_size = max(11, int(rect.width() / (len(icon_name) * 0.7)))
                painter.setFont(QFont("Arial", icon_size))
                painter.drawText(rect, Qt.AlignCenter, icon_name)

    def _paint_stat_monitor(self, painter, rect, qcolor):
        stat_type = self.widget_dict.get("stat_type", 0x01)
        value_pos = self.widget_dict.get("value_position", 0)
        painter.setPen(qcolor)

        if value_pos == 0:
            # Inline: single centered text matching display placeholder
            placeholder = STAT_PLACEHOLDERS.get(stat_type, "--%")
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            painter.drawText(rect, Qt.AlignCenter, placeholder)
        else:
            name = STAT_NAME_LABELS.get(stat_type, "?")
            value = STAT_VALUE_PLACEHOLDERS.get(stat_type, "--")
            half = rect.height() / 2
            if value_pos == 1:
                # Value on top, name on bottom
                painter.setFont(QFont("Arial", 11, QFont.Bold))
                painter.drawText(rect.adjusted(4, 2, -4, -half), Qt.AlignCenter, value)
                painter.setFont(QFont("Arial", 8))
                painter.drawText(rect.adjusted(4, half, -4, -2), Qt.AlignCenter, name)
            else:
                # Name on top, value on bottom
                painter.setFont(QFont("Arial", 8))
                painter.drawText(rect.adjusted(4, 2, -4, -half), Qt.AlignCenter, name)
                painter.setFont(QFont("Arial", 11, QFont.Bold))
                painter.drawText(rect.adjusted(4, half, -4, -2), Qt.AlignCenter, value)

    def _paint_status_bar(self, painter, rect, qcolor):
        from datetime import datetime
        painter.setPen(qcolor)
        painter.setFont(QFont("Arial", 9))
        left_x = rect.left() + 8
        # Left side: keyboard icon + page label (matches display)
        label = self.widget_dict.get("label", "Hotkeys")
        painter.drawText(QRectF(left_x, rect.top(), 160, rect.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, "\u2328  " + label)
        # Center: time (matches display placement)
        if self.widget_dict.get("show_time", True):
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            painter.save()
            painter.setPen(QColor(0x2E, 0xCC, 0x71))  # CLR_GREEN
            painter.drawText(rect, Qt.AlignCenter, time_str)
            painter.restore()
        # Right side: icons packed right-to-left (matches display order)
        right_parts = []
        if self.widget_dict.get("show_wifi", True):
            right_parts.append("\U0001F4F6")   # WiFi
        if self.widget_dict.get("show_pc", True):
            right_parts.append("\U0001F50C")   # USB
        if self.widget_dict.get("show_settings", True):
            right_parts.append("\u2699")       # Settings gear
        if self.widget_dict.get("show_brightness", True):
            right_parts.append("\u2600")       # Brightness
        if right_parts:
            spacing = self.widget_dict.get("icon_spacing", 8)
            gap = " " * max(1, spacing // 4)
            status_text = gap.join(right_parts)
            painter.drawText(rect.adjusted(0, 0, -8, 0),
                             Qt.AlignRight | Qt.AlignVCenter, status_text)

    def _paint_clock(self, painter, rect, qcolor):
        painter.setPen(qcolor)
        if self.widget_dict.get("clock_analog", False):
            # Draw circle for analog clock
            cx, cy = rect.center().x(), rect.center().y()
            r = min(rect.width(), rect.height()) / 2 - 4
            painter.drawEllipse(QPointF(cx, cy), r, r)
            painter.setFont(QFont("Arial", 7))
            painter.drawText(rect, Qt.AlignCenter, "12")
        else:
            painter.setFont(QFont("Arial", 14, QFont.Bold))
            painter.drawText(rect, Qt.AlignCenter, "00:00")

    def _paint_text_label(self, painter, rect, qcolor):
        label = self.widget_dict.get("label", "Label")
        font_size = self.widget_dict.get("font_size", 16)
        text_align = self.widget_dict.get("text_align", 1)
        qt_align = {0: Qt.AlignLeft, 1: Qt.AlignHCenter, 2: Qt.AlignRight}.get(text_align, Qt.AlignHCenter)
        painter.setPen(qcolor)
        painter.setFont(QFont("Arial", max(7, font_size // 2)))
        painter.drawText(rect.adjusted(4, 0, -4, 0), qt_align | Qt.AlignVCenter, label)

    def _paint_separator(self, painter, rect, qcolor):
        thickness = self.widget_dict.get("thickness", 2)
        painter.setPen(QPen(qcolor, max(1, thickness)))
        if self.widget_dict.get("separator_vertical", False):
            cx = rect.center().x()
            painter.drawLine(int(cx), int(rect.top() + 2), int(cx), int(rect.bottom() - 2))
        else:
            cy = rect.center().y()
            painter.drawLine(int(rect.left() + 2), int(cy), int(rect.right() - 2), int(cy))

    def _paint_page_nav(self, painter, rect, qcolor):
        painter.setPen(Qt.NoPen)
        dot_r = 4
        spacing = 14
        # Read actual page count from scene
        page_count = 1
        if self.scene() and hasattr(self.scene(), 'page_count'):
            page_count = max(1, self.scene().page_count)
        cx = rect.center().x()
        cy = rect.center().y()
        total_w = (page_count - 1) * spacing
        start_x = cx - total_w / 2
        for i in range(page_count):
            x = start_x + i * spacing
            if i == 0:
                painter.setBrush(QBrush(qcolor))
            else:
                painter.setBrush(QBrush(QColor("#555")))
            painter.drawEllipse(QPointF(x, cy), dot_r, dot_r)


# ============================================================
# Resize Handle -- 8 handles for resizing selected widget
# ============================================================

class ResizeHandle(QGraphicsRectItem):
    """A small square handle for resizing a CanvasWidgetItem."""

    HANDLE_SIZE = 8
    TL, T, TR, L, R, BL, B, BR = range(8)

    CURSORS = {
        0: Qt.SizeFDiagCursor,  # TL
        1: Qt.SizeVerCursor,    # T
        2: Qt.SizeBDiagCursor,  # TR
        3: Qt.SizeHorCursor,    # L
        4: Qt.SizeHorCursor,    # R
        5: Qt.SizeBDiagCursor,  # BL
        6: Qt.SizeVerCursor,    # B
        7: Qt.SizeFDiagCursor,  # BR
    }

    def __init__(self, handle_pos, tracked_item):
        s = self.HANDLE_SIZE
        super().__init__(-s / 2, -s / 2, s, s)
        self.handle_pos = handle_pos
        self.tracked_item = tracked_item
        self.setBrush(QBrush(QColor("#FFD700")))
        self.setPen(QPen(QColor("#B8860B"), 1))
        self.setZValue(1000)
        self.setCursor(self.CURSORS.get(handle_pos, Qt.ArrowCursor))
        self.setAcceptHoverEvents(True)
        self._dragging = False
        self._drag_start = None
        self._start_rect = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.scenePos()
            item = self.tracked_item
            self._start_rect = QRectF(
                item.pos().x(), item.pos().y(), item._w, item._h
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging or self._start_rect is None:
            return

        delta = event.scenePos() - self._drag_start
        r = QRectF(self._start_rect)

        if self.handle_pos in (self.TL, self.L, self.BL):
            r.setLeft(r.left() + delta.x())
        if self.handle_pos in (self.TR, self.R, self.BR):
            r.setRight(r.right() + delta.x())
        if self.handle_pos in (self.TL, self.T, self.TR):
            r.setTop(r.top() + delta.y())
        if self.handle_pos in (self.BL, self.B, self.BR):
            r.setBottom(r.bottom() + delta.y())

        # Snap to grid
        x = round(r.x() / SNAP_GRID) * SNAP_GRID
        y = round(r.y() / SNAP_GRID) * SNAP_GRID
        w = round(r.width() / SNAP_GRID) * SNAP_GRID
        h = round(r.height() / SNAP_GRID) * SNAP_GRID

        # Enforce minimum size
        if w < WIDGET_MIN_W:
            if self.handle_pos in (self.TL, self.L, self.BL):
                x = self._start_rect.right() - WIDGET_MIN_W
            w = WIDGET_MIN_W
        if h < WIDGET_MIN_H:
            if self.handle_pos in (self.TL, self.T, self.TR):
                y = self._start_rect.bottom() - WIDGET_MIN_H
            h = WIDGET_MIN_H

        # Clamp to display
        x = max(0, x)
        y = max(0, y)
        if x + w > DISPLAY_WIDTH:
            w = DISPLAY_WIDTH - x
        if y + h > DISPLAY_HEIGHT:
            h = DISPLAY_HEIGHT - y

        self.tracked_item._suppress_notify = True
        self.tracked_item.setPos(x, y)
        self.tracked_item.set_size(w, h)
        self.tracked_item._suppress_notify = False

        scene = self.scene()
        if scene and hasattr(scene, "update_handles"):
            scene.update_handles()

        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            scene = self.scene()
            if scene and hasattr(scene, "on_widget_resized"):
                scene.on_widget_resized(self.tracked_item)
            event.accept()
