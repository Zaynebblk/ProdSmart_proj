import sqlite3
import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QPushButton, QScrollArea, QDialog,
                             QLineEdit, QDateEdit, QComboBox, QMessageBox,
                             QCheckBox, QGraphicsDropShadowEffect, QSizePolicy,
                             QSystemTrayIcon, QGridLayout)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QColor, QIcon, QFontMetrics
from PyQt6.QtMultimedia import QSoundEffect
from resources.theme import get_theme, FONT_FAMILY, rgba
from resources.priority import (
    normalize_priority,
    priority_to_quadrant,
    quadrant_from_flags,
)

# --- NO WHEEL COMBOBOX ---
class NoWheelComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ensure_font_size()

    def _ensure_font_size(self):
        font = self.font()
        if font.pointSize() <= 0:
            font.setPointSize(10)
            self.setFont(font)
        view = self.view()
        if view:
            view_font = view.font()
            if view_font.pointSize() <= 0:
                view_font.setPointSize(10)
                view.setFont(view_font)

    def wheelEvent(self, event):
        event.ignore()

# --- STYLES HELPER ---
def get_dialog_style(theme):
    c = get_theme(theme)
    is_dark = theme == "Dark"
    dialog_bg = c["card_alt"] if is_dark else c["bg"]
    input_bg = c["input_bg"]
    focus = c["accent2"]
    text_color = c["text"]
    return f"""
        QDialog {{ background-color: {dialog_bg}; }}
        QLabel {{ color: {text_color}; font-weight: 600; font-size: 13px; padding-top: 10px; }}
        QLineEdit, QDateEdit {{
            background-color: {input_bg}; border: 1px solid {c['border']};
            border-radius: 10px; padding: 10px; font-size: 14px; color: {text_color};
        }}
        QComboBox {{
            background-color: {input_bg}; border: 1px solid {c['border']};
            border-radius: 10px; padding: 10px; font-size: 10.5pt; color: {text_color};
        }}
        QLineEdit:focus, QDateEdit:focus {{ border: 1px solid {focus}; }}
        QComboBox::drop-down {{ border: none; }}
        QComboBox QAbstractItemView {{ background-color: {input_bg}; color: {text_color}; selection-background-color: {c['accent']}; }}
    """

PALETTE = {
    "mist": "#BAD2E0",
    "sky": "#82AFF2",
    "ocean": "#3078CD",
    "deep": "#25456B",
    "abyss": "#113356",
    "paper": "#F8F6F2"
}

STYLES = {
    "btn_primary": """
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3078CD, stop:1 #82AFF2);
            color: white; border-radius: 16px; font-weight: bold; font-size: 14px; border: none;
            padding: 10px 18px;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #25456B, stop:1 #3078CD); }
    """,
    "btn_secondary": """
        QPushButton {
            background-color: transparent; color: #25456B; border: 1px solid #BAD2E0;
            border-radius: 12px; padding: 8px 16px; font-weight: bold;
        }
        QPushButton:hover { background-color: #BAD2E0; color: #113356; border-color: #82AFF2; }
    """
}

PRIORITY_COLORS = {
    "high": "#ef4444",
    "medium": "#f59e0b",
    "low": "#3b82f6",
    "too low": "#94a3b8"
}

# --- DIALOGS ---
class AddTaskDialog(QDialog):
    def __init__(self, parent=None, title_text="New Task", theme="Light"):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.setFixedWidth(400)
        self.setStyleSheet(get_dialog_style(theme))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        lbl_head = QLabel(title_text.upper())
        lbl_head.setStyleSheet("color: #3078CD; font-size: 12px; font-weight: 800;")
        layout.addWidget(lbl_head)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("What needs to be done?")
        layout.addWidget(self.title_input)

        self.title_error = QLabel("Champ requis")
        self.title_error.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 600;")
        self.title_error.setVisible(False)
        layout.addWidget(self.title_error)
        self.title_input.textChanged.connect(lambda _: self._set_title_error(False))

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Add details...")
        layout.addWidget(self.desc_input)

        lbl_due = QLabel("Deadline:")
        layout.addWidget(lbl_due)

        row = QHBoxLayout()
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())

        self.important_check = QCheckBox("Important", self)
        self.important_check.setCursor(Qt.CursorShape.PointingHandCursor)

        row.addWidget(self.date_input)
        row.addWidget(self.important_check)
        layout.addLayout(row)

        layout.addSpacing(10)

        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(STYLES["btn_secondary"])
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("Save Task")
        self.btn_save.setStyleSheet(STYLES["btn_primary"])
        self.btn_save.setFixedSize(120, 40)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def _set_title_error(self, show):
        self.title_error.setVisible(bool(show))

    def accept(self):
        if not self.title_input.text().strip():
            self._set_title_error(True)
            self.title_input.setFocus()
            return
        self._set_title_error(False)
        super().accept()

    def load_data(self, title, desc, date_str, important):
        self.title_input.setText(title)
        self.desc_input.setText(desc)
        if date_str: self.date_input.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        self.important_check.setChecked(bool(important))

    def get_data(self):
        return {
            "title": self.title_input.text(),
            "description": self.desc_input.text(),
            "date": self.date_input.date().toString("yyyy-MM-dd"),
            "important": self.important_check.isChecked()
        }

