"""
Canvas Scene: CanvasScene (800x480 display canvas), CanvasView (scaled view), ItemsPalette (drag source).
"""

import logging

from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QListWidget,
    QListWidgetItem,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPointF, QMimeData, QTimer
from PySide6.QtGui import QKeySequence, QPen, QBrush, QColor, QPainter, QDrag

from companion.config_manager import (
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    SNAP_GRID,
    WIDGET_DEFAULT_SIZES,
    WIDGET_TYPE_NAMES,
    WIDGET_TYPE_MAX,
)
from companion.ui.canvas_items import CanvasWidgetItem, ResizeHandle
from companion.ui.editor_constants import WIDGET_PALETTE_ICONS

logger = logging.getLogger(__name__)


# ============================================================
# Canvas Scene -- 800x480 with grid, drag-drop, selection management
# ============================================================

class CanvasScene(QGraphicsScene):
    """The 800x480 display canvas with grid lines and widget management."""

    widget_selected = Signal(str)    # widget_id
    widget_deselected = Signal()
    widget_geometry_changed = Signal(str, int, int, int, int)  # widget_id, x, y, w, h
    widget_dropped = Signal(int, int, int)  # type, x, y
    delete_requested = Signal(list)
    paste_requested = Signal(list)
    move_to_page_requested = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self._handles = []
        self._tracked_item = None
        self._clipboard = []  # list of widget dicts for copy/paste
        self._multi_move_origin = None  # for group drag
        self.page_count = 1  # updated by EditorMainWindow when pages change
        self.page_list = []  # list of (page_idx, page_name) tuples
        self.current_page_index = 0

    def drawBackground(self, painter, rect):
        # Fill everything outside the canvas dark
        painter.fillRect(rect, QColor("#06090f"))
        # Fill the canvas area
        canvas = QRectF(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        painter.fillRect(canvas, QColor("#0D1117"))
        # Subtle grid lines (only inside canvas)
        pen = QPen(QColor("#1a1f2e"), 0.5)
        painter.setPen(pen)
        for x in range(0, DISPLAY_WIDTH + 1, SNAP_GRID):
            painter.drawLine(x, 0, x, DISPLAY_HEIGHT)
        for y in range(0, DISPLAY_HEIGHT + 1, SNAP_GRID):
            painter.drawLine(0, y, DISPLAY_WIDTH, y)
        # Canvas border
        painter.setPen(QPen(QColor("#30363d"), 2))
        painter.drawRect(canvas)

    def on_selection_changed(self):
        """Called when item selection changes."""
        selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
        if len(selected) == 1:
            item = selected[0]
            self._show_handles(item)
            self.widget_selected.emit(item.widget_id)
        else:
            self._clear_handles()
            self.widget_deselected.emit()

    def on_widget_moved(self, item):
        """Called when a widget item has been moved."""
        x, y = int(item.pos().x()), int(item.pos().y())
        self.widget_geometry_changed.emit(item.widget_id, x, y, item._w, item._h)
        self.update_handles()

    def on_widget_resized(self, item):
        """Called when a widget item has been resized (handle released)."""
        x, y = int(item.pos().x()), int(item.pos().y())
        self.widget_geometry_changed.emit(item.widget_id, x, y, item._w, item._h)

    def _show_handles(self, item):
        """Show resize handles around the given item."""
        self._clear_handles()
        self._tracked_item = item
        for hp in range(8):
            handle = ResizeHandle(hp, item)
            self.addItem(handle)
            self._handles.append(handle)
        self.update_handles()

    def _clear_handles(self):
        """Remove all resize handles from scene."""
        for handle in self._handles:
            self.removeItem(handle)
        self._handles.clear()
        self._tracked_item = None

    def update_handles(self):
        """Reposition handles around tracked item."""
        if not self._tracked_item or not self._handles:
            return
        item = self._tracked_item
        x, y = item.pos().x(), item.pos().y()
        w, h = item._w, item._h
        positions = [
            (x, y),                    # TL
            (x + w / 2, y),            # T
            (x + w, y),                # TR
            (x, y + h / 2),            # L
            (x + w, y + h / 2),        # R
            (x, y + h),                # BL
            (x + w / 2, y + h),        # B
            (x + w, y + h),            # BR
        ]
        for handle, pos in zip(self._handles, positions):
            handle.setPos(pos[0], pos[1])

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-widget-type"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-widget-type"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-widget-type"):
            data = event.mimeData().data("application/x-widget-type")
            widget_type = int(bytes(data).decode())
            pos = event.scenePos()
            x = round(pos.x() / SNAP_GRID) * SNAP_GRID
            y = round(pos.y() / SNAP_GRID) * SNAP_GRID
            # Clamp to display
            dw, dh = WIDGET_DEFAULT_SIZES.get(widget_type, (180, 100))
            x = max(0, min(DISPLAY_WIDTH - dw, x))
            y = max(0, min(DISPLAY_HEIGHT - dh, y))
            self.widget_dropped.emit(widget_type, int(x), int(y))
            event.acceptProposedAction()

    def contextMenuEvent(self, event):
        """Right-click context menu for canvas items."""
        items_at = [i for i in self.items(event.scenePos()) if isinstance(i, CanvasWidgetItem)]
        selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]

        # If right-clicked on an unselected item, select it
        if items_at and items_at[0] not in selected:
            self.clearSelection()
            items_at[0].setSelected(True)
            selected = [items_at[0]]

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: #1c2128; color: #e0e0e0; border: 1px solid #333; }"
            "QMenu::item:selected { background: #2d333b; }"
            "QMenu::separator { background: #333; height: 1px; margin: 4px 8px; }"
        )

        if selected:
            count = len(selected)
            label = f"{count} widgets" if count > 1 else "widget"

            # Copy
            copy_action = menu.addAction(f"Copy {label}")
            copy_action.setShortcut(QKeySequence.Copy)

            # Duplicate
            dup_action = menu.addAction(f"Duplicate {label}")
            dup_action.setShortcut(QKeySequence("Ctrl+D"))

            menu.addSeparator()

            # Move to page submenu
            move_menu = menu.addMenu("Move to Page...")
            page_actions = []
            for page_idx, page_name in self.page_list:
                    if page_idx != self.current_page_index:
                        pa = move_menu.addAction(page_name)
                        pa.setData(page_idx)
                        page_actions.append(pa)
            if not page_actions:
                move_menu.setEnabled(False)

            menu.addSeparator()

            # Z-order
            front_action = menu.addAction("Bring to Front")
            back_action = menu.addAction("Send to Back")

            menu.addSeparator()

            # Delete
            del_action = menu.addAction(f"Delete {label}")
            del_action.setShortcut(QKeySequence.Delete)
        else:
            copy_action = dup_action = front_action = back_action = del_action = None
            page_actions = []

        # Paste (always available if clipboard has content)
        menu.addSeparator()
        paste_action = menu.addAction("Paste")
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.setEnabled(bool(self._clipboard))

        # Execute
        action = menu.exec(event.screenPos())
        if action is None:
            return

        if action == copy_action:
            self._copy_selected(selected)
        elif action == del_action:
            self._delete_selected(selected)
        elif action == dup_action:
            self._copy_selected(selected)
            self._paste_at(event.scenePos())
        elif action == paste_action:
            self._paste_at(event.scenePos())
        elif action == front_action:
            max_z = max((i.zValue() for i in self.items() if isinstance(i, CanvasWidgetItem)), default=0)
            for item in selected:
                item.setZValue(max_z + 1)
        elif action == back_action:
            min_z = min((i.zValue() for i in self.items() if isinstance(i, CanvasWidgetItem)), default=0)
            for item in selected:
                item.setZValue(min_z - 1)
        elif action in page_actions:
            target_page = action.data()
            self.move_to_page_requested.emit([i.widget_id for i in selected], target_page)

    def _copy_selected(self, selected):
        """Copy selected widget dicts to clipboard."""
        import copy
        self._clipboard = []
        for item in selected:
            d = copy.deepcopy(item.widget_dict)
            self._clipboard.append(d)

    def _paste_at(self, scene_pos):
        """Paste clipboard widgets near the given position."""
        if not self._clipboard:
            return
        import copy
        offset = 20
        widgets = []
        for d in self._clipboard:
            nd = copy.deepcopy(d)
            nd["x"] = min(DISPLAY_WIDTH - nd.get("width", 100), max(0, nd["x"] + offset))
            nd["y"] = min(DISPLAY_HEIGHT - nd.get("height", 100), max(0, nd["y"] + offset))
            widgets.append(nd)
        self.paste_requested.emit(widgets)

    def _delete_selected(self, selected):
        """Delete selected items."""
        for item in selected:
            self.removeItem(item)
        self._clear_handles()
        self.delete_requested.emit([item.widget_id for item in selected])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
            if selected:
                self._delete_selected(selected)
        elif event.matches(QKeySequence.Copy):
            selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
            if selected:
                self._copy_selected(selected)
        elif event.matches(QKeySequence.Paste):
            # Paste at center of view
            views = self.views()
            if views:
                center = views[0].mapToScene(views[0].viewport().rect().center())
                self._paste_at(center)
        elif event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
            if selected:
                self._copy_selected(selected)
                center = selected[0].pos()
                self._paste_at(QPointF(center.x(), center.y()))
        else:
            super().keyPressEvent(event)


