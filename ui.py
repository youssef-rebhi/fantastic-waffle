import os
import sys

import keyboard
from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai import PROVIDER_PRESETS, list_provider_ids, provider_label
from saved_api_keys import (
    add_entry,
    delete_entry,
    get_key_by_id,
    get_last_entry_id,
    set_last_entry_id,
    list_entries,
    storage_location_hint,
)

class SelectionWindow(QWidget):
    """Draggable and resizable overlay window for screen selection"""

    def __init__(self, color, position, size):
        super().__init__()
        self.color = color
        self.interactive = True
        self.dragging = False
        self.resizing = False
        self.drag_start = QPoint()
        self.resize_start = QPoint()
        self.resize_rect = QRect()
        self.resize_margin = 10

        self.setup_window(position, size)

    def setup_window(self, position, size):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(position[0], position[1], size[0], size[1])
        self.setMouseTracking(True)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setBrush(QColor(*self.color, 50))
        painter.setPen(QColor(*self.color, 200))
        painter.drawRect(self.rect())

    def mousePressEvent(self, event):
        if not self.interactive or event.button() != Qt.LeftButton:
            return

        if self.is_on_edge(event.pos()):
            self.resizing = True
            self.resize_start = event.globalPos()
            self.resize_rect = self.geometry()
        else:
            self.dragging = True
            self.drag_start = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if not self.interactive:
            return

        if self.resizing:
            diff = event.globalPos() - self.resize_start
            new_rect = QRect(self.resize_rect)
            new_rect.setBottomRight(new_rect.bottomRight() + diff)
            self.setGeometry(new_rect)
        elif self.dragging:
            self.move(event.globalPos() - self.drag_start)
        else:
            cursor = Qt.SizeFDiagCursor if self.is_on_edge(event.pos()) else Qt.ArrowCursor
            self.setCursor(cursor)

    def mouseReleaseEvent(self, event):
        if not self.interactive:
            return
        self.dragging = False
        self.resizing = False

    def is_on_edge(self, pos):
        rect = self.rect()
        return (
            abs(pos.x() - rect.right()) < self.resize_margin
            and abs(pos.y() - rect.bottom()) < self.resize_margin
        )

    def get_rect(self):
        geo = self.geometry()
        return (geo.left(), geo.top(), geo.width(), geo.height())

    def toggle_interactive(self):
        self.interactive = not self.interactive
        if self.interactive:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        else:
            self.setWindowFlags(
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.Tool
                | Qt.WindowTransparentForInput
            )
        self.show()


