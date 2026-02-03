import sys
import os
import ctypes
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QStackedWidget, QFrame, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon

# --- IMPORTS DES PAGES ---
from pages.tasks_page import TasksPage
from pages.matrix_page import EisenhowerMatrix
# --- IMPORT DATABASE ---
from database.db_manager import init_db

# Configure App ID for Windows Taskbar
myappid = 'mycompany.prodsmart.taskmanager.1.0' 
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

class PlaceholderPage(QWidget):
    def __init__(self, name):
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel(f"Page {name} en construction")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProdSmart")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #f8f9fa;")

        # --- CONFIGURATION DES CHEMINS ---
        basedir = os.path.dirname(__file__)
        image_path = os.path.join(basedir, "ProdSmart.png")

        # --- 1. ICÔNE DE LA FENÊTRE ---
        if os.path.exists(image_path):
            self.setWindowIcon(QIcon(image_path))

        # Layout Principal
        self.central_widget = QWidget()
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- 2. SIDEBAR ---
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setStyleSheet("background-color: white; border-right: 1px solid #e2e8f0;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        
        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("margin-top: 15px; margin-bottom: 15px;")
        
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("ProdSmart")
            logo_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #3182ce;")

        sidebar_layout.addWidget(logo_label)

        # Boutons de navigation
        self.btn_tasks = QPushButton("📋 Tasks")
        self.btn_matrix = QPushButton("⊞ Matrix")
        self.btn_pomodoro = QPushButton("⏱ Pomodoro")
        self.btn_dashboard = QPushButton("📊 Dashboard")
        
        for btn in [self.btn_tasks, self.btn_matrix, self.btn_pomodoro, self.btn_dashboard]:
            btn.setStyleSheet("""
                QPushButton { text-align: left; padding: 12px; border: none; border-radius: 8px; margin: 2px 10px; }
                QPushButton:hover { background-color: #edf2f7; }
            """)
            sidebar_layout.addWidget(btn)
        
        sidebar_layout.addStretch()
        self.main_layout.addWidget(self.sidebar)

        # --- 3. CONTENT AREA ---
        self.content_stack = QStackedWidget()
        self.page_tasks = TasksPage()
        self.page_matrix = EisenhowerMatrix()
        self.page_pomodoro = PlaceholderPage("Pomodoro")
        self.page_dashboard = PlaceholderPage("Dashboard")
        
        self.content_stack.addWidget(self.page_tasks)
        self.content_stack.addWidget(self.page_matrix)
        self.content_stack.addWidget(self.page_pomodoro)
        self.content_stack.addWidget(self.page_dashboard)

        # --- CRITICAL FIX: SIGNAL CONNECTION ---
        # This ensures that when Matrix updates DB, Task page refreshes instantly
        # (Make sure you added the signal to EisenhowerMatrix in matrix_page.py!)
        try:
            self.page_matrix.task_updated.connect(self.page_tasks.refresh_tasks)
        except AttributeError:
            print("Warning: task_updated signal not found in EisenhowerMatrix yet.")

        # Connexions Navigation
        self.btn_tasks.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.btn_matrix.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self.btn_pomodoro.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.btn_dashboard.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))

        self.content_stack.currentChanged.connect(self.on_page_change)

        self.main_layout.addWidget(self.content_stack)
        self.setCentralWidget(self.central_widget)

    def on_page_change(self, index):
        if index == 0: 
            self.page_tasks.refresh_tasks()
        elif index == 1:
            self.page_matrix.refresh_matrix()

if __name__ == "__main__":
    init_db() 
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())