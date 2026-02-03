import sqlite3
from PyQt6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, 
                             QScrollArea, QHBoxLayout, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QMimeData, QSize, pyqtSignal  # <--- 1. ADDED pyqtSignal HERE
from PyQt6.QtGui import QDrag, QCursor, QFont, QColor

from database.db_manager import get_db_connection

# --- 1. CARTE DÉPLAÇABLE ---
class TaskCard(QFrame):
    def __init__(self, task_id, title):
        super().__init__()
        self.task_id = task_id
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        self.setStyleSheet("""
            QFrame { 
                background-color: white; 
                border: 1px solid #e2e8f0; 
                border-radius: 8px; 
                margin-bottom: 8px;
            }
            QFrame:hover { 
                border: 1px solid #3182ce; 
                background-color: #ebf8ff; 
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grip = QLabel("::") 
        grip.setStyleSheet("color: #cbd5e0; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        grip.setFixedWidth(15)
        
        lbl = QLabel(title)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("border: none; background: transparent; color: #2d3748; font-size: 13px; font-weight: 500;")

        layout.addWidget(grip)
        layout.addWidget(lbl)
        layout.addStretch()

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

# --- 2. ZONE DE DÉPÔT (QUADRANT) ---
class Quadrant(QFrame):
    def __init__(self, title, sub, bg_color, border_color, text_color, urgent, important, parent_mx):
        super().__init__()
        self.setAcceptDrops(True)
        self.u_target = urgent
        self.i_target = important
        self.parent_mx = parent_mx
        
        self.setStyleSheet(f"""
            QFrame.Quadrant {{
                background-color: {bg_color}; 
                border: 2px solid {border_color}; 
                border-radius: 12px;
            }}
        """)
        self.setProperty("class", "Quadrant")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {text_color}; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        
        lbl_sub = QLabel(sub.upper())
        lbl_sub.setStyleSheet(f"color: {text_color}; font-size: 10px; font-weight: bold; opacity: 0.7; letter-spacing: 1px; border: none; background: transparent;")
        
        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_sub)
        layout.addLayout(header_layout)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {border_color}; opacity: 0.5;")
        layout.addWidget(line)

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

    def add_task(self, t_id, title):
        self.c_layout.addWidget(TaskCard(t_id, title))

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
        
        # --- FIXED LOGIC START ---
        p_text = "too low"
        
        if self.u_target and self.i_target:
            p_text = "high"
        elif not self.u_target and self.i_target:
            p_text = "medium"
        elif self.u_target and not self.i_target:
            p_text = "low"
        else:
            p_text = "too low"
        # --- FIXED LOGIC END ---
        
        conn.execute("UPDATE tasks SET is_urgent=?, is_important=?, priority=? WHERE id=?", 
                     (1 if self.u_target else 0, 1 if self.i_target else 0, p_text, t_id))
        conn.commit()
        conn.close()
        
        self.parent_mx.refresh_matrix()
        
        # --- 3. EMIT SIGNAL ---
        # This will now work because task_updated is defined in EisenhowerMatrix below
        self.parent_mx.task_updated.emit() 
        
        event.accept()

# --- 3. PAGE PRINCIPALE ---
class EisenhowerMatrix(QWidget):
    # --- 2. DEFINE SIGNAL HERE ---
    task_updated = pyqtSignal()  # <--- CRITICAL LINE

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f7fafc;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        page_title = QLabel("Eisenhower Matrix")
        page_title.setStyleSheet("font-size: 26px; font-weight: bold; color: #1a202c; margin-bottom: 20px;")
        main_layout.addWidget(page_title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(25)
        
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

        main_layout.addLayout(grid_layout)

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