class ControlPanel(QWidget):
    """Settings and answer display (stays on top)."""

    # Emitted from e.g. global hotkeys (non-Qt threads); queued to GUI thread.
    _signal_set_status = pyqtSignal(str)
    _signal_set_result = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quiz helper")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMinimumWidth(360)

        self.provider_combo = QComboBox()
        for pid in list_provider_ids():
            self.provider_combo.addItem(provider_label(pid), pid)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.saved_key_combo = QComboBox()
        self.saved_key_combo.setToolTip(
            "Pick a saved key or stay on Manual. Keys are stored on this PC only "
            "— see Save / Remove buttons."
            f"\nFile: {storage_location_hint()}"
        )

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Paste API key here (or choose saved)")

        self._setting_key_programmatically = False

        self.save_key_btn = QPushButton("Save key…")
        self.save_key_btn.setToolTip("Save the current key with a label for reuse")
        self.save_key_btn.clicked.connect(self._on_click_save_key)

        self.forget_key_btn = QPushButton("Remove saved")
        self.forget_key_btn.setToolTip("Delete the highlighted saved key from disk")
        self.forget_key_btn.clicked.connect(self._on_click_remove_saved)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.save_key_btn)
        btn_row.addWidget(self.forget_key_btn)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("Optional: override default model ID")

        self.two_step_check = QCheckBox(
            "Two-step prompting (extra API call; more accurate)"
        )
        self.two_step_check.setChecked(False)
        self.two_step_hint = QLabel(
            "Tip: keep this off if you hit rate limits — each solver run uses fewer requests."
        )
        self.two_step_hint.setWordWrap(True)
        self.two_step_hint.setStyleSheet("color: #444;")

        self.status_label = QLabel("F8: solve | F6/F7: toggle red/blue capture areas")
        self.status_label.setWordWrap(True)

        self.answer_edit = QTextEdit()
        self.answer_edit.setReadOnly(True)
        self.answer_edit.setPlaceholderText("AI answer appears here after F8.")
        self.answer_edit.setMinimumHeight(120)

        settings = QGroupBox("API")
        form = QFormLayout()
        form.addRow("Provider", self.provider_combo)
        form.addRow("Saved key", self.saved_key_combo)
        form.addRow("API key", self.api_key_edit)
        form.addRow(btn_row)
        form.addRow("Model (optional)", self.model_edit)
        settings.setLayout(form)
        root = QVBoxLayout(self)
        root.addWidget(settings)
        root.addWidget(self.two_step_check)
        root.addWidget(self.two_step_hint)
        root.addWidget(self.status_label)
        root.addWidget(QLabel("Answer"))
        root.addWidget(self.answer_edit)

        self._on_provider_changed()
        self._place_bottom_right()

        self._signal_set_status.connect(self._apply_status_slot, Qt.QueuedConnection)
        self._signal_set_result.connect(self._apply_result_slot, Qt.QueuedConnection)

        self.saved_key_combo.currentIndexChanged.connect(self._on_saved_key_changed)
        self.api_key_edit.textEdited.connect(self._on_api_key_typed)

        self._populate_saved_keys_combo(select_id=get_last_entry_id())
        self._bootstrap_key_field_after_combo_ready()

    def _apply_status_slot(self, text: str):
        self.status_label.setStyleSheet("")
        self.status_label.setText(text)

    def _apply_result_slot(self, answer: str, error: str):
        if error:
            self.status_label.setStyleSheet("color: #b00020;")
            self.status_label.setText(error)
            if not answer:
                self.answer_edit.clear()
        else:
            self.status_label.setStyleSheet("")
            self.status_label.setText("Done.")
            self.answer_edit.setPlainText(answer or "")

    def _populate_saved_keys_combo(self, select_id=None):
        self.saved_key_combo.blockSignals(True)
        self.saved_key_combo.clear()
        self.saved_key_combo.addItem("— Manual (paste below) —", None)
        preferred = select_id if select_id is not None else get_last_entry_id()
        idx_pick = 0
        for e in list_entries():
            self.saved_key_combo.addItem(e["label"], e["id"])
        if preferred:
            for i in range(self.saved_key_combo.count()):
                if self.saved_key_combo.itemData(i) == preferred:
                    idx_pick = i
                    break
        self.saved_key_combo.setCurrentIndex(idx_pick)
        self.saved_key_combo.blockSignals(False)

    def _bootstrap_key_field_after_combo_ready(self):
        eid = self.saved_key_combo.currentData()
        if eid:
            self._setting_key_programmatically = True
            self.api_key_edit.setText(get_key_by_id(eid) or "")
            self._setting_key_programmatically = False
        elif not self.api_key_edit.text().strip():
            self._prefill_key_from_env()

    def _on_saved_key_changed(self, _index=-1):
        eid = self.saved_key_combo.currentData()
        set_last_entry_id(eid if eid else None)
        if not eid:
            return
        self._setting_key_programmatically = True
        self.api_key_edit.setText(get_key_by_id(eid) or "")
        self._setting_key_programmatically = False

    def _on_api_key_typed(self, _text: str):
        if self._setting_key_programmatically:
            return
        self.saved_key_combo.blockSignals(True)
        self.saved_key_combo.setCurrentIndex(0)
        self.saved_key_combo.blockSignals(False)
        set_last_entry_id(None)

    def _on_click_save_key(self):
        key = self.api_key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "No key", "Enter an API key in the field first.")
            return
        label, ok = QInputDialog.getText(self, "Save key", "Label for this key (e.g. OpenRouter personal):")
        if not ok or not label.strip():
            return
        entry = add_entry(label.strip(), key)
        self._populate_saved_keys_combo(select_id=entry["id"])
        self._on_saved_key_changed()

    def _on_click_remove_saved(self):
        eid = self.saved_key_combo.currentData()
        if not eid:
            QMessageBox.information(
                self,
                "Remove saved",
                "Choose a saved key in the dropdown (not Manual) to remove.",
            )
            return
        label = self.saved_key_combo.currentText()
        if (
            QMessageBox.question(
                self,
                "Remove saved key",
                f'Forget "{label}" from this computer?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        delete_entry(eid)
        self._populate_saved_keys_combo(select_id=None)
        self.api_key_edit.clear()
        set_last_entry_id(None)

    def _place_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        margin = 16
        x = screen.right() - self.width() - margin
        y = screen.bottom() - self.height() - margin
        self.move(max(screen.left(), x), max(screen.top(), y))

    def _prefill_key_from_env(self):
        from dotenv import load_dotenv

        load_dotenv()
        load_dotenv("api.env")
        key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or ""
        )
        if key and not self.api_key_edit.text().strip():
            self.api_key_edit.setText(key)

    def _on_provider_changed(self, _index=0):
        pid = self.provider_combo.currentData()
        preset = PROVIDER_PRESETS.get(pid) or {}
        default = preset.get("default_model", "")
        self.model_edit.setPlaceholderText(
            f"Leave empty for default ({default})" if default else "Optional model override"
        )

    def get_ai_context(self):
        return {
            "provider_id": self.provider_combo.currentData(),
            "api_key": self.api_key_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "use_prompt_enhancement": self.two_step_check.isChecked(),
        }

    def set_status(self, text: str):
        self._signal_set_status.emit(text)

    def set_result(self, answer: str = "", error: str = ""):
        self._signal_set_result.emit(answer or "", error or "")


def toggle_window(window, name):
    window.toggle_interactive()
    mode = "interactive" if window.interactive else "click-through"
    print(f"🔄 {name} rectangle: {mode} mode")


def setup_ui():
    app = QApplication(sys.argv)

    question_window = SelectionWindow((255, 0, 0), (100, 100), (500, 100))
    options_window = SelectionWindow((0, 0, 255), (100, 250), (500, 200))
    control_panel = ControlPanel()
    control_panel.show()

    return app, question_window, options_window, control_panel


def setup_hotkeys(question_window, options_window, process_callback):
    keyboard.add_hotkey("F6", lambda: toggle_window(question_window, "Red"))
    keyboard.add_hotkey("F7", lambda: toggle_window(options_window, "Blue"))
    keyboard.add_hotkey("F8", process_callback)
