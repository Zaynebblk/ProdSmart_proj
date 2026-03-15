import sys
import os
import json
import ctypes
import traceback
import signal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QStackedWidget, QFrame, QLabel, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

# --- IMPORTS ---
try:
    from database.db_manager import init_db
    from pages.dashboard_page import DashboardPage
    from pages.tasks_page import TasksPage
    from pages.matrix_page import EisenhowerMatrix
    from pages.pomodoro_page import PomodoroPage
    from pages.history_page import HistoryPage
    from pages.report_page import SessionReportPage
    from pages.settings_page import SettingsPage
    from pages.quick_stats_page import QuickStatsPage
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
        self.sidebar.setFixedWidth(240)
        self.sidebar.setObjectName("Sidebar")
        sidebar_l = QVBoxLayout(self.sidebar)
        sidebar_l.setContentsMargins(12, 10, 12, 10)
        sidebar_l.setSpacing(8)
        
        # --- SIDEBAR HEADER (Logo + Title) ---
        header_widget = QWidget()
        header_widget.setObjectName("SidebarHeader")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(14, 16, 14, 16)
        header_layout.setSpacing(10)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo
        logo_icon = QLabel()
        logo_icon.setObjectName("SidebarLogo")
        if os.path.exists("ProdSmart.png"):
            pixmap = QPixmap("ProdSmart.png")
            scaled_pixmap = pixmap.scaled(140, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_icon.setPixmap(scaled_pixmap)
        logo_icon.setFixedSize(150, 150)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        logo_text = QLabel("ProdSmart")
        logo_text.setObjectName("SidebarTitle")
        logo_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addWidget(logo_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(logo_text, alignment=Qt.AlignmentFlag.AlignCenter)

        sidebar_l.addWidget(header_widget)

        sep_top = QFrame()
        sep_top.setObjectName("SidebarSeparator")
        sep_top.setFixedHeight(1)
        sep_top.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar_l.addWidget(sep_top)
        # -----------------------------------------
        self.btn_tasks = QPushButton("Tasks")
        self.btn_dashboard = QPushButton("Dashboard")
        
        self.btn_matrix = QPushButton("Matrix")
        self.btn_pomodoro = QPushButton("Pomodoro")
        self.btn_history = QPushButton("History")
        self.btn_settings = QPushButton("Settings")

        self.nav_buttons = [ self.btn_tasks,
            self.btn_dashboard,
            self.btn_matrix,
            self.btn_pomodoro,
            self.btn_history,
            self.btn_settings
        ]
        
        for btn in self.nav_buttons:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("nav", True)

        for btn in [ self.btn_tasks,self.btn_dashboard, self.btn_matrix, self.btn_pomodoro, self.btn_history]:
            sidebar_l.addWidget(btn)

        sep_bottom = QFrame()
        sep_bottom.setObjectName("SidebarSeparator")
        sep_bottom.setFixedHeight(1)
        sep_bottom.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar_l.addWidget(sep_bottom)

        sidebar_l.addWidget(self.btn_settings)

        sidebar_l.addStretch()
        self.main_layout.addWidget(self.sidebar)

        # 2. CONTENT (STACK)
        self.content_stack = QStackedWidget()
        
        # Initialize pages
        self.page_tasks = TasksPage()
        self.page_dashboard = DashboardPage()
        self.page_matrix = EisenhowerMatrix()
        self.page_pomodoro = PomodoroPage()
        self.page_history = HistoryPage()
        self.page_report = SessionReportPage()
        self.page_quick_stats = QuickStatsPage()
        self.page_settings = SettingsPage()
        
        self.content_stack.addWidget(self.page_tasks)      # Index 0
        self.content_stack.addWidget(self.page_dashboard)  # Index 1
        self.content_stack.addWidget(self.page_matrix)     # Index 2
        self.content_stack.addWidget(self.page_pomodoro)   # Index 3
        self.content_stack.addWidget(self.page_history)    # Index 4
        self.content_stack.addWidget(self.page_settings)   # Index 5
        self.content_stack.addWidget(self.page_report)     # Index 6
        self.content_stack.addWidget(self.page_quick_stats) # Index 7

        self.main_layout.addWidget(self.content_stack)
        self.setCentralWidget(self.central_widget)

        # 3. BUTTON CONNECTIONS
        self.btn_tasks.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.btn_dashboard.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        
        self.btn_matrix.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.btn_pomodoro.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))
        self.btn_history.clicked.connect(lambda: self.content_stack.setCurrentIndex(4))
        self.btn_settings.clicked.connect(lambda: self.content_stack.setCurrentIndex(5))

        # Monitor Page Changes to Auto-Refresh Data
        self.content_stack.currentChanged.connect(self.on_page_changed)

        # --- 4. SIGNALS CONNECTIONS ---
        
        # Connection 1: Settings -> Apply Theme
        self.page_settings.settings_saved.connect(self.apply_settings)

        # Connection 2: Task Added -> Matrix Refresh
        if hasattr(self.page_tasks, 'task_added'):
            self.page_tasks.task_added.connect(self.page_matrix.refresh_matrix)

        # Connection 3: Task -> Pomodoro
        if hasattr(self.page_tasks, 'pomodoro_requested'):
            self.page_tasks.pomodoro_requested.connect(self.open_pomodoro_for_task)

        # Connection 4: Pomodoro -> Tasks (Select Task shortcut)
        if hasattr(self.page_pomodoro, 'select_task_requested'):
            self.page_pomodoro.select_task_requested.connect(self.open_tasks_from_pomodoro)

        # Connection 5: History -> Dashboard (Full Analytics Breakdown)
        if hasattr(self.page_history, 'request_dashboard'):
            self.page_history.request_dashboard.connect(self.open_dashboard_from_history)

        # Connection 3: History Restore -> Tasks Refresh
        # (This relies on the signal we added to history_page.py)
        if hasattr(self.page_history, 'task_restored'):
            self.page_history.task_restored.connect(self.page_tasks.refresh_tasks)

        # Connection 6: History -> Report
        if hasattr(self.page_history, 'request_report'):
            self.page_history.request_report.connect(self.open_report_from_history)

        # Connection 7: Report -> History
        if hasattr(self.page_report, 'request_history'):
            self.page_report.request_history.connect(self.open_history_from_report)

        # Connection 8: History -> Quick Stats
        if hasattr(self.page_history, 'request_quick_stats'):
            self.page_history.request_quick_stats.connect(self.open_quick_stats_from_history)

        # Connection 9: Quick Stats -> History
        if hasattr(self.page_quick_stats, 'request_history'):
            self.page_quick_stats.request_history.connect(self.open_history_from_quick_stats)

        # 5. INITIAL LOAD
        self.apply_settings()
        self.content_stack.setCurrentIndex(0)
        self.page_tasks.refresh_tasks()
        self._set_active_nav(self.btn_tasks)

    def on_page_changed(self, index):
        """Auto-refresh data when clicking on a tab"""
        if index == 0:
            self.page_tasks.refresh_tasks()
            self._set_active_nav(self.btn_tasks)
        elif index == 1:
            if hasattr(self.page_dashboard, "refresh_dashboard"):
                self.page_dashboard.refresh_dashboard()
            elif hasattr(self.page_dashboard, "_load_metrics_from_db"):
                self.page_dashboard._load_metrics_from_db()
            self._set_active_nav(self.btn_dashboard)
        elif index == 2:
            self.page_matrix.refresh_matrix()
            self._set_active_nav(self.btn_matrix)
        elif index == 3:
            self._set_active_nav(self.btn_pomodoro)
        elif index == 4:
            # --- FIX: Removed 'theme_mode' argument here ---
            self.page_history.refresh_history()
            self._set_active_nav(self.btn_history)
        elif index == 5:
            self._set_active_nav(self.btn_settings)
        elif index == 6:
            self._set_active_nav(self.btn_history)
        elif index == 7:
            self._set_active_nav(self.btn_history)

    def open_pomodoro_for_task(self, t_id, title):
        if hasattr(self, "page_pomodoro") and hasattr(self.page_pomodoro, "set_task"):
            self.page_pomodoro.set_task(t_id, title)
        self.content_stack.setCurrentIndex(3)
        self._set_active_nav(self.btn_pomodoro)

    def open_tasks_from_pomodoro(self):
        self.content_stack.setCurrentIndex(0)
        self._set_active_nav(self.btn_tasks)

    def open_dashboard_from_history(self):
        self.content_stack.setCurrentIndex(1)
        self._set_active_nav(self.btn_dashboard)

    def open_report_from_history(self, activity_id):
        if hasattr(self, "page_report"):
            self.page_report.load_report(activity_id)
        self.content_stack.setCurrentIndex(6)
        self._set_active_nav(self.btn_history)

    def open_history_from_report(self):
        self.content_stack.setCurrentIndex(4)
        self._set_active_nav(self.btn_history)

    def open_quick_stats_from_history(self, activity_id):
        if hasattr(self, "page_quick_stats"):
            self.page_quick_stats.load_activity(activity_id)
        self.content_stack.setCurrentIndex(7)
        self._set_active_nav(self.btn_history)

    def open_history_from_quick_stats(self):
        self.content_stack.setCurrentIndex(4)
        self._set_active_nav(self.btn_history)

    def _set_active_nav(self, active_btn):
        if not hasattr(self, "nav_buttons"):
            return
        for btn in self.nav_buttons:
            is_active = btn is active_btn
            if btn.property("active") != is_active:
                btn.setProperty("active", is_active)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()

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

        if hasattr(self, 'page_dashboard'):
            self.page_dashboard.update_theme(theme)

        if hasattr(self, 'page_report'):
            self.page_report.update_theme(theme)

        if hasattr(self, 'page_quick_stats'):
            self.page_quick_stats.update_theme(theme)

    # --- STYLE LIGHT ---
    def set_light_theme(self):
        self.setStyleSheet("""
            /* GLOBAL */
            QMainWindow { background-color: #f8f9fa; color: #1e293b; }
            QWidget { color: #1e293b; }
            QFrame#Sidebar { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
            QWidget#SidebarHeader { background-color: #f8fafc; border-radius: 14px; margin: 12px; }
            QLabel#SidebarLogo { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 6px; }
            QLabel#SidebarTitle { font-size: 20px; font-weight: 900; color: #2563eb; }
            QFrame#SidebarSeparator { background-color: #e2e8f0; margin: 8px 10px; }
            
            /* SIDEBAR BUTTONS */
            QFrame#Sidebar QPushButton[nav="true"] { background-color: transparent; padding: 12px 14px; border: none; border-radius: 10px; color: #475569; font-weight: bold; }
            QFrame#Sidebar QPushButton[nav="true"]:hover { background-color: #eef2f7; color: #1d4ed8; }
            QFrame#Sidebar QPushButton[nav="true"][active="true"] { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:0.03 #2563eb, stop:0.03 #e7f0ff, stop:1 #e7f0ff);
                color: #1d4ed8;
            }
            QFrame#Sidebar QPushButton[nav="true"][active="true"]:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1d4ed8, stop:0.03 #1d4ed8, stop:0.03 #dde9ff, stop:1 #dde9ff);
            }
            
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
            QMainWindow { background-color: #121212; color: #e0e0e0; }
            QWidget { color: #e0e0e0; }
            QFrame#Sidebar { background-color: #1b1f26; border-right: 1px solid #2b3038; }
            QWidget#SidebarHeader { background-color: #202632; border-radius: 14px; margin: 12px; }
            QLabel#SidebarLogo { background-color: #111827; border: 1px solid #2b3038; border-radius: 12px; padding: 6px; }
            QLabel#SidebarTitle { font-size: 20px; font-weight: 900; color: #93c5fd; }
            QFrame#SidebarSeparator { background-color: #2b3340; margin: 8px 10px; }
            
            /* SIDEBAR BUTTONS */
            QFrame#Sidebar QPushButton[nav="true"] { background-color: transparent; padding: 12px 14px; border: none; border-radius: 10px; color: #b3bac6; font-weight: bold; }
            QFrame#Sidebar QPushButton[nav="true"]:hover { background-color: #2b3340; color: #93c5fd; }
            QFrame#Sidebar QPushButton[nav="true"][active="true"] { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #60a5fa, stop:0.03 #60a5fa, stop:0.03 #243042, stop:1 #243042);
                color: #bfdbfe;
            }
            QFrame#Sidebar QPushButton[nav="true"][active="true"]:hover { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #93c5fd, stop:0.03 #93c5fd, stop:0.03 #2f3a4b, stop:1 #2f3a4b);
            }
            
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
            
        # Exit cleanly on Ctrl+C without a traceback.
        signal.signal(signal.SIGINT, lambda *_: app.quit())

        window = MainApp()
        window.show()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
