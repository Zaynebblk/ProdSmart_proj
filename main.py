import sys
import os
import json
import ctypes
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QStackedWidget, QFrame, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

# --- IMPORTS ---
try:
    from database.db_manager import init_db
    from pages.tasks_page import TasksPage
    from pages.matrix_page import EisenhowerMatrix
    from pages.pomodoro_page import PomodoroPage
    from pages.history_page import HistoryPage
    from pages.settings_page import SettingsPage
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProdSmart")
        self.resize(1200, 800)

        # --- SET WINDOW & TASKBAR ICON ---
        if os.path.exists("ProdSmart.png"):
            self.setWindowIcon(QIcon("ProdSmart.png"))

        # ID for Windows Taskbar
        try:
            if os.name == 'nt':
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('prodsmart.app.1.0')
        except: pass

        self.central_widget = QWidget()
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. SIDEBAR
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setObjectName("Sidebar")
        sidebar_l = QVBoxLayout(self.sidebar)
        
        # --- SIDEBAR HEADER (Logo + Title) ---
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 20, 10, 20)
        header_layout.setSpacing(10)

        # Logo
        logo_icon = QLabel()
        if os.path.exists("ProdSmart.png"):
            pixmap = QPixmap("ProdSmart.png")
            scaled_pixmap = pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_icon.setPixmap(scaled_pixmap)
        logo_icon.setStyleSheet("border: none; background: transparent;")

        # Title
        logo_text = QLabel("ProdSmart")
        logo_text.setStyleSheet("font-size: 24px; font-weight: bold; color: #2563eb; border: none; background: transparent;")

        header_layout.addWidget(logo_icon)
        header_layout.addWidget(logo_text)
        header_layout.addStretch()

        sidebar_l.addWidget(header_widget)
        # -----------------------------------------

        self.btn_tasks = QPushButton("📋 Tasks")
        self.btn_matrix = QPushButton("⊞ Matrix")
        self.btn_pomodoro = QPushButton("⏱ Pomodoro")
        self.btn_history = QPushButton("📜 History")
        self.btn_settings = QPushButton("⚙ Settings")
        
        for btn in [self.btn_tasks, self.btn_matrix, self.btn_pomodoro, self.btn_history, self.btn_settings]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sidebar_l.addWidget(btn)
        
        sidebar_l.addStretch()
        self.main_layout.addWidget(self.sidebar)

        # 2. CONTENT (STACK)
        self.content_stack = QStackedWidget()
        
        # Initialize pages
        self.page_tasks = TasksPage()
        self.page_matrix = EisenhowerMatrix()
        self.page_pomodoro = PomodoroPage()
        self.page_history = HistoryPage()
        self.page_settings = SettingsPage()

        self.content_stack.addWidget(self.page_tasks)      # Index 0
        self.content_stack.addWidget(self.page_matrix)     # Index 1
        self.content_stack.addWidget(self.page_pomodoro)   # Index 2
        self.content_stack.addWidget(self.page_history)    # Index 3
        self.content_stack.addWidget(self.page_settings)   # Index 4

        self.main_layout.addWidget(self.content_stack)
        self.setCentralWidget(self.central_widget)

        # 3. BUTTON CONNECTIONS
        self.btn_tasks.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.btn_matrix.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self.btn_pomodoro.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.btn_history.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))
        self.btn_settings.clicked.connect(lambda: self.content_stack.setCurrentIndex(4))

        # Monitor Page Changes to Auto-Refresh Data
        self.content_stack.currentChanged.connect(self.on_page_changed)

        # --- 4. SIGNALS CONNECTIONS ---
        
        # Connection 1: Settings -> Apply Theme
        self.page_settings.settings_saved.connect(self.apply_settings)

        # Connection 2: Task Added -> Matrix Refresh
        if hasattr(self.page_tasks, 'task_added'):
            self.page_tasks.task_added.connect(self.page_matrix.refresh_matrix)
        
        # Connection 3: History Restore -> Tasks Refresh
        # (This relies on the signal we added to history_page.py)
        if hasattr(self.page_history, 'task_restored'):
            self.page_history.task_restored.connect(self.page_tasks.refresh_tasks)

        # 5. INITIAL LOAD
        self.apply_settings()

    def on_page_changed(self, index):
        """Auto-refresh data when clicking on a tab"""
        if index == 0:
            self.page_tasks.refresh_tasks()
        elif index == 1:
            self.page_matrix.refresh_matrix()
        elif index == 3:
            # --- FIX: Removed 'theme_mode' argument here ---
            self.page_history.refresh_history()

    def get_settings_path(self):
        return os.path.join(os.getcwd(), "settings.json")

    def apply_settings(self):
        """Reads JSON and applies theme to ALL pages."""
        theme = "Light"
        path = self.get_settings_path()
        
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    theme = data.get("theme", "Light")
            except Exception as e:
                print(f"Error reading settings: {e}")
        
        print(f"Applying Theme: {theme}")

        # 1. Apply to Main Window
        if theme == "Dark":
            self.set_dark_theme()
        else:
            self.set_light_theme()

        # 2. Apply to Specific Pages
        if hasattr(self, 'page_matrix'):
            self.page_matrix.update_theme(theme)
            
        if hasattr(self, 'page_tasks'):
            self.page_tasks.update_theme(theme)

        # We keep this for compatibility, even if it doesn't change history looks
        if hasattr(self, 'page_history'):
            self.page_history.update_theme(theme)

    # --- STYLE LIGHT ---
    def set_light_theme(self):
        self.setStyleSheet("""
            /* GLOBAL */
            QMainWindow, QWidget { background-color: #f8f9fa; color: #1e293b; }
            QFrame#Sidebar { background-color: white; border-right: 1px solid #e2e8f0; }
            
            /* SIDEBAR BUTTONS */
            QPushButton { background-color: transparent; text-align: left; padding: 12px; border: none; border-radius: 8px; color: #475569; font-weight: 600; }
            QPushButton:hover { background-color: #edf2f7; color: #2563eb; }
            
            /* SETTINGS SPECIFIC */
            QFrame#SettingsCard { background-color: white; border: 1px solid #e2e8f0; border-radius: 12px; }
            QLabel#SettingsLabel { color: #1e293b; }
            QComboBox { background-color: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px; color: #1e293b; }
            QComboBox QAbstractItemView { background-color: white; color: #1e293b; selection-background-color: #edf2f7; selection-color: #2563eb; }
        """)

    # --- STYLE DARK ---
    def set_dark_theme(self):
        self.setStyleSheet("""
            /* GLOBAL */
            QMainWindow, QWidget { background-color: #121212; color: #e0e0e0; }
            QFrame#Sidebar { background-color: #1e1e1e; border-right: 1px solid #333; }
            
            /* SIDEBAR BUTTONS */
            QPushButton { background-color: transparent; text-align: left; padding: 12px; border: none; border-radius: 8px; color: #a0a0a0; font-weight: 600; }
            QPushButton:hover { background-color: #333; color: #60a5fa; }
            
            /* SETTINGS SPECIFIC */
            QFrame#SettingsCard { background-color: #1e1e1e; border: 1px solid #333; border-radius: 12px; }
            QLabel#SettingsLabel { color: #e0e0e0; }
            QComboBox { background-color: #2d2d2d; border: 1px solid #444; border-radius: 6px; padding: 5px; color: white; }
            QComboBox QAbstractItemView { background-color: #2d2d2d; color: white; selection-background-color: #2563eb; selection-color: white; }
        """)

if __name__ == "__main__":
    try:
        init_db()
        app = QApplication(sys.argv)
        
        if os.path.exists("ProdSmart.png"):
            app.setWindowIcon(QIcon("ProdSmart.png"))
            
        window = MainApp()
        window.show()
        sys.exit(app.exec())
    except Exception:
        traceback.print_exc()