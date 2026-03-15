import sqlite3
from PyQt6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, 
                             QScrollArea, QHBoxLayout, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QMimeData, QSize, pyqtSignal
from PyQt6.QtGui import QDrag, QCursor, QFont, QColor

from database.db_manager import get_db_connection

# --- 1. DRAGGABLE CARD ---
class TaskCard(QFrame):
    def __init__(self, task_id, title, theme_mode="Light"):
        super().__init__()
        self.task_id = task_id
        self.title_text = title
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        # Setup basic layout
        self.layout_box = QHBoxLayout(self)
        self.layout_box.setContentsMargins(12, 12, 12, 12)
        self.layout_box.setSpacing(10)

        self.grip = QLabel("::") 
        self.grip.setFixedWidth(15)
        
        self.lbl = QLabel(title)
        self.lbl.setWordWrap(True)

        self.layout_box.addWidget(self.grip)
        self.layout_box.addWidget(self.lbl)
        self.layout_box.addStretch()
        
        # Apply the initial theme
        self.set_theme(theme_mode)

    def set_theme(self, mode):
        if mode == "Dark":
            bg_color = "#2d2d2d"
            border_color = "#404040"
            text_color = "white"
            grip_color = "#666"
            hover_bg = "#383838"
            hover_border = "#3b82f6"
        else:
            bg_color = "white"
            border_color = "#e2e8f0"
            text_color = "#2d3748"
            grip_color = "#cbd5e0"
            hover_bg = "#ebf8ff"
            hover_border = "#3182ce"

        self.setStyleSheet(f"""
            QFrame {{ 
                background-color: {bg_color}; 
                border: 1px solid {border_color}; 
                border-radius: 8px; 
                margin-bottom: 8px;
            }}
            QFrame:hover {{ 
                border: 1px solid {hover_border}; 
                background-color: {hover_bg}; 
            }}
        """)
        
        self.grip.setStyleSheet(f"color: {grip_color}; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        self.lbl.setStyleSheet(f"border: none; background: transparent; color: {text_color}; font-size: 13px; font-weight: 500;")

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self.task_id))
            drag.setMimeData(mime)
            
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.position().toPoint())
            
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            drag.exec(Qt.DropAction.MoveAction)
            self.setCursor(Qt.CursorShape.OpenHandCursor)

# --- 2. DROP ZONE (QUADRANT) ---
class Quadrant(QFrame):
    def __init__(self, title, sub, bg_color, border_color, text_color, urgent, important, parent_mx):
        super().__init__()
        self.setAcceptDrops(True)
        self.u_target = urgent
        self.i_target = important
        self.parent_mx = parent_mx
        self.current_theme = "Light"

        # Save Light Mode Colors
        self.light_bg = bg_color
        self.light_border = border_color
        self.light_text = text_color
        
        # Define Dark Mode Colors based on Quadrant Type
        if urgent and important: # Do First (Red)
            self.dark_bg = "#2C1A1A"  # Dark Red
            self.dark_border = "#5c2b2b"
            self.dark_text = "#fc8181" 
        elif not urgent and important: # Schedule (Green)
            self.dark_bg = "#1C2B22" # Dark Green
            self.dark_border = "#276749"
            self.dark_text = "#68d391"
        elif urgent and not important: # Delegate (Orange)
            self.dark_bg = "#2C2218" # Dark Orange
            self.dark_border = "#7b341e"
            self.dark_text = "#f6ad55"
        else: # Eliminate (Gray)
            self.dark_bg = "#1A202C" # Dark Gray
            self.dark_border = "#4a5568"
            self.dark_text = "#cbd5e0"

        self.title_str = title
        self.sub_str = sub

        self.setProperty("class", "Quadrant")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        
        self.lbl_title = QLabel(title)
        self.lbl_sub = QLabel(sub.upper())
        
        header_layout.addWidget(self.lbl_title)
        header_layout.addWidget(self.lbl_sub)
        layout.addLayout(header_layout)
        
        self.line = QFrame()
        self.line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self.line)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent; border: none;")
        self.c_layout = QVBoxLayout(self.container)
        self.c_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.c_layout.setSpacing(5)
        self.c_layout.setContentsMargins(0, 10, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.container)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                border: none; background: transparent; width: 8px; margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e0; min-height: 20px; border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        layout.addWidget(scroll)

        # Apply initial styles
        self.apply_theme("Light")

    def apply_theme(self, mode):
        self.current_theme = mode
        
        if mode == "Dark":
            c_bg = self.dark_bg
            c_border = self.dark_border
            c_text = self.dark_text
            c_sub_text = "rgba(255, 255, 255, 0.7)"
        else:
            c_bg = self.light_bg
            c_border = self.light_border
            c_text = self.light_text
            c_sub_text = f"{self.light_text}"

        self.setStyleSheet(f"""
            QFrame.Quadrant {{
                background-color: {c_bg}; 
                border: 2px solid {c_border}; 
                border-radius: 12px;
            }}
        """)
        
        self.lbl_title.setStyleSheet(f"color: {c_text}; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        self.lbl_sub.setStyleSheet(f"color: {c_sub_text}; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        self.line.setStyleSheet(f"background-color: {c_border};")

        # Update all existing tasks inside
        for i in range(self.c_layout.count()):
            widget = self.c_layout.itemAt(i).widget()
            if isinstance(widget, TaskCard):
                widget.set_theme(mode)

    def add_task(self, t_id, title):
        # Create card with current theme
        card = TaskCard(t_id, title, self.current_theme)
        self.c_layout.addWidget(card)

    def clear(self):
        while self.c_layout.count():
            item = self.c_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): 
            event.accept()
            self.setFrameShadow(QFrame.Shadow.Raised)
        else: 
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setFrameShadow(QFrame.Shadow.Plain)
        event.accept()

    def dropEvent(self, event):
        t_id = event.mimeData().text()
        conn = get_db_connection()
        
        p_text = "too low"
        if self.u_target and self.i_target:
            p_text = "high"
        elif not self.u_target and self.i_target:
            p_text = "medium"
        elif self.u_target and not self.i_target:
            p_text = "low"
        else:
            p_text = "too low"
        
        conn.execute("UPDATE tasks SET is_urgent=?, is_important=?, priority=? WHERE id=?", 
                     (1 if self.u_target else 0, 1 if self.i_target else 0, p_text, t_id))
        conn.commit()
        conn.close()
        
        self.parent_mx.refresh_matrix()
        self.parent_mx.task_updated.emit() 
        event.accept()