class ViewTaskDialog(QDialog):
    def __init__(self, title, desc, due_date, created_date, priority, total_focus_min=0, total_sessions=0, sessions=None, parent=None, theme="Light"):
        super().__init__(parent)
        self.setWindowTitle("Task Details")
        self.setFixedWidth(400)
        if sessions is None:
            sessions = []

        bg = "#113356" if theme == "Dark" else "#F8F6F2"
        txt = "#e6eef5" if theme == "Dark" else "#113356"
        box_bg = "#1b2f4d" if theme == "Dark" else "#ffffff"

        self.setStyleSheet(f"QDialog {{ background-color: {bg}; }} QLabel {{ color: {txt}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        p_colors = PRIORITY_COLORS
        c = p_colors.get(priority, "#718096")
        lbl_p = QLabel(priority.upper())
        lbl_p.setStyleSheet(f"color: {c}; font-weight: 900; font-size: 11px;")
        layout.addWidget(lbl_p)

        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet(f"font-size: 22px; font-weight: 800; padding-top: 5px; color: {txt};")
        layout.addWidget(t)

        dates_row = QHBoxLayout()
        c_lbl = QLabel(f"Created: {created_date}")
        c_lbl.setStyleSheet("color: #82AFF2; font-size: 12px;")
        d_lbl = QLabel(f"Due: {due_date}")
        d_lbl.setStyleSheet("color: #3078CD; font-size: 12px; font-weight: bold;")

        dates_row.addWidget(c_lbl)
        dates_row.addSpacing(15)
        dates_row.addWidget(d_lbl)
        dates_row.addStretch()
        layout.addLayout(dates_row)

        layout.addSpacing(15)

        desc_box = QFrame()
        desc_box.setStyleSheet(f"background: {box_bg}; border-radius: 10px; padding: 15px;")
        dl = QVBoxLayout(desc_box)
        dl.setContentsMargins(0,0,0,0)
        lbl_desc = QLabel(desc if desc else "No details provided.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"color: {txt};")
        dl.addWidget(lbl_desc)
        layout.addWidget(desc_box)

        layout.addSpacing(16)

        # Pomodoro summary + sessions
        summary = QLabel(f"Focus total: {total_focus_min} min  -  Sessions: {total_sessions}")
        summary.setStyleSheet(f"color: {txt}; font-size: 11px; font-weight: 700;")
        layout.addWidget(summary)

        sess_box = QFrame()
        sess_box.setStyleSheet(f"background: {box_bg}; border-radius: 10px; padding: 12px;")
        sl = QVBoxLayout(sess_box)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(6)

        sessions_container = QWidget()
        sessions_layout = QVBoxLayout(sessions_container)
        sessions_layout.setContentsMargins(0, 0, 0, 0)
        sessions_layout.setSpacing(6)

        if sessions:
            for s in sessions:
                sessions_layout.addWidget(s)
        else:
            empty = QLabel("No Pomodoro sessions yet.")
            empty.setStyleSheet(f"color: {txt}; font-size: 11px;")
            sessions_layout.addWidget(empty)

        sessions_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(sessions_container)
        scroll.setFixedHeight(160)

        sl.addWidget(scroll)

        layout.addWidget(sess_box)

        layout.addSpacing(12)
        btn = QPushButton("Close")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(STYLES["btn_secondary"])
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

# --- TASK CARD ---
class TaskCard(QFrame):
    def __init__(self, t_id, title, desc, due_date_pretty, created_date_pretty, priority, focus_minutes, parent_page, is_completed=False):
        super().__init__()
        self.t_id = t_id
        self.parent_page = parent_page
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("TaskCard")

        self.priority = normalize_priority(priority) or "too low"
        self.title_text = title
        self.current_theme = "Light"
        self.accent_color = PRIORITY_COLORS.get(self.priority.lower(), "#94a3b8")
        self.focus_minutes = int(focus_minutes or 0)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(24)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(10)
        self.shadow.setColor(QColor(17, 51, 86, 35))
        self.setGraphicsEffect(self.shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.accent_bar = QFrame(self)
        self.accent_bar.setFixedWidth(6)
        self.accent_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.accent_bar.setObjectName("TaskAccent")

        accent_container = QWidget(self)
        accent_container.setFixedWidth(12)
        accent_layout = QVBoxLayout(accent_container)
        accent_layout.setContentsMargins(6, 12, 0, 12)
        accent_layout.addWidget(self.accent_bar)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 18, 18, 18)
        layout.setSpacing(10)

        outer.addWidget(accent_container)
        outer.addWidget(content)

        # Header
        header = QHBoxLayout()
        self.checkbox = QCheckBox(content)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.toggled.connect(self.on_checked)

        self.badge = QLabel(self.priority.upper(), content)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(78, 22)
        self.badge.setStyleSheet("font-size: 9px; font-weight: 900;")

        header.addWidget(self.checkbox)
        header.addStretch()
        header.addWidget(self.badge)
        layout.addLayout(header)

        self.lbl_title = QLabel(title, content)
        self.lbl_title.setWordWrap(True)
        layout.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(desc if desc else "", content)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setMaximumHeight(40)
        self.lbl_desc.setVisible(bool(desc))
        layout.addWidget(self.lbl_desc)

        footer = QVBoxLayout()
        footer.setSpacing(8)
        dates_layout = QVBoxLayout()
        dates_layout.setSpacing(2)

        self.lbl_created = QLabel(f"Created: {created_date_pretty}", content)
        self.lbl_created.setWordWrap(True)
        self.lbl_created.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.lbl_due = QLabel(f"Due: {due_date_pretty}", content)
        self.lbl_due.setWordWrap(True)
        self.lbl_due.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        dates_layout.addWidget(self.lbl_created)
        dates_layout.addWidget(self.lbl_due)

        self.lbl_focus = QLabel(f"Focus: {self.focus_minutes} min", content)
        self.lbl_focus.setWordWrap(True)
        self.lbl_focus.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        dates_layout.addWidget(self.lbl_focus)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)
        self.btn_edit = QPushButton("EDIT", content)
        self.btn_edit.setFixedHeight(20)
        self.btn_edit.setMinimumWidth(52)
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setStyleSheet(
            "QPushButton { background-color: #3078CD; border: 1px solid #25456B; color: white; "
            "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
            "QPushButton:hover { background-color: #25456B; border-color: #25456B; }"
        )
        self.btn_edit.clicked.connect(self.on_edit)

        self.btn_del = QPushButton("DELETE", content)
        self.btn_del.setFixedHeight(20)
        self.btn_del.setMinimumWidth(60)
        self.btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del.setStyleSheet(
            "QPushButton { background-color: #ef4444; border: 1px solid #b91c1c; color: white; "
            "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
            "QPushButton:hover { background-color: #b91c1c; border-color: #7f1d1d; }"
        )
        self.btn_del.clicked.connect(self.on_delete)

        self.btn_focus = QPushButton("FOCUS", content)
        self.btn_focus.setFixedHeight(20)
        self.btn_focus.setMinimumWidth(58)
        self.btn_focus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_focus.clicked.connect(self.on_focus)

        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_focus)
        actions_layout.addWidget(self.btn_edit)
        actions_layout.addWidget(self.btn_del)

        footer.addLayout(dates_layout)
        footer.addLayout(actions_layout)
        layout.addLayout(footer)

        self._set_checked_state(is_completed)
        self.update_theme("Light")

    def _set_checked_state(self, checked):
        checked = bool(checked)
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(checked)
        self.checkbox.blockSignals(False)
        f = self.lbl_title.font()
        f.setStrikeOut(checked)
        self.lbl_title.setFont(f)
        self._apply_text_styles(checked)

    def _apply_text_styles(self, checked=False):
        colors = get_theme(self.current_theme)
        checked_color = "#22c55e"
        if self.current_theme == "Dark":
            title_color = checked_color if checked else colors["text"]
            desc_color = colors["sub"] if not checked else checked_color
        else:
            title_color = checked_color if checked else colors["text"]
            desc_color = checked_color if checked else colors["sub"]

        self.lbl_title.setStyleSheet(f"color: {title_color}; font-size: 15px; font-weight: 800; border: none; background: transparent;")
        self.lbl_desc.setStyleSheet(f"color: {desc_color}; font-size: 11px; border: none; background: transparent;")

    def update_theme(self, theme):
        self.current_theme = theme
        colors = get_theme(theme)
        accent = self.accent_color
        if theme == "Dark":
            card_bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors['card_alt']}, stop:1 {colors['bg']})"
            border = colors["border"]
            hover_border = colors["accent2"]
            created_color = colors["sub"]
            due_color = colors["accent2"]
            focus_color = colors["accent"]
            checkbox_border = colors["border"]
            checkbox_bg = colors["card_alt"]
            edit_style = (
                f"QPushButton {{ background-color: {colors['accent']}; border: 1px solid {colors['deep']}; color: white; "
                f"border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }} "
                f"QPushButton:hover {{ background-color: {colors['deep']}; border-color: {colors['deep']}; }}"
            )
            del_style = (
                "QPushButton { background-color: #ef4444; border: 1px solid #7f1d1d; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background-color: #b91c1c; border-color: #7f1d1d; }"
            )
            focus_style = (
                "QPushButton { background-color: #22c55e; border: 1px solid #15803d; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background-color: #16a34a; border-color: #166534; }"
            )
        else:
            card_bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors['card']}, stop:1 {colors['accent_soft']})"
            border = colors["border"]
            hover_border = colors["accent"]
            created_color = colors["sub"]
            due_color = colors["deep"]
            focus_color = colors["accent"]
            checkbox_border = colors["border"]
            checkbox_bg = colors["card"]
            edit_style = (
                f"QPushButton {{ background-color: {colors['accent']}; border: 1px solid {colors['deep']}; color: white; "
                f"border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }} "
                f"QPushButton:hover {{ background-color: {colors['deep']}; border-color: {colors['deep']}; }}"
            )
            del_style = (
                "QPushButton { background-color: #ef4444; border: 1px solid #b91c1c; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background-color: #b91c1c; border-color: #7f1d1d; }"
            )
            focus_style = (
                "QPushButton { background-color: #22c55e; border: 1px solid #16a34a; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background-color: #16a34a; border-color: #166534; }"
            )

        self.setStyleSheet(
            f"QFrame#TaskCard {{ background: {card_bg}; border: 1px solid {border}; border-radius: 22px; }}"
            f"QFrame#TaskCard:hover {{ border: 1px solid {hover_border}; }}"
        )

        self.accent_bar.setStyleSheet(f"background: {accent}; border-radius: 3px;")

        self.checkbox.setStyleSheet(
            f"QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; "
            f"border: 2px solid {checkbox_border}; background: {checkbox_bg}; }}"
            "QCheckBox::indicator:checked { background-color: #22c55e; border-color: #16a34a; }"
        )

        self.badge.setStyleSheet(
            f"background: {accent}; color: white; border-radius: 11px; font-size: 9px; "
            "font-weight: 900; padding: 2px 6px;"
        )
        self.lbl_created.setStyleSheet(f"color: {created_color}; font-size: 10px; border: none; background: transparent;")
        self.lbl_due.setStyleSheet(f"color: {due_color}; font-size: 11px; font-weight: 800; border: none; background: transparent;")
        self.lbl_focus.setStyleSheet(f"color: {focus_color}; font-size: 10px; font-weight: 700; border: none; background: transparent;")
        self.btn_edit.setStyleSheet(edit_style)
        self.btn_del.setStyleSheet(del_style)
        self.btn_focus.setStyleSheet(focus_style)
        self._apply_text_styles(self.checkbox.isChecked())

    def enterEvent(self, event):
        self.shadow.setColor(QColor(48, 120, 205, 80))
        self.shadow.setBlurRadius(34)
        self.shadow.setYOffset(14)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.shadow.setColor(QColor(17, 51, 86, 45))
        self.shadow.setBlurRadius(24)
        self.shadow.setYOffset(10)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_page.show_task_details(self.t_id)
        super().mousePressEvent(event)

    def on_checked(self, checked):
        f = self.lbl_title.font()
        f.setStrikeOut(checked)
        self.lbl_title.setFont(f)
        self._apply_text_styles(checked)
        self.parent_page.mark_task_completed(self.t_id, checked)
        self.parent_page.task_added.emit()

    def on_edit(self): self.parent_page.edit_task(self.t_id)
    def on_delete(self): self.parent_page.delete_task(self.t_id)
    def on_focus(self): self.parent_page.start_pomodoro(self.t_id, self.title_text, self.priority)

