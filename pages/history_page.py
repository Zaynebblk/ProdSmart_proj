from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QPushButton, 
                             QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from database.db_manager import get_db_connection
from datetime import datetime

class StatCard(QFrame):
    def __init__(self, title, value, color, theme="Light", width=185):
        super().__init__()
        self.setFixedWidth(width)
        self.setFixedHeight(110)
        
        # --- THEME COLORS ---
        if theme == "Dark":
            bg_color = "#1e1e1e"
            border_color = "#333"
            text_val_color = "#e0e0e0"
            text_lbl_color = "#a0a0a0"
        else:
            bg_color = "white"
            border_color = "#e2e8f0"
            text_val_color = "#1a202c"
            text_lbl_color = "#718096"

        self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border-radius: 15px; border: 1px solid {border_color}; }}")
        
        # Shadow (Subtler in dark mode)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow_color = QColor(0, 0, 0, 50) if theme == "Dark" else QColor(0, 0, 0, 30)
        shadow.setColor(shadow_color)
        shadow.setYOffset(4)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Color Accent
        accent = QFrame()
        accent.setFixedWidth(4)
        accent.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        layout.addWidget(accent)

        v_layout = QVBoxLayout()
        # Title Label
        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet(f"color: {text_lbl_color}; font-size: 9px; font-weight: bold; border: none; background: transparent;")
        v_layout.addWidget(lbl_title)
        
        # Value Label
        lbl_val = QLabel(str(value))
        lbl_val.setStyleSheet(f"color: {text_val_color}; font-size: 26px; font-weight: 800; border: none; background: transparent;")
        v_layout.addWidget(lbl_val)
        
        layout.addLayout(v_layout)

class HistoryPage(QWidget):
    task_restored = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_theme = "Light" # Default State
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 40, 30, 40)
        self.layout.setSpacing(25)

        # Title
        self.title = QLabel("Performance Analytics")
        self.layout.addWidget(self.title)

        # Stats Area
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(10)
        self.layout.addLayout(self.stats_layout)

        # Subtitle
        self.sub_title = QLabel("Completion Log")
        self.layout.addWidget(self.sub_title)
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(12)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)

        # Apply initial styles
        self.apply_label_styles()

    def apply_label_styles(self):
        if self.current_theme == "Dark":
            text_main = "#e0e0e0"
            text_sub = "#a0a0a0"
        else:
            text_main = "#1a202c"
            text_sub = "#2d3748"
            
        self.title.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {text_main};")
        self.sub_title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {text_sub};")

    def update_theme(self, theme):
        """Called by main.py when settings change"""
        self.current_theme = theme
        self.apply_label_styles()
        self.refresh_history()

    def format_date(self, date_str):
        if not date_str or date_str == "None":
            return "recently"
        try:
            task_date = datetime.strptime(date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            diff = (now.date() - task_date.date()).days
            if diff == 0: return f"at {task_date.strftime('%H:%M')} today"
            elif diff == 1: return f"at {task_date.strftime('%H:%M')} yesterday"
            else: return f"on {task_date.strftime('%b %d, %H:%M')}"
        except: return "recently"

    def refresh_history(self):
        # Clear existing items
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        conn = get_db_connection()
        try:
            # Note: Ensure you ran the 'fix_db.py' script so 'completed_at' exists!
            rows = conn.execute("SELECT id, title, priority, completed_at FROM tasks WHERE is_completed = 1 ORDER BY completed_at DESC").fetchall()
        except Exception as e:
            print("DB Error (History):", e)
            rows = []
        conn.close()

        # Calculate Stats
        total = len(rows)
        h = sum(1 for r in rows if str(r[2]).lower() == "high")
        m = sum(1 for r in rows if str(r[2]).lower() == "medium")
        l = sum(1 for r in rows if str(r[2]).lower() == "low")
        tl = sum(1 for r in rows if str(r[2]).lower() == "too low")

        # Create Stat Cards with CURRENT THEME
        self.stats_layout.addWidget(StatCard("Total Done", total, "#4f46e5", self.current_theme, 195))
        self.stats_layout.addWidget(StatCard("High", h, "#ef4444", self.current_theme))
        self.stats_layout.addWidget(StatCard("Medium", m, "#f59e0b", self.current_theme))
        self.stats_layout.addWidget(StatCard("Low", l, "#3b82f6", self.current_theme))
        self.stats_layout.addWidget(StatCard("Too Low", tl, "#64748b", self.current_theme))
        self.stats_layout.addStretch()

        # Create List Items
        for row in rows:
            self.list_layout.addWidget(self.create_pro_card(row))

    def create_pro_card(self, data):
        card = QFrame()
        
        # --- THEME STYLES FOR LIST ITEMS ---
        if self.current_theme == "Dark":
            bg = "#1e1e1e"
            border = "#333"
            title_color = "#e0e0e0"
            time_bg = "#2d2d2d"
            time_border = "#444"
            time_text = "#a0a0a0"
            btn_bg = "#2d2d2d"
            btn_fg = "#a0a0a0"
            btn_hover = "#444"
        else:
            bg = "white"
            border = "#e2e8f0"
            title_color = "#4a5568"
            time_bg = "#f8fafc"
            time_border = "#edf2f7"
            time_text = "#a0aec0"
            btn_bg = "#f1f5f9"
            btn_fg = "#64748b"
            btn_hover = "#3b82f6"

        card.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 12px; border: 1px solid {border}; }}")
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setYOffset(2)
        card.setGraphicsEffect(shadow)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        
        v_info = QVBoxLayout()
        title = QLabel(data[1])
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {title_color}; text-decoration: line-through; border: none; background: transparent;")
        
        date_text = self.format_date(str(data[3])) 
        meta_h = QHBoxLayout()
        time_lbl = QLabel(f"Finished {date_text}")
        time_lbl.setStyleSheet(f"font-size: 12px; color: {time_text}; background: {time_bg}; padding: 2px 8px; border-radius: 4px; border: 1px solid {time_border};")
        
        prio_val = str(data[2]).lower() if data[2] else "low"
        colors = {"high": "#ef4444", "medium": "#f59e0b", "low": "#3b82f6", "too low": "#64748b"}
        p_color = colors.get(prio_val, "#3b82f6")
        
        badge = QLabel(prio_val.upper())
        badge.setStyleSheet(f"color: white; background-color: {p_color}; font-size: 9px; font-weight: bold; padding: 3px 10px; border-radius: 5px; border: none;")
        
        meta_h.addWidget(time_lbl); meta_h.addWidget(badge); meta_h.addStretch()
        v_info.addWidget(title); v_info.addLayout(meta_h)
        layout.addLayout(v_info); layout.addStretch()
        
        btn = QPushButton("↺")
        btn.setFixedSize(32, 32)
        # Specific button styling to handle hover states correctly in string format
        btn.setStyleSheet(f"""
            QPushButton {{ border-radius: 16px; background: {btn_bg}; color: {btn_fg}; border: none; }} 
            QPushButton:hover {{ background: {btn_hover}; color: white; }}
        """)
        btn.clicked.connect(lambda: self.restore_task(data[0]))
        layout.addWidget(btn)
        
        return card

    def restore_task(self, t_id):
        conn = get_db_connection()
        conn.execute("UPDATE tasks SET is_completed = 0, completed_at = NULL WHERE id = ?", (t_id,))
        conn.commit(); conn.close()
        
        self.task_restored.emit() 
        self.refresh_history()