# --- 3. MAIN PAGE ---
class EisenhowerMatrix(QWidget):
    task_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Initial Theme
        self.current_theme = "Light"
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        
        self.page_title = QLabel("Eisenhower Matrix")
        self.main_layout.addWidget(self.page_title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(25)
        
        # Initialize Quadrants
        self.q1 = Quadrant("Urgent & Important", "Do First", 
                           "#fff5f5", "#feb2b2", "#c53030", True, True, self)
        
        self.q2 = Quadrant("Important, Not Urgent", "Schedule", 
                           "#f0fff4", "#9ae6b4", "#2f855a", False, True, self)
        
        self.q3 = Quadrant("Urgent, Not Important", "Delegate", 
                           "#fffaf0", "#fbd38d", "#c05621", True, False, self)
        
        self.q4 = Quadrant("Not Urgent, Not Important", "Eliminate", 
                           "#edf2f7", "#cbd5e0", "#4a5568", False, False, self)

        grid_layout.addWidget(self.q1, 0, 0)
        grid_layout.addWidget(self.q2, 0, 1)
        grid_layout.addWidget(self.q3, 1, 0)
        grid_layout.addWidget(self.q4, 1, 1)

        self.main_layout.addLayout(grid_layout)
        
        # Apply Default Light Theme
        self.update_theme("Light")

        # --- KEY CHANGE: Load tasks immediately on startup ---
        self.refresh_matrix()

    def update_theme(self, theme_name):
        """Called by MainApp to switch themes"""
        self.current_theme = theme_name
        
        if theme_name == "Dark":
            bg_color = "#121212"
            title_color = "white"
        else:
            bg_color = "#f7fafc"
            title_color = "#1a202c"

        self.setStyleSheet(f"background-color: {bg_color};")
        self.page_title.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {title_color}; margin-bottom: 20px;")

        # Update all quadrants
        for q in [self.q1, self.q2, self.q3, self.q4]:
            q.apply_theme(theme_name)

    def refresh_matrix(self):
        for q in [self.q1, self.q2, self.q3, self.q4]: q.clear()
        
        conn = get_db_connection()
        rows = conn.execute("SELECT id, title, is_urgent, is_important FROM tasks WHERE is_completed = 0").fetchall()
        conn.close()

        for row in rows:
            t_id, title, u, i = row
            is_u, is_i = bool(u), bool(i)
            
            if is_u and is_i: self.q1.add_task(t_id, title)
            elif not is_u and is_i: self.q2.add_task(t_id, title)
            elif is_u and not is_i: self.q3.add_task(t_id, title)
            else: self.q4.add_task(t_id, title)
