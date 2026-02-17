import sqlite3
import json
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QPushButton, QScrollArea, QDialog, 
                             QLineEdit, QDateEdit, QComboBox, QMessageBox, 
                             QCheckBox, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor

# --- STYLES HELPER ---
def get_dialog_style(theme):
    if theme == "Dark":
        return """
            QDialog { background-color: #2d2d2d; }
            QLabel { color: #e0e0e0; font-weight: 600; font-size: 13px; margin-top: 10px; }
            QLineEdit, QDateEdit, QComboBox { 
                background-color: #404040; border: 1px solid #555; 
                border-radius: 10px; padding: 10px; font-size: 14px; color: white; 
            }
            QLineEdit:focus, QDateEdit:focus { border: 1px solid #3b82f6; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #404040; color: white; selection-background-color: #3b82f6; }
        """
    else:
        return """
            QDialog { background-color: #ffffff; }
            QLabel { color: #4a5568; font-weight: 600; font-size: 13px; margin-top: 10px; }
            QLineEdit, QDateEdit, QComboBox { 
                background-color: #f7fafc; border: 1px solid #e2e8f0; 
                border-radius: 10px; padding: 10px; font-size: 14px; color: #2d3748; 
            }
            QLineEdit:focus, QDateEdit:focus { border: 1px solid #3182ce; background: white; }
        """