# ============================================================
# Canvas View -- scaled view with aspect ratio
# ============================================================

class CanvasView(QGraphicsView):
    """Scaled view of the 800x480 canvas, always fits to available space."""

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setMinimumSize(400, 250)
        # Disable scrollbars -- canvas must always fit in view
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("background: #0a0e14; border: 1px solid #333;")

    def _fit(self):
        # Small margin so the canvas border is visible
        margin = 10
        r = self.scene().sceneRect().adjusted(-margin, -margin, margin, margin)
        self.fitInView(r, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit)  # defer so layout is settled


# ============================================================
# Items Palette -- drag source for widget types
# ============================================================

class ItemsPalette(QListWidget):
    """Left sidebar with draggable widget types."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setMaximumWidth(150)
        self.setMinimumWidth(120)
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(
            "QListWidget { background: #161b22; border: 1px solid #333; }"
            "QListWidget::item { padding: 8px 4px; color: #e0e0e0; }"
            "QListWidget::item:hover { background: #21262d; }"
        )

        for wtype in range(WIDGET_TYPE_MAX + 1):
            name = WIDGET_TYPE_NAMES.get(wtype, f"Type {wtype}")
            icon_char = WIDGET_PALETTE_ICONS.get(wtype, "?")
            item = QListWidgetItem(f"{icon_char}  {name}")
            item.setData(Qt.UserRole, wtype)
            self.addItem(item)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        wtype = item.data(Qt.UserRole)
        mime.setData("application/x-widget-type", str(wtype).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)
