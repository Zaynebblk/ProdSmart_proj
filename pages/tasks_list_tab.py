import sqlite3
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QPushButton, QScrollArea, QDialog, 
                             QLineEdit, QDateEdit, QComboBox)
from PyQt6.QtCore import Qt, QDate

# ==========================================
# 1. PETITS COMPOSANTS (Doivent être au début)
# ==========================================

class TaskCard(QFrame):
    """La carte visuelle d'une tâche"""
    def __init__(self, title, priority):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #edf2f7;
                padding: 15px;
                margin-bottom: 10px;
            }
        """)
        layout = QHBoxLayout(self)
        
        # Titre
        self.label = QLabel(title)
        self.label.setStyleSheet("border: none; color: #2d3748; font-size: 14px;")
        
        # Badge de couleur selon la priorité
        colors = {
            "high": ("#fff5f5", "#e53e3e"),   # Rouge
            "medium": ("#fffaf0", "#dd6b20"), # Orange
            "low": ("#f0fff4", "#38a169")     # Vert
        }
        # Par défaut gris si inconnu
        bg, fg = colors.get(priority.lower(), ("#edf2f7", "#718096"))
        
        badge = QLabel(priority.upper())
        badge.setStyleSheet(f"background-color: {bg}; color: {fg}; border-radius: 6px; padding: 4px 8px; font-size: 10px; font-weight: bold; border: none;")
        
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(badge)

class DayColumn(QFrame):
    """La colonne verticale (ex: Tuesday)"""
    def __init__(self, date_text, count_text):
        super().__init__()
        self.setFixedWidth(320)
        self.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(self)
        
        self.lbl_date = QLabel(date_text)
        self.lbl_date.setStyleSheet("font-weight: bold; font-size: 16px; color: #1a202c;")
        self.lbl_count = QLabel(f"{count_text} pending")
        self.lbl_count.setStyleSheet("color: #a0aec0; font-size: 12px; margin-bottom: 10px;")
        
        layout.addWidget(self.lbl_date)
        layout.addWidget(self.lbl_count)
        
        self.list_layout = QVBoxLayout()
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addLayout(self.list_layout)
        layout.addStretch()

# ==========================================
# 2. LA FENÊTRE DE DIALOGUE "ADD TASK"
# ==========================================

class AddTaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Task")
        self.setFixedWidth(450)
        
        # Style identique à votre image
        self.setStyleSheet("""
            QDialog { background-color: white; }
            QLabel { color: #1a202c; font-weight: bold; font-size: 14px; margin-top: 10px; }
            QLineEdit, QDateEdit, QComboBox { 
                background-color: #f7fafc; 
                border: 1px solid #e2e8f0; 
                border-radius: 6px; 
                padding: 10px; 
                font-size: 14px;
            }
            QPushButton#SaveBtn {
                background-color: #4a5568; color: white; border-radius: 6px; padding: 10px 20px; font-weight: bold;
            }
            QPushButton#SaveBtn:hover { background-color: #2d3748; }
            QPushButton#CancelBtn {
                background-color: white; color: #1a202c; border: 1px solid #cbd5e0; border-radius: 6px; padding: 10px 20px; font-weight: bold;
            }
            QPushButton#CancelBtn:hover { background-color: #f7fafc; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(30, 30, 30, 30)

        # Champs
        layout.addWidget(QLabel("Title"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter task title...")
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("Due Date"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        layout.addWidget(self.date_input)

        layout.addWidget(QLabel("Priority"))
        self.priority_input = QComboBox()
        # Les données internes sont 'low', 'high', 'medium' pour la logique DB
        # Change "low" to "too low" for the first item
        self.priority_input.addItem("🟣 Not Urgent & Not Important", "too low") 
        self.priority_input.addItem("🔴 Urgent & Important (High)", "high")
        self.priority_input.addItem("🟠 Not Urgent & Important (Medium)", "medium")
        self.priority_input.addItem("🟢 Urgent & Not Important (Low)", "low")
        layout.addWidget(self.priority_input)

        # AI Banner
        ai_frame = QFrame()
        ai_frame.setStyleSheet("background-color: #f3f0ff; border-radius: 8px; margin-top: 10px;")
        ai_layout = QHBoxLayout(ai_frame)
        ai_lbl = QLabel("✨ AI Assistance\nAI will suggest the best quadrant based on your task details")
        ai_lbl.setStyleSheet("color: #553c9a; font-weight: normal; font-size: 12px; border: none; margin: 0;")
        ai_layout.addWidget(ai_lbl)
        layout.addWidget(ai_frame)

        layout.addStretch()

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("CancelBtn")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_save = QPushButton("Save Task")
        self.btn_save.setObjectName("SaveBtn")
        self.btn_save.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def get_data(self):
        return {
            "title": self.title_input.text(),
            "priority": self.priority_input.currentData()
        }

# ==========================================
# 3. LA PAGE PRINCIPALE (Importée par main.py)
# ==========================================

# NOTE: J'ai renommé la classe en 'TasksListTab' car c'est ce nom 
# que main.py cherche (from ui.tasks_list_tab import TasksListTab).
class TasksListTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f7fafc;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # Header
        header = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title = QLabel("Task Management")
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #1a202c;")
        title_vbox.addWidget(title)
        
        self.btn_add = QPushButton("+ Add New Task")
        self.btn_add.setFixedSize(140, 40)
        self.btn_add.setStyleSheet("""
            QPushButton { background-color: #3182ce; color: white; border-radius: 8px; font-weight: bold; }
            QPushButton:hover { background-color: #2b6cb0; }
        """)
        self.btn_add.clicked.connect(self.prompt_new_task)
        
        header.addLayout(title_vbox)
        header.addStretch()
        header.addWidget(self.btn_add)
        main_layout.addLayout(header)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        container = QWidget()
        self.columns_layout = QHBoxLayout(container)
        self.columns_layout.setSpacing(25)

        # Colonnes par défaut
        self.day1 = DayColumn("My Tasks", "Recent")
        # On ajoute une tâche d'exemple