import sqlite3
import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QPushButton, QScrollArea, QDialog,
                             QLineEdit, QDateEdit, QComboBox, QMessageBox,
                             QCheckBox, QGraphicsDropShadowEffect, QSizePolicy)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor

# --- STYLES HELPER ---
def get_dialog_style(theme):
    if theme == "Dark":
        return """
            QDialog { background-color: #113356; }
            QLabel { color: #e6eef5; font-weight: 600; font-size: 13px; padding-top: 10px; }
            QLineEdit, QDateEdit, QComboBox {
                background-color: #1b2f4d; border: 1px solid #25456B;
                border-radius: 10px; padding: 10px; font-size: 14px; color: white;
            }
            QLineEdit:focus, QDateEdit:focus { border: 1px solid #82AFF2; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #1b2f4d; color: white; selection-background-color: #3078CD; }
        """
    else:
        return """
            QDialog { background-color: #F8F6F2; }
            QLabel { color: #25456B; font-weight: 600; font-size: 13px; padding-top: 10px; }
            QLineEdit, QDateEdit, QComboBox {
                background-color: #ffffff; border: 1px solid #BAD2E0;
                border-radius: 10px; padding: 10px; font-size: 14px; color: #113356;
            }
            QLineEdit:focus, QDateEdit:focus { border: 1px solid #3078CD; background: white; }
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

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Add details...")
        layout.addWidget(self.desc_input)

        lbl_due = QLabel("Deadline:")
        layout.addWidget(lbl_due)

        row = QHBoxLayout()
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())

        self.priority_input = QComboBox()
        self.priority_input.addItem("Too Low (Delete)", "too low")
        self.priority_input.addItem("Low (Delegate)", "low")
        self.priority_input.addItem("Medium (Schedule)", "medium")
        self.priority_input.addItem("High (Do First)", "high")

        # --- NEW LOGIC: READ FROM SETTINGS ---
        default_index = 2 # fallback is Medium
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    data = json.load(f)
                    prio_setting = data.get("default_priority", "Medium")

                    # Map settings text to dropdown index
                    if prio_setting == "Too Low": default_index = 0
                    elif prio_setting == "Low": default_index = 1
                    elif prio_setting == "Medium": default_index = 2
                    elif prio_setting == "High": default_index = 3
        except:
            pass # Use default Medium if error

        self.priority_input.setCurrentIndex(default_index)

        row.addWidget(self.date_input)
        row.addWidget(self.priority_input)
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

    def load_data(self, title, desc, date_str, priority):
        self.title_input.setText(title)
        self.desc_input.setText(desc)
        if date_str: self.date_input.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        idx = self.priority_input.findData(priority)
        if idx >= 0: self.priority_input.setCurrentIndex(idx)

    def get_data(self):
        return {
            "title": self.title_input.text(),
            "description": self.desc_input.text(),
            "date": self.date_input.date().toString("yyyy-MM-dd"),
            "priority": self.priority_input.currentData()
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
    def __init__(self, t_id, title, desc, due_date_pretty, created_date_pretty, priority, focus_minutes, parent_page):
        super().__init__()
        self.t_id = t_id
        self.parent_page = parent_page
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(300)
        self.setObjectName("TaskCard")

        self.priority = priority
        self.title_text = title
        self.current_theme = "Light"
        self.accent_color = PRIORITY_COLORS.get(priority.lower(), "#94a3b8")
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

        self.accent_bar = QFrame()
        self.accent_bar.setFixedWidth(6)
        self.accent_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.accent_bar.setObjectName("TaskAccent")

        accent_container = QWidget()
        accent_container.setFixedWidth(12)
        accent_layout = QVBoxLayout(accent_container)
        accent_layout.setContentsMargins(6, 12, 0, 12)
        accent_layout.addWidget(self.accent_bar)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 18, 18, 18)
        layout.setSpacing(10)

        outer.addWidget(accent_container)
        outer.addWidget(content)

        # Header
        header = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.toggled.connect(self.on_checked)

        self.badge = QLabel(priority.upper())
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(78, 22)
        self.badge.setStyleSheet("font-size: 9px; font-weight: 900;")

        header.addWidget(self.checkbox)
        header.addStretch()
        header.addWidget(self.badge)
        layout.addLayout(header)

        self.lbl_title = QLabel(title)
        self.lbl_title.setWordWrap(True)
        layout.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(desc if desc else "")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setMaximumHeight(40)
        self.lbl_desc.setVisible(bool(desc))
        layout.addWidget(self.lbl_desc)

        footer = QVBoxLayout()
        footer.setSpacing(8)
        dates_layout = QVBoxLayout()
        dates_layout.setSpacing(2)

        self.lbl_created = QLabel(f"Created: {created_date_pretty}")
        self.lbl_created.setWordWrap(True)
        self.lbl_created.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.lbl_due = QLabel(f"Due: {due_date_pretty}")
        self.lbl_due.setWordWrap(True)
        self.lbl_due.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        dates_layout.addWidget(self.lbl_created)
        dates_layout.addWidget(self.lbl_due)

        self.lbl_focus = QLabel(f"Focus: {self.focus_minutes} min")
        self.lbl_focus.setWordWrap(True)
        self.lbl_focus.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        dates_layout.addWidget(self.lbl_focus)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)
        self.btn_edit = QPushButton("EDIT")
        self.btn_edit.setFixedHeight(20)
        self.btn_edit.setMinimumWidth(52)
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setStyleSheet(
            "QPushButton { background: #3078CD; border: 1px solid #25456B; color: white; "
            "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
            "QPushButton:hover { background: #25456B; border-color: #25456B; }"
        )
        self.btn_edit.clicked.connect(self.on_edit)

        self.btn_del = QPushButton("DELETE")
        self.btn_del.setFixedHeight(20)
        self.btn_del.setMinimumWidth(60)
        self.btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del.setStyleSheet(
            "QPushButton { background: #ef4444; border: 1px solid #b91c1c; color: white; "
            "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
            "QPushButton:hover { background: #b91c1c; border-color: #7f1d1d; }"
        )
        self.btn_del.clicked.connect(self.on_delete)

        self.btn_focus = QPushButton("FOCUS")
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

        self.update_theme("Light")

    def _apply_text_styles(self, checked=False):
        checked_color = "#22c55e"
        if self.current_theme == "Dark":
            title_color = checked_color if checked else "#F8F6F2"
            desc_color = "#BAD2E0" if not checked else checked_color
        else:
            title_color = checked_color if checked else "#113356"
            desc_color = checked_color if checked else "#25456B"

        self.lbl_title.setStyleSheet(f"color: {title_color}; font-size: 15px; font-weight: 800; border: none; background: transparent;")
        self.lbl_desc.setStyleSheet(f"color: {desc_color}; font-size: 11px; border: none; background: transparent;")

    def update_theme(self, theme):
        self.current_theme = theme
        accent = self.accent_color
        if theme == "Dark":
            card_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #162b45, stop:1 #0f2238)"
            border = "#25456B"
            hover_border = "#82AFF2"
            created_color = "#9bb5cc"
            due_color = "#82AFF2"
            focus_color = "#7dd3fc"
            checkbox_border = "#315a85"
            checkbox_bg = "#0f2238"
            edit_style = (
                "QPushButton { background: #3078CD; border: 1px solid #1f3a5a; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background: #25456B; border-color: #25456B; }"
            )
            del_style = (
                "QPushButton { background: #ef4444; border: 1px solid #7f1d1d; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background: #b91c1c; border-color: #7f1d1d; }"
            )
            focus_style = (
                "QPushButton { background: #22c55e; border: 1px solid #15803d; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background: #16a34a; border-color: #166534; }"
            )
        else:
            card_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #F5F9FD)"
            border = "#D7E3EE"
            hover_border = "#3078CD"
            created_color = "#6e90ad"
            due_color = "#25456B"
            focus_color = "#2563eb"
            checkbox_border = "#BAD2E0"
            checkbox_bg = "#ffffff"
            edit_style = (
                "QPushButton { background: #3078CD; border: 1px solid #25456B; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background: #25456B; border-color: #25456B; }"
            )
            del_style = (
                "QPushButton { background: #ef4444; border: 1px solid #b91c1c; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background: #b91c1c; border-color: #7f1d1d; }"
            )
            focus_style = (
                "QPushButton { background: #22c55e; border: 1px solid #16a34a; color: white; "
                "border-radius: 8px; font-weight: bold; font-size: 10px; padding: 0px 10px; }"
                "QPushButton:hover { background: #16a34a; border-color: #166534; }"
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
    def on_focus(self): self.parent_page.start_pomodoro(self.t_id, self.title_text)

# --- COLUMNS ---
class DayColumn(QWidget):
    def __init__(self, title, is_today=False, theme="Light"):
        super().__init__()
        self.setFixedWidth(340)
        self.cards = []
        self.title = title
        self.count = 0
        self.is_today = is_today
        self.current_theme = theme
        self.setObjectName("DayColumn")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("DayPanel")
        self.panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.lbl = QLabel(title)
        layout.addWidget(self.lbl)

        self.accent = QFrame()
        self.accent.setFixedHeight(3)
        self.accent.setMaximumWidth(70)
        layout.addWidget(self.accent)

        self.card_layout = QVBoxLayout()
        self.card_layout.setSpacing(16)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
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
        suffix = "task" if self.count == 1 else "tasks"
        self.lbl.setText(f"{self.title}  -  {self.count} {suffix}")

    def update_theme(self, theme):
        self.current_theme = theme
        is_today = self.is_today
        color = "#3078CD" if is_today else ("#BAD2E0" if theme == "Dark" else "#25456B")
        self.lbl.setStyleSheet(f"font-size: 16px; font-weight: 900; color: {color}; margin-bottom: 8px; background: transparent; border: none;")
        accent_color = "#3078CD" if is_today else ("#25456B" if theme == "Dark" else "#BAD2E0")
        self.accent.setStyleSheet(f"background: {accent_color}; border-radius: 2px;")
        if theme == "Dark":
            self.panel.setStyleSheet(
                "QFrame#DayPanel { background: rgba(15, 34, 56, 0.55); border: 1px solid #25456B; border-radius: 18px; }"
            )
        else:
            self.panel.setStyleSheet(
                "QFrame#DayPanel { background: rgba(255, 255, 255, 0.7); border: 1px solid #D7E3EE; border-radius: 18px; }"
            )
        for card in self.cards:
            card.update_theme(theme)

# --- MAIN PAGE ---
class TasksPage(QWidget):
    task_added = pyqtSignal()
    pomodoro_requested = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()
        self.current_theme = "Light"
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
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(16)

        txt_layout = QVBoxLayout()
        txt_layout.setSpacing(6)

        self.welcome = QLabel("WELCOME")
        self.title = QLabel("Your Creative Flow")
        self.subtitle = QLabel("")

        txt_layout.addWidget(self.welcome)
        txt_layout.addWidget(self.title)
        txt_layout.addWidget(self.subtitle)
        header_layout.addLayout(txt_layout)
        header_layout.addStretch()

        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        self.chip_total = QLabel("0 tasks")
        self.chip_due = QLabel("0 due today")
        chips_layout.addWidget(self.chip_total)
        chips_layout.addWidget(self.chip_due)

        btn_add = QPushButton("+ New Task")
        btn_add.setFixedSize(150, 44)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(STYLES["btn_primary"])
        shadow = QGraphicsDropShadowEffect(btn_add)
        shadow.setColor(QColor(48, 120, 205, 90))
        shadow.setBlurRadius(18)
        shadow.setYOffset(6)
        btn_add.setGraphicsEffect(shadow)
        btn_add.clicked.connect(self.prompt_new_task)

        header_layout.addLayout(chips_layout)
        header_layout.addWidget(btn_add)
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
            QScrollBar:horizontal { height: 10px; background: rgba(15, 23, 42, 0.08); border-radius: 5px; }
            QScrollBar::handle:horizontal { background: rgba(48, 120, 205, 0.35); border-radius: 5px; }
            QScrollBar::handle:horizontal:hover { background: rgba(48, 120, 205, 0.55); }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.columns_layout = QHBoxLayout(container)
        self.columns_layout.setSpacing(12)
        self.columns_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        scroll.setWidget(container)
        main.addWidget(scroll)

        self.init_db()
        self.refresh_tasks()

    def showEvent(self, event):
        self.refresh_tasks()
        super().showEvent(event)

    # --- THEME MANAGER ---
    def update_theme(self, theme):
        self.current_theme = theme
        if theme == "Dark":
            self.setStyleSheet(
                "QWidget { font-family: 'Poppins', 'Segoe UI', 'Arial'; }"
                "QWidget#TasksPage { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f2238, stop:1 #183151); }"
            )
            self.header_frame.setStyleSheet(
                "QFrame#TasksHeader { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #162b45, stop:1 #0f2238); "
                "border: 1px solid #25456B; border-radius: 18px; }"
            )
            self.welcome.setStyleSheet("font-size: 11px; font-weight: 800; color: #BAD2E0; background: transparent; border: none;")
            self.title.setStyleSheet("font-size: 34px; font-weight: 900; color: #F8F6F2; background: transparent; border: none;")
            self.subtitle.setStyleSheet("font-size: 13px; font-weight: 600; color: #AFC4D8; background: transparent; border: none;")
            self.chip_total.setStyleSheet("background: #0f2238; color: #F8F6F2; border: 1px solid #25456B; border-radius: 999px; padding: 7px 14px; font-size: 11px; font-weight: 700;")
            self.chip_due.setStyleSheet("background: #0f2238; color: #82AFF2; border: 1px solid #25456B; border-radius: 999px; padding: 7px 14px; font-size: 11px; font-weight: 700;")
        else:
            self.setStyleSheet(
                "QWidget { font-family: 'Poppins', 'Segoe UI', 'Arial'; }"
                "QWidget#TasksPage { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F4F7FB, stop:1 #E5EEF7); }"
            )
            self.header_frame.setStyleSheet(
                "QFrame#TasksHeader { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFFFFF, stop:1 #EFF5FB); "
                "border: 1px solid #D7E3EE; border-radius: 18px; }"
            )
            self.welcome.setStyleSheet("font-size: 11px; font-weight: 800; color: #3078CD; background: transparent; border: none;")
            self.title.setStyleSheet("font-size: 34px; font-weight: 900; color: #113356; background: transparent; border: none;")
            self.subtitle.setStyleSheet("font-size: 13px; font-weight: 600; color: #47617c; background: transparent; border: none;")
            self.chip_total.setStyleSheet("background: #FFFFFF; color: #113356; border: 1px solid #D7E3EE; border-radius: 999px; padding: 7px 14px; font-size: 11px; font-weight: 700;")
            self.chip_due.setStyleSheet("background: #EFF5FB; color: #25456B; border: 1px solid #D7E3EE; border-radius: 999px; padding: 7px 14px; font-size: 11px; font-weight: 700;")

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
        if self.current_theme == "Dark":
            bg = "rgba(15, 34, 56, 0.7)"
            border = "#25456B"
            title_color = "#F8F6F2"
            sub_color = "#AFC4D8"
        else:
            bg = "rgba(255, 255, 255, 0.85)"
            border = "#D7E3EE"
            title_color = "#113356"
            sub_color = "#47617c"

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
            urg, imp = row[3], row[4]
            if urg and imp: prio = "high"
            elif not urg and imp: prio = "medium"
            elif urg and not imp: prio = "low"
            else: prio = "too low"

            dlg = AddTaskDialog(self, "Edit Task", theme=self.current_theme)
            dlg.load_data(row[0], row[1], row[2], prio)
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

    # --- Helpers BDD ---
    def save_task_to_db(self, data):
        is_urg = 1 if data["priority"] in ['high', 'low'] else 0
        is_imp = 1 if data["priority"] in ['high', 'medium'] else 0

        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        conn = self.get_db_connection()
        conn.execute("INSERT INTO tasks (title, description, due_date, created_date, priority, is_urgent, is_important, is_completed) VALUES (?,?,?,?,?,?,?,0)",
                     (data['title'], data['description'], data['date'], today_str, data['priority'], is_urg, is_imp))
        conn.commit()
        conn.close()

    def update_task_in_db(self, t_id, data):
        is_urg = 1 if data["priority"] in ['high', 'low'] else 0
        is_imp = 1 if data["priority"] in ['high', 'medium'] else 0

        conn = self.get_db_connection()
        conn.execute("UPDATE tasks SET title=?, description=?, due_date=?, priority=?, is_urgent=?, is_important=? WHERE id=?",
                     (data['title'], data['description'], data['date'], data['priority'], is_urg, is_imp, t_id))
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
            rows = conn.execute(
                "SELECT id, title, description, due_date, created_date, is_urgent, is_important FROM tasks WHERE is_completed=0 ORDER BY due_date"
            ).fetchall()
            focus_rows = conn.execute(
                "SELECT task_id, COALESCE(SUM(duration_min), 0) FROM pomodoro_sessions WHERE status='completed' GROUP BY task_id"
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
            self.columns_layout.addWidget(empty)
            self.columns_layout.addStretch()
            self.chip_total.setText("0 tasks")
            self.chip_due.setText("0 due today")
            return

        for row in rows:
            t_id, title, desc, due_date_str, created_date_str, urg, imp = row

            if urg == 1 and imp == 1: priority = "high"
            elif urg == 0 and imp == 1: priority = "medium"
            elif urg == 1 and imp == 0: priority = "low"
            else: priority = "too low"

            if not due_date_str: pretty_due = "No Deadline"
            else: pretty_due = QDate.fromString(due_date_str, "yyyy-MM-dd").toString("dddd d MMMM yyyy")

            if not created_date_str: pretty_created = "Unknown"
            else: pretty_created = QDate.fromString(created_date_str, "yyyy-MM-dd").toString("d MMM yyyy")

            if due_date_str == today_str:
                due_today += 1

            if pretty_due not in map_cols:
                is_today = (due_date_str == today_str)
                col = DayColumn(pretty_due, is_today, theme=self.current_theme)
                self.columns_layout.addWidget(col)
                map_cols[pretty_due] = col
                self.columns.append(col)

            focus_minutes = focus_map.get(t_id, 0)
            card = TaskCard(t_id, title, desc, pretty_due, pretty_created, priority, focus_minutes, self)
            card.update_theme(self.current_theme)
            map_cols[pretty_due].add_task_card(card)

        self.columns_layout.addStretch()
        self.chip_total.setText(f"{total_tasks} tasks")
        self.chip_due.setText(f"{due_today} due today")

    def start_pomodoro(self, t_id, title):
        self.pomodoro_requested.emit(t_id, title)