# --- COLUMNS ---
class DayColumn(QWidget):
    def __init__(self, title, is_today=False, theme="Light"):
        super().__init__()
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cards = []
        self.title = title
        self.count = 0
        self.is_today = is_today
        self.current_theme = theme
        self._label_color = None
        self._label_base_size = 16
        self._label_min_size = 8
        self.setObjectName("DayColumn")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("DayPanel")
        self.panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.lbl = QLabel(title, self.panel)
        self.lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.lbl)

        self.accent = QFrame(self.panel)
        self.accent.setFixedHeight(3)
        self.accent.setMaximumWidth(70)
        layout.addWidget(self.accent)

        self.card_layout = QVBoxLayout()
        self.card_layout.setSpacing(16)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setContentsMargins(0, 6, 0, 6)

        layout.addLayout(self.card_layout)
        layout.addStretch()
        outer.addWidget(self.panel, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addStretch()
        self.update_theme(theme)

    def add_task_card(self, card):
        self.cards.append(card)
        self.count += 1
        self._update_label()
        self.card_layout.addWidget(card)

    def _update_label(self):
        self._apply_label_fit()

    def _label_text_full(self):
        suffix = "task" if self.count == 1 else "tasks"
        return f"{self.title}  -  {self.count} {suffix}"

    def _title_available_width(self):
        available = self.lbl.width()
        if available <= 10:
            available = max(10, self.panel.width() - 24)
        return available

    def _fit_size_for_text(self, base_size):
        text = self._label_text_full()
        available = self._title_available_width()
        font = self.lbl.font()
        chosen_size = self._label_min_size
        for size in range(int(base_size), self._label_min_size - 1, -1):
            font.setPointSize(size)
            metrics = QFontMetrics(font)
            if metrics.horizontalAdvance(text) <= available:
                chosen_size = size
                break
        return chosen_size

    def apply_title_font_size(self, size):
        text = self._label_text_full()
        font = self.lbl.font()
        font.setPointSize(int(size))
        self.lbl.setFont(font)
        self.lbl.setText(text)
        self.lbl.setToolTip(text)

    def _apply_label_fit(self):
        parent = self.parentWidget()
        while parent is not None and not hasattr(parent, "_sync_column_title_sizes"):
            parent = parent.parentWidget()
        if parent and hasattr(parent, "_sync_column_title_sizes"):
            parent._sync_column_title_sizes()
            return
        base_size = self._label_base_size
        available = self._title_available_width()
        if available > 0:
            base_size = int(round(max(self._label_min_size, min(self._label_base_size, available / 18))))
        chosen_size = self._fit_size_for_text(base_size)
        self.apply_title_font_size(chosen_size)

    def update_theme(self, theme):
        self.current_theme = theme
        is_today = self.is_today
        colors = get_theme(theme)
        color = colors["accent"] if is_today else colors["sub"]
        self._label_color = color
        self.lbl.setStyleSheet(f"font-weight: 900; color: {color}; margin-bottom: 8px; background: transparent; border: none;")
        accent_color = colors["accent"] if is_today else colors["border"]
        self.accent.setStyleSheet(f"background: {accent_color}; border-radius: 2px;")
        if theme == "Dark":
            self.panel.setStyleSheet(
                f"QFrame#DayPanel {{ background: {rgba(colors['card_alt'], 0.7)}; border: 1px solid {colors['border']}; border-radius: 18px; }}"
            )
        else:
            self.panel.setStyleSheet(
                f"QFrame#DayPanel {{ background: {rgba(colors['card'], 0.85)}; border: 1px solid {colors['border']}; border-radius: 18px; }}"
            )
        for card in self.cards:
            card.update_theme(theme)
        self._apply_label_fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_label_fit()

# --- MAIN PAGE ---
class TasksPage(QWidget):
    task_added = pyqtSignal()
    pomodoro_requested = pyqtSignal(int, str, str)

    def __init__(self):
        super().__init__()
        self.current_theme = "Light"
        self.task_reminders_enabled = True
        self.sound_effects = True
        self.enable_notifications = True
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(60 * 1000)  # check every minute
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._last_remind = {}  # map task_id -> datetime of last reminder
        self._reminder_repeat_minutes = 10
        self._tray = None
        self.columns = []
        self.empty_state = None
        self.empty_title = None
        self.empty_subtitle = None
        self.setObjectName("TasksPage")

        main = QVBoxLayout(self)
        main.setContentsMargins(40, 32, 40, 0)
        main.setSpacing(18)

        # Header
        self.header_frame = QFrame()
        self.header_frame.setObjectName("TasksHeader")
        header_layout = QGridLayout(self.header_frame)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(16)
        self.header_layout = header_layout

        txt_layout = QVBoxLayout()
        txt_layout.setSpacing(6)

        self.welcome = QLabel("WELCOME")
        self.title = QLabel("Your Creative Flow")
        self.title.setWordWrap(True)
        self.subtitle = QLabel("")
        self.subtitle.setWordWrap(True)

        txt_layout.addWidget(self.welcome)
        txt_layout.addWidget(self.title)
        txt_layout.addWidget(self.subtitle)
        self.header_text_layout = txt_layout

        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        self.chip_total = QLabel("0 tasks")
        self.chip_due = QLabel("0 due today")
        chips_layout.addWidget(self.chip_total)
        chips_layout.addWidget(self.chip_due)
        self.header_chips_layout = chips_layout

        btn_add = QPushButton("+ New Task")
        btn_add.setMinimumSize(120, 44)
        btn_add.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(STYLES["btn_primary"])
        shadow = QGraphicsDropShadowEffect(btn_add)
        shadow.setColor(QColor(48, 120, 205, 90))
        shadow.setBlurRadius(18)
        shadow.setYOffset(6)
        btn_add.setGraphicsEffect(shadow)
        btn_add.clicked.connect(self.prompt_new_task)

        self.header_add_btn = btn_add
        self._reflow_header()
        main.addWidget(self.header_frame)

        header_shadow = QGraphicsDropShadowEffect(self.header_frame)
        header_shadow.setColor(QColor(17, 51, 86, 30))
        header_shadow.setBlurRadius(20)
        header_shadow.setYOffset(6)
        self.header_frame.setGraphicsEffect(header_shadow)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal { height: 10px; background: rgba(15, 23, 42, 20); border-radius: 5px; }
            QScrollBar::handle:horizontal { background: rgba(48, 120, 205, 89); border-radius: 5px; }
            QScrollBar::handle:horizontal:hover { background: rgba(48, 120, 205, 140); }
        """)
        self.scroll = scroll

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.columns_layout = QGridLayout(container)
        self.columns_layout.setSpacing(12)
        self.columns_layout.setContentsMargins(0, 0, 0, 0)
        self.columns_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(container)
        main.addWidget(scroll)

        self.init_db()
        self.refresh_tasks()
        # Load settings (starts/stops reminder timer)
        try:
            self.apply_settings()
        except Exception:
            pass

    def showEvent(self, event):
        self.refresh_tasks()
        self._reflow_header()
        self._sync_column_title_sizes()
        super().showEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_columns()
        self._reflow_header()
        self._sync_column_title_sizes()

    def _sync_column_title_sizes(self):
        if not self.columns:
            return
        min_available = None
        for col in self.columns:
            try:
                available = col._title_available_width()
            except Exception:
                continue
            if available > 0 and (min_available is None or available < min_available):
                min_available = available
        if not min_available:
            return

        sample_col = self.columns[0]
        base_size = max(sample_col._label_min_size, min(sample_col._label_base_size, int(round(min_available / 18))))
        sizes = []
        for col in self.columns:
            try:
                sizes.append(col._fit_size_for_text(base_size))
            except Exception:
                pass
        if not sizes:
            return
        target_size = min(sizes)
        for col in self.columns:
            try:
                col.apply_title_font_size(target_size)
            except Exception:
                pass

    # --- THEME MANAGER ---
    def update_theme(self, theme):
        self.current_theme = theme
        colors = get_theme(theme)
        if theme == "Dark":
            page_bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors['bg']}, stop:1 {colors['card_alt']})"
            header_bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors['card_alt']}, stop:1 {colors['bg']})"
            chip_bg = colors["card_alt"]
            chip_border = colors["border"]
            chip_total_color = colors["text"]
            chip_due_color = colors["accent"]
        else:
            page_bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors['bg']}, stop:1 {colors['accent_soft']})"
            header_bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors['card']}, stop:1 {colors['accent_soft']})"
            chip_bg = colors["card"]
            chip_border = colors["border"]
            chip_total_color = colors["text"]
            chip_due_color = colors["deep"]

        self.setStyleSheet(
            "QWidget { font-family: '%s', 'Segoe UI'; }"
            "QWidget#TasksPage { background: %s; }" % (FONT_FAMILY, page_bg)
        )
        self.header_frame.setStyleSheet(
            "QFrame#TasksHeader { background: %s; border: 1px solid %s; border-radius: 18px; }" %
            (header_bg, colors["border"])
        )
        self.welcome.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {colors['accent']}; background: transparent; border: none;")
        self.title.setStyleSheet(f"font-size: 34px; font-weight: 900; color: {colors['text']}; background: transparent; border: none;")
        self.subtitle.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {colors['sub']}; background: transparent; border: none;")
        self.chip_total.setStyleSheet(
            "background: %s; color: %s; border: 1px solid %s; border-radius: 999px; padding: 7px 14px; font-size: 11px; font-weight: 700;" %
            (chip_bg, chip_total_color, chip_border)
        )
        self.chip_due.setStyleSheet(
            "background: %s; color: %s; border: 1px solid %s; border-radius: 999px; padding: 7px 14px; font-size: 11px; font-weight: 700;" %
            (chip_bg, chip_due_color, chip_border)
        )

        for col in self.columns:
            col.update_theme(theme)
        if self.empty_state:
            self._style_empty_state()

    def _build_empty_state(self):
        frame = QFrame()
        frame.setMinimumWidth(520)
        frame.setFixedHeight(220)
        frame.setObjectName("EmptyState")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(10)

        title = QLabel("No tasks yet")
        subtitle = QLabel("Create a new task to kick off your day with clarity.")
        subtitle.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        self.empty_state = frame
        self.empty_title = title
        self.empty_subtitle = subtitle
        self._style_empty_state()
        return frame

    def _style_empty_state(self):
        if not self.empty_state:
            return
        colors = get_theme(self.current_theme)
        if self.current_theme == "Dark":
            bg = rgba(colors["card_alt"], 0.75)
            border = colors["border"]
            title_color = colors["text"]
            sub_color = colors["sub"]
        else:
            bg = rgba(colors["card"], 0.9)
            border = colors["border"]
            title_color = colors["text"]
            sub_color = colors["sub"]

        self.empty_state.setStyleSheet(
            f"QFrame#EmptyState {{ background: {bg}; border: 1px dashed {border}; border-radius: 22px; }}"
        )
        self.empty_title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {title_color};")
        self.empty_subtitle.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {sub_color};")

    # --- BDD ---
    def get_db_connection(self):
        return sqlite3.connect("prodsmart.db")

    def init_db(self):
        conn = self.get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, description TEXT, due_date TEXT, priority TEXT,
                created_date TEXT, is_completed INTEGER DEFAULT 0,
                is_urgent INTEGER DEFAULT 0, is_important INTEGER DEFAULT 0
            )
        """)
        try: conn.execute("ALTER TABLE tasks ADD COLUMN created_date TEXT")
        except sqlite3.OperationalError: pass
        try: conn.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
        except sqlite3.OperationalError: pass
        conn.close()

    # --- Actions ---
    def prompt_new_task(self):
        dlg = AddTaskDialog(self, theme=self.current_theme)
        default_important = False
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    data = json.load(f)
                    if "default_important" in data:
                        default_important = bool(data.get("default_important", False))
                    else:
                        prio = str(data.get("default_priority", "")).strip().lower()
                        default_important = prio in ("high", "medium")
        except Exception:
            default_important = False
        try:
            dlg.important_check.setChecked(default_important)
        except Exception:
            pass
        if dlg.exec():
            data = dlg.get_data()
            if data['title']:
                self.save_task_to_db(data)
                self.refresh_tasks()
                self.task_added.emit()

    def show_task_details(self, t_id):
        conn = self.get_db_connection()
        row = conn.execute("SELECT title, description, due_date, created_date, is_urgent, is_important FROM tasks WHERE id=?", (t_id,)).fetchone()

        if row:
            created = row[3] if row[3] else "Unknown"
            urg, imp = row[4], row[5]
            if urg and imp: prio = "high"
            elif not urg and imp: prio = "medium"
            elif urg and not imp: prio = "low"
            else: prio = "too low"

            total_focus_min = 0
            total_sessions = 0
            sessions_widgets = []
            try:
                total_row = conn.execute(
                    "SELECT COALESCE(SUM(duration_min), 0), COUNT(*) FROM pomodoro_sessions WHERE task_id=? AND status='completed'",
                    (t_id,)
                ).fetchone()
                if total_row:
                    total_focus_min = int(total_row[0] or 0)

                total_sessions_row = conn.execute(
                    "SELECT COUNT(*) FROM pomodoro_sessions WHERE task_id=?",
                    (t_id,)
                ).fetchone()
                if total_sessions_row:
                    total_sessions = int(total_sessions_row[0] or 0)

                sess_rows = conn.execute(
                    "SELECT started_at, duration_min, status FROM pomodoro_sessions WHERE task_id=? ORDER BY started_at DESC",
                    (t_id,)
                ).fetchall()

                for started_at, duration_min, status in sess_rows:
                    display_time = "Unknown time"
                    if started_at:
                        raw = str(started_at).split(".")[0]
                        dt = None
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                            try:
                                dt = datetime.strptime(raw, fmt)
                                break
                            except ValueError:
                                continue
                        if dt:
                            display_time = dt.strftime("%b %d, %H:%M")
                    dur = int(duration_min or 0)
                    st = str(status or "").lower()
                    status_text = st if st else "completed"
                    lbl = QLabel(f"{display_time}  -  {dur} min  ({status_text})")
                    lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
                    sessions_widgets.append(lbl)
            except Exception:
                sessions_widgets = []
            finally:
                conn.close()

            ViewTaskDialog(
                row[0], row[1], row[2], created, prio,
                total_focus_min, total_sessions, sessions_widgets,
                self, theme=self.current_theme
            ).exec()
        else:
            conn.close()

    def edit_task(self, t_id):
        conn = self.get_db_connection()
        row = conn.execute("SELECT title, description, due_date, is_urgent, is_important FROM tasks WHERE id=?", (t_id,)).fetchone()
        conn.close()
        if row:
            dlg = AddTaskDialog(self, "Edit Task", theme=self.current_theme)
            dlg.load_data(row[0], row[1], row[2], row[4])
            if dlg.exec():
                data = dlg.get_data()
                self.update_task_in_db(t_id, data)
                self.refresh_tasks()
                self.task_added.emit()

    def delete_task(self, t_id):
        if QMessageBox.question(self, "Delete", "Remove this Task?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            conn = self.get_db_connection()
            conn.execute("DELETE FROM tasks WHERE id=?", (t_id,))
            conn.commit()
            conn.close()
            self.refresh_tasks()
            self.task_added.emit()

    def mark_task_completed(self, t_id, checked):
        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if checked else None
        conn = self.get_db_connection()
        conn.execute(
            "UPDATE tasks SET is_completed=?, completed_at=? WHERE id=?",
            (1 if checked else 0, completed_at, t_id)
        )
        conn.commit()
        conn.close()
        # Refresh UI so task disappears immediately when 'Show completed' is disabled
        try:
            self.refresh_tasks()
        except Exception:
            pass
        # Notify other pages (matrix, etc.) about the change
        try:
            self.task_added.emit()
        except Exception:
            pass
        # If completed, clear reminder tracking so it stops repeating
        try:
            if checked and t_id in self._last_remind:
                del self._last_remind[t_id]
        except Exception:
            pass

    # --- Helpers BDD ---
    def _deadline_is_urgent(self, due_date_str):
        if not due_date_str:
            return 0
        try:
            due = QDate.fromString(due_date_str, "yyyy-MM-dd")
        except Exception:
            return 0
        if not due.isValid():
            return 0
        today = QDate.currentDate()
        days_to = today.daysTo(due)
        return 1 if days_to <= 2 else 0

    def save_task_to_db(self, data):
        is_imp = 1 if data.get("important") else 0
        is_urg = self._deadline_is_urgent(data.get("date"))
        prio = quadrant_from_flags(is_urg, is_imp)

        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        conn = self.get_db_connection()
        conn.execute("INSERT INTO tasks (title, description, due_date, created_date, priority, is_urgent, is_important, is_completed) VALUES (?,?,?,?,?,?,?,0)",
                     (data['title'], data['description'], data['date'], today_str, prio, is_urg, is_imp))
        conn.commit()
        conn.close()

    def update_task_in_db(self, t_id, data):
        is_imp = 1 if data.get("important") else 0
        is_urg = self._deadline_is_urgent(data.get("date"))
        prio = quadrant_from_flags(is_urg, is_imp)

        conn = self.get_db_connection()
        conn.execute("UPDATE tasks SET title=?, description=?, due_date=?, priority=?, is_urgent=?, is_important=? WHERE id=?",
                     (data['title'], data['description'], data['date'], prio, is_urg, is_imp, t_id))
        conn.commit()
        conn.close()

    def refresh_tasks(self):
        while self.columns_layout.count():
            item = self.columns_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self.columns = []
        self.empty_state = None
        self.empty_title = None
        self.empty_subtitle = None

        conn = self.get_db_connection()
        try:
            # Respect user setting for showing completed tasks
            show_completed = True
            try:
                if os.path.exists("settings.json"):
                    with open("settings.json", "r") as sf:
                        sdata = json.load(sf)
                        show_completed = sdata.get("show_completed", True)
            except:
                pass

            if show_completed:
                rows = conn.execute(
                    "SELECT id, title, description, due_date, created_date, is_urgent, is_important, is_completed FROM tasks ORDER BY due_date"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, title, description, due_date, created_date, is_urgent, is_important, is_completed FROM tasks WHERE is_completed=0 ORDER BY due_date"
                ).fetchall()
            focus_rows = conn.execute(
                "SELECT task_id, COALESCE(SUM(duration_min), 0) "
                "FROM pomodoro_sessions "
                "WHERE status IN ('completed', 'stopped') "
                "GROUP BY task_id"
            ).fetchall()
        except:
            rows = []
            focus_rows = []
        conn.close()

        focus_map = {r[0]: int(r[1] or 0) for r in focus_rows}

        map_cols = {}
        total_tasks = len(rows)
        due_today = 0
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        self.subtitle.setText(QDate.currentDate().toString("dddd, d MMMM yyyy"))

        if total_tasks == 0:
            empty = self._build_empty_state()
            self.columns_layout.addWidget(empty, 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
            self.chip_total.setText("0 tasks")
            self.chip_due.setText("0 due today")
            return

        for row in rows:
            t_id, title, desc, due_date_str, created_date_str, urg, imp, is_completed = row

            priority = quadrant_from_flags(urg, imp)

            if not due_date_str: pretty_due = "No Deadline"
            else: pretty_due = QDate.fromString(due_date_str, "yyyy-MM-dd").toString("dddd d MMMM yyyy")

            if not created_date_str: pretty_created = "Unknown"
            else: pretty_created = QDate.fromString(created_date_str, "yyyy-MM-dd").toString("d MMM yyyy")

            if due_date_str == today_str:
                due_today += 1

            if pretty_due not in map_cols:
                is_today = (due_date_str == today_str)
                col = DayColumn(pretty_due, is_today, theme=self.current_theme)
                map_cols[pretty_due] = col
                self.columns.append(col)

            focus_minutes = focus_map.get(t_id, 0)
            card = TaskCard(t_id, title, desc, pretty_due, pretty_created, priority, focus_minutes, self, is_completed)
            card.update_theme(self.current_theme)
            map_cols[pretty_due].add_task_card(card)

        self._reflow_columns()
        self.chip_total.setText(f"{total_tasks} tasks")
        self.chip_due.setText(f"{due_today} due today")

    def _reflow_columns(self):
        if not hasattr(self, "columns_layout") or not self.columns:
            return
        layout = self.columns_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() and item.widget() not in self.columns:
                item.widget().deleteLater()

        try:
            available = self.scroll.viewport().width()
        except Exception:
            available = self.width()
        margins = layout.contentsMargins()
        available = max(1, available - margins.left() - margins.right())
        spacing = layout.spacing()
        min_col_width = 280
        cols_per_row = max(1, int((available + spacing) // (min_col_width + spacing)))

        for idx, col in enumerate(self.columns):
            row = idx // cols_per_row
            col_idx = idx % cols_per_row
            layout.addWidget(col, row, col_idx)

        for col_idx in range(cols_per_row):
            layout.setColumnStretch(col_idx, 1)
        self._sync_column_title_sizes()

    def _reflow_header(self):
        if not hasattr(self, "header_layout"):
            return
        layout = self.header_layout
        while layout.count():
            layout.takeAt(0)
        width = self.header_frame.width() if hasattr(self, "header_frame") else self.width()
        narrow = width < 760

        if narrow:
            layout.addLayout(self.header_text_layout, 0, 0, 1, 2)
            layout.addWidget(self.header_add_btn, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addLayout(self.header_chips_layout, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
            layout.setColumnStretch(0, 1)
        else:
            layout.addLayout(self.header_text_layout, 0, 0)
            layout.addLayout(self.header_chips_layout, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addWidget(self.header_add_btn, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)
            layout.setColumnStretch(0, 1)

    # --- REMINDER HELPERS ---
    def _ensure_tray(self):
        if self._tray is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ProdSmart.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setVisible(True)

    def _show_notification(self, title, message):
        if not getattr(self, "enable_notifications", True):
            return
        self._ensure_tray()
        if self._tray:
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            # Avoid modal popups that can flash during page switches.
            # If tray isn't available, skip the popup.
            pass

    def apply_settings(self):
        """Load settings.json and enable/disable reminders and sounds accordingly."""
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    data = json.load(f)
                    self.task_reminders_enabled = data.get("task_reminders", True)
                    self.enable_notifications = data.get("enable_notifications", True)
                    self.sound_effects = data.get("sound_effects", True)
                    self._reminder_repeat_minutes = int(data.get("reminder_repeat_minutes", 10))
            else:
                # defaults
                self.task_reminders_enabled = True
                self.enable_notifications = True
                self.sound_effects = True
        except Exception:
            self.task_reminders_enabled = True
            self.enable_notifications = True
            self.sound_effects = True

        # Setup sound
        try:
            sound_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "alarm.wav")
            self._reminder_sound = QSoundEffect(self)
            if os.path.exists(sound_path):
                self._reminder_sound.setSource(QUrl.fromLocalFile(sound_path))
                self._reminder_sound.setVolume(0.6)
            else:
                self._reminder_sound = None
        except Exception:
            self._reminder_sound = None

        # Start/stop timer
        try:
            if self.task_reminders_enabled and self.enable_notifications:
                if not self._reminder_timer.isActive():
                    self._reminder_timer.start()
            else:
                if self._reminder_timer.isActive():
                    self._reminder_timer.stop()
        except Exception:
            pass

    def _check_reminders(self):
        """Check DB for tasks due today and not completed; show reminder once per task per session."""
        if not getattr(self, "task_reminders_enabled", True):
            return
        if not getattr(self, "enable_notifications", True):
            return

        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        conn = self.get_db_connection()
        try:
            rows = conn.execute(
                "SELECT id, title FROM tasks WHERE due_date=? AND is_completed=0",
                (today_str,)
            ).fetchall()
        except Exception:
            rows = []
        conn.close()

        from datetime import datetime
        for r in rows:
            try:
                t_id = r[0]
                title = r[1]
                now = datetime.now()
                last = self._last_remind.get(t_id)
                should_remind = False
                if last is None:
                    should_remind = True
                else:
                    elapsed = (now - last).total_seconds() / 60.0
                    if elapsed >= (self._reminder_repeat_minutes or 10):
                        should_remind = True

                if not should_remind:
                    continue

                # Play sound if enabled
                if self.sound_effects and getattr(self, "_reminder_sound", None):
                    try:
                        self._reminder_sound.play()
                    except Exception:
                        pass

                # Show reminder notification
                try:
                    self._show_notification("Task Reminder", f"Reminder: '{title}' is due today.")
                except Exception:
                    pass

                # Record last remind time
                self._last_remind[t_id] = now
            except Exception:
                continue

    def start_pomodoro(self, t_id, title, priority=None):
        prio = normalize_priority(priority) or "too low"
        self.pomodoro_requested.emit(t_id, title, prio)