STYLES = {
    "btn_primary": """
        QPushButton { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3182ce, stop:1 #4fd1c5); 
            color: white; border-radius: 12px; font-weight: bold; font-size: 14px; border: none; 
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2b6cb0, stop:1 #38b2ac); }
        QPushButton:pressed { margin-top: 2px; }
    """,
    "btn_secondary": """
        QPushButton { 
            background-color: transparent; color: #718096; border: 1px solid #cbd5e0; 
            border-radius: 12px; padding: 8px 16px; font-weight: 600; 
        }
        QPushButton:hover { background-color: #edf2f7; color: #2d3748; border-color: #a0aec0; }
    """
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
        lbl_head.setStyleSheet("color: #3b82f6; font-size: 12px; font-weight: 800; letter-spacing: 1px;")
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
        self.priority_input.addItem("⬇️ Too Low (Delete)", "too low")
        self.priority_input.addItem("⚪ Low (Delegate)", "low")
        self.priority_input.addItem("🔶 Medium (Schedule)", "medium")
        self.priority_input.addItem("🔥 High (Do First)", "high")
        
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
    def __init__(self, title, desc, due_date, created_date, priority, parent=None, theme="Light"):
        super().__init__(parent)
        self.setWindowTitle("Task Details")
        self.setFixedWidth(400)
        
        bg = "#2d2d2d" if theme == "Dark" else "white"
        txt = "white" if theme == "Dark" else "#2d3748"
        box_bg = "#404040" if theme == "Dark" else "#f7fafc"
        
        self.setStyleSheet(f"QDialog {{ background-color: {bg}; }} QLabel {{ color: {txt}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        p_colors = {"high": "#e53e3e", "medium": "#dd6b20", "low": "#38a169", "too low": "#718096"}
        c = p_colors.get(priority, "#718096")
        lbl_p = QLabel(priority.upper())
        lbl_p.setStyleSheet(f"color: {c}; font-weight: 900; letter-spacing: 1px; font-size: 11px;")
        layout.addWidget(lbl_p)

        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet(f"font-size: 22px; font-weight: 800; margin-top: 5px; color: {txt};")
        layout.addWidget(t)

        dates_row = QHBoxLayout()
        c_lbl = QLabel(f"🌱 Created: {created_date}")
        c_lbl.setStyleSheet("color: #a0aec0; font-size: 12px;")
        d_lbl = QLabel(f"⏰ Due: {due_date}")
        d_lbl.setStyleSheet("color: #e53e3e; font-size: 12px; font-weight: bold;")
        
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
        lbl_desc.setStyleSheet(f"color: {txt}; line-height: 1.4;")
        dl.addWidget(lbl_desc)
        layout.addWidget(desc_box)

        layout.addSpacing(20)
        btn = QPushButton("Close")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(STYLES["btn_secondary"])
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

# --- TASK CARD ---
class TaskCard(QFrame):
    def __init__(self, t_id, title, desc, due_date_pretty, created_date_pretty, priority, parent_page):
        super().__init__()
        self.t_id = t_id
        self.parent_page = parent_page
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(280)
        
        self.priority = priority
        self.title_text = title
        self.current_theme = "Light"

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(8)
        self.shadow.setColor(QColor(0, 0, 0, 15))
        self.setGraphicsEffect(self.shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 6px; border: 2px solid #cbd5e0; }
            QCheckBox::indicator:checked { background-color: #48bb78; border-color: #48bb78; }
        """)
        self.checkbox.toggled.connect(self.on_checked)
        
        badges = {
            "high": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff416c, stop:1 #ff4b2b)",
            "medium": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f2994a, stop:1 #f2c94c)",
            "low": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #56ab2f, stop:1 #a8e063)",
            "too low": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #bdc3c7, stop:1 #2c3e50)"
        }
        bg_style = badges.get(priority.lower(), "#cbd5e0")
        
        self.badge = QLabel(priority.upper())
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(60, 20)
        self.badge.setStyleSheet(f"background: {bg_style}; color: white; border-radius: 10px; font-size: 9px; font-weight: 900;")

        header.addWidget(self.checkbox)
        header.addStretch()
        header.addWidget(self.badge)
        layout.addLayout(header)

        self.lbl_title = QLabel(title)
        self.lbl_title.setWordWrap(True)
        layout.addWidget(self.lbl_title)

        footer = QHBoxLayout()
        dates_layout = QVBoxLayout()
        dates_layout.setSpacing(2)
        
        lbl_created = QLabel(f"🌱 {created_date_pretty}")
        lbl_created.setStyleSheet("color: #a0aec0; font-size: 10px; border: none; background: transparent;")
        
        lbl_due = QLabel(f"⏰ {due_date_pretty}")
        lbl_due.setStyleSheet("color: #e53e3e; font-size: 11px; font-weight: 700; border: none; background: transparent;")
        
        dates_layout.addWidget(lbl_created)
        dates_layout.addWidget(lbl_due)
        
        actions_layout = QHBoxLayout()
        self.btn_edit = QPushButton("✏️")
        self.btn_edit.setFixedSize(25, 25)
        self.btn_edit.setStyleSheet("background: transparent; border: none;")
        self.btn_edit.clicked.connect(self.on_edit)
        
        self.btn_del = QPushButton("🗑️")
        self.btn_del.setFixedSize(25, 25)
        self.btn_del.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { color: red; }")
        self.btn_del.clicked.connect(self.on_delete)

        actions_layout.addWidget(self.btn_edit)
        actions_layout.addWidget(self.btn_del)

        footer.addLayout(dates_layout)
        footer.addStretch()
        footer.addLayout(actions_layout)
        layout.addLayout(footer)
        
        self.update_theme("Light")

    def update_theme(self, theme):
        self.current_theme = theme
        if theme == "Dark":
            self.setStyleSheet("""
                QFrame { background-color: #2d2d2d; border: 1px solid #404040; border-radius: 20px; }
                QFrame:hover { border: 1px solid #3b82f6; }
            """)
            self.lbl_title.setStyleSheet("color: #e0e0e0; font-size: 15px; font-weight: 700; border: none; background: transparent;")
        else:
            self.setStyleSheet("""
                QFrame { background-color: white; border: 1px solid #f0f4f8; border-radius: 20px; }
                QFrame:hover { border: 1px solid #63b3ed; }
            """)
            self.lbl_title.setStyleSheet("color: #2d3748; font-size: 15px; font-weight: 700; border: none; background: transparent;")

    def enterEvent(self, event):
        self.shadow.setColor(QColor(59, 130, 246, 60)) 
        self.shadow.setBlurRadius(30)
        self.shadow.setYOffset(12)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.shadow.setColor(QColor(0, 0, 0, 15))
        self.shadow.setBlurRadius(20)
        self.shadow.setYOffset(8)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_page.show_task_details(self.t_id)
        super().mousePressEvent(event)

    def on_checked(self, checked):
        f = self.lbl_title.font()
        f.setStrikeOut(checked)
        self.lbl_title.setFont(f)
        color = '#718096' if checked else ('#e0e0e0' if self.current_theme == "Dark" else '#2d3748')
        self.lbl_title.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 700; border: none; background: transparent;")
        self.parent_page.mark_task_completed(self.t_id, checked)
        self.parent_page.task_added.emit()

    def on_edit(self): self.parent_page.edit_task(self.t_id)
    def on_delete(self): self.parent_page.delete_task(self.t_id)

# --- COLUMNS ---
class DayColumn(QWidget):
    def __init__(self, title, is_today=False, theme="Light"):
        super().__init__()
        self.setFixedWidth(300)
        self.cards = [] 
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 0, 15, 0)
        
        self.head_color = "#3b82f6" if is_today else ("#a0aec0" if theme == "Dark" else "#718096")
        self.lbl = QLabel(title)
        self.lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {self.head_color}; margin-bottom: 10px;")
        layout.addWidget(self.lbl)

        self.card_layout = QVBoxLayout()
        self.card_layout.setSpacing(15)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        layout.addLayout(self.card_layout)
        layout.addStretch()

    def add_task_card(self, card):
        self.cards.append(card)
        self.card_layout.addWidget(card)

    def update_theme(self, theme):
        is_today = (self.head_color == "#3b82f6")
        color = "#3b82f6" if is_today else ("#a0aec0" if theme == "Dark" else "#718096")
        self.lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {color}; margin-bottom: 10px;")
        for card in self.cards:
            card.update_theme(theme)

# --- MAIN PAGE ---
class TasksPage(QWidget):
    task_added = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_theme = "Light"
        self.columns = []

        main = QVBoxLayout(self)
        main.setContentsMargins(50, 40, 50, 0)
        main.setSpacing(20)

        # Header
        top_bar = QHBoxLayout()
        txt_layout = QVBoxLayout()
        
        self.welcome = QLabel("Welcome ✨")
        self.title = QLabel("Your Creative Flow")
        
        txt_layout.addWidget(self.welcome)
        txt_layout.addWidget(self.title)
        top_bar.addLayout(txt_layout)
        top_bar.addStretch()

        btn_add = QPushButton("+ New Task")
        btn_add.setFixedSize(140, 45)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(STYLES["btn_primary"])
        shadow = QGraphicsDropShadowEffect(btn_add)
        shadow.setColor(QColor(49, 130, 206, 80))
        shadow.setBlurRadius(15)
        shadow.setYOffset(4)
        btn_add.setGraphicsEffect(shadow)
        btn_add.clicked.connect(self.prompt_new_task)
        
        top_bar.addWidget(btn_add)
        main.addLayout(top_bar)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal { height: 8px; background: rgba(0,0,0,0.1); border-radius: 4px; }
            QScrollBar::handle:horizontal { background: rgba(0,0,0,0.2); border-radius: 4px; }
        """)
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.columns_layout = QHBoxLayout(container)
        self.columns_layout.setSpacing(10)
        self.columns_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
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
            self.setStyleSheet("background-color: #121212;") 
            self.welcome.setStyleSheet("font-size: 12px; font-weight: 800; color: #60a5fa; text-transform: uppercase; letter-spacing: 2px;")
            self.title.setStyleSheet("font-size: 32px; font-weight: 900; color: #e0e0e0;")
        else:
            self.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fdfbfb, stop:1 #ebedee);")
            self.welcome.setStyleSheet("font-size: 12px; font-weight: 800; color: #3182ce; text-transform: uppercase; letter-spacing: 2px;")
            self.title.setStyleSheet("font-size: 32px; font-weight: 900; color: #1a202c;")

        for col in self.columns:
            col.update_theme(theme)

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
        conn.close()
        
        if row:
            created = row[3] if row[3] else "Unknown"
            urg, imp = row[4], row[5]
            if urg and imp: prio = "high"
            elif not urg and imp: prio = "medium"
            elif urg and not imp: prio = "low"
            else: prio = "too low"
            
            ViewTaskDialog(row[0], row[1], row[2], created, prio, self, theme=self.current_theme).exec()

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
        conn = self.get_db_connection()
        conn.execute("UPDATE tasks SET is_completed=? WHERE id=?", (1 if checked else 0, t_id))
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

        conn = self.get_db_connection()
        try:
            rows = conn.execute("SELECT id, title, description, due_date, created_date, is_urgent, is_important FROM tasks WHERE is_completed=0 ORDER BY due_date").fetchall()
        except: rows = []
        conn.close()

        map_cols = {}
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

            if pretty_due not in map_cols:
                is_today = (due_date_str == QDate.currentDate().toString("yyyy-MM-dd"))
                col = DayColumn(pretty_due, is_today, theme=self.current_theme)
                self.columns_layout.addWidget(col)
                map_cols[pretty_due] = col
                self.columns.append(col)
            
            card = TaskCard(t_id, title, desc, pretty_due, pretty_created, priority, self)
            card.update_theme(self.current_theme) 
            map_cols[pretty_due].add_task_card(card)
        
        self.columns_layout.addStretch()