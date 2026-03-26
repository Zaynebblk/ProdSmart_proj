import sys
import os
import json
import ctypes
import traceback
import signal
import time
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QStackedWidget, QFrame, QLabel, QSizePolicy)
from PyQt6.QtCore import Qt, QObject, QEvent, qInstallMessageHandler
from PyQt6.QtGui import QIcon, QPixmap, QFontMetrics
from resources.theme import get_theme, FONT_FAMILY

_LAST_QSS_INFO = None

def _app_icon_path():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    png_path = os.path.join(root_dir, "ProdSmart.png")
    ico_path = os.path.join(root_dir, "ProdSmart.ico")
    # Prefer the PNG logo if present, so the window/taskbar icon matches the brand logo.
    if os.path.exists(png_path):
        return png_path
    if os.path.exists(ico_path):
        return ico_path
    return None

def _install_qss_sanitizer():
    try:
        from PyQt6.QtWidgets import QWidget
    except Exception:
        return

    original_set = QWidget.setStyleSheet

    def _sanitize(style):
        if not isinstance(style, str):
            return style

        # Remove unsupported properties if any slipped in.
        s = re.sub(r"text-transform\\s*:\\s*uppercase\\s*;?", "", style)

        def _fix_block(match):
            block = match.group(0)
            block = re.sub(r"font-weight\\s*:\\s*(900|800|700)\\s*;?", "font-weight: bold;", block)
            return block

        # Fix any QPushButton-related blocks (including subselectors)
        s = re.sub(r"QPushButton[^\\{]*\\{[^\\}]*\\}", _fix_block, s, flags=re.DOTALL)
        s = re.sub(r"QMessageBox\\s+QPushButton[^\\{]*\\{[^\\}]*\\}", _fix_block, s, flags=re.DOTALL)
        return s

    def _wrapped_set(self, style):
        global _LAST_QSS_INFO
        try:
            _LAST_QSS_INFO = (self.__class__.__name__, self.objectName(), style)
        except Exception:
            _LAST_QSS_INFO = None
        try:
            return original_set(self, _sanitize(style))
        except Exception:
            return original_set(self, style)

    QWidget.setStyleSheet = _wrapped_set

def _install_qss_debug():
    if os.getenv("PRODSMART_DEBUG_QSS") != "1":
        return
    try:
        import PyQt6.sip as sip
    except Exception:
        try:
            import sip  # type: ignore
        except Exception:
            sip = None
    print("[QSS Debug] enabled")

    qss_cache = {}
    try:
        from PyQt6.QtWidgets import QWidget as _QWidget, QPushButton as _QPushButton
    except Exception:
        _QWidget = None
        _QPushButton = None

    if sip and _QWidget and _QPushButton:
        original_widget_set_style = _QWidget.setStyleSheet
        original_btn_set_style = _QPushButton.setStyleSheet

        def _cache_style(obj, style):
            try:
                ptr = sip.unwrapinstance(obj)
                qss_cache[int(ptr)] = style
            except Exception:
                pass

        def _wrapped_widget_set_style(self, style):
            if isinstance(self, _QPushButton):
                _cache_style(self, style)
            return original_widget_set_style(self, style)

        def _wrapped_btn_set_style(self, style):
            _cache_style(self, style)
            return original_btn_set_style(self, style)

        _QWidget.setStyleSheet = _wrapped_widget_set_style
        _QPushButton.setStyleSheet = _wrapped_btn_set_style

    def _handler(msg_type, context, message):
        print(message)
        if "Could not parse stylesheet of object QPushButton" in message and sip:
            match = re.search(r"QPushButton\((0x[0-9A-Fa-f]+)\)", message)
            if match:
                ptr_val = None
                try:
                    ptr_val = int(match.group(1), 16)
                except Exception:
                    ptr_val = None

                obj = None
                if ptr_val is not None:
                    try:
                        obj = sip.wrapinstance(ptr_val, QObject)
                    except Exception:
                        obj = None

                if obj is not None:
                    try:
                        name = obj.objectName()
                    except Exception:
                        name = ""
                    print(f"[QSS Debug] objectName='{name}' class={obj.__class__.__name__}")

                if ptr_val is not None and ptr_val in qss_cache:
                    print(f"[QSS Debug] styleSheet={qss_cache[ptr_val]}")
                else:
                    print("[QSS Debug] styleSheet not cached for this pointer.")

                if _LAST_QSS_INFO:
                    cls_name, obj_name, style = _LAST_QSS_INFO
                    print(f"[QSS Debug] last_set_style widget={cls_name} objectName='{obj_name}'")
                    print(f"[QSS Debug] last_set_style_sheet={style}")
        elif "Could not parse stylesheet of object QPushButton" in message and sip is None:
            print("[QSS Debug] sip module not available; cannot resolve QPushButton pointer.")

    qInstallMessageHandler(_handler)

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
        self.setMinimumSize(640, 420)

        # --- SET WINDOW & TASKBAR ICON ---
        icon_path = _app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        # ID for Windows Taskbar
        try:
            if os.name == 'nt':
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('prodsmart.app.1.0')
        except: pass

        self.central_widget = QWidget()
        self.central_widget.setMinimumSize(0, 0)
        self.central_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. SIDEBAR
        self.sidebar = QFrame()
        self.sidebar.setMinimumWidth(190)
        self.sidebar.setMaximumWidth(280)
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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
        header_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.sidebar_header = header_widget
        self.sidebar_header_layout = header_layout

        # Logo
        logo_icon = QLabel()
        logo_icon.setObjectName("SidebarLogo")
        self._logo_pixmap = None
        if os.path.exists("ProdSmart.png"):
            pixmap = QPixmap("ProdSmart.png")
            if not pixmap.isNull():
                self._logo_pixmap = pixmap
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.logo_icon = logo_icon

        # Title
        logo_text = QLabel("ProdSmart")
        logo_text.setObjectName("SidebarTitle")
        logo_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_text = logo_text

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
        self.content_stack.setMinimumSize(0, 0)
        self.content_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
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

        self.main_layout.addWidget(self.content_stack, stretch=1)
        self.setCentralWidget(self.central_widget)

        # Suppress tiny transient windows that can flash during page switches.
        self._transient_blocker = _TransientWindowBlocker(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self._transient_blocker)

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

        # Connection 5b: Dashboard -> Action
        if hasattr(self.page_dashboard, 'action_requested'):
            self.page_dashboard.action_requested.connect(self.handle_dashboard_action)

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
            if hasattr(self, "_transient_blocker"):
                self._transient_blocker.suppress_for(1200)
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

    def open_pomodoro_for_task(self, t_id, title, priority=None, task_type=None):
        if hasattr(self, "page_pomodoro") and hasattr(self.page_pomodoro, "set_task"):
            self.page_pomodoro.set_task(t_id, title, priority, task_type)
        self.content_stack.setCurrentIndex(3)
        self._set_active_nav(self.btn_pomodoro)

    def open_tasks_from_pomodoro(self):
        self.content_stack.setCurrentIndex(0)
        self._set_active_nav(self.btn_tasks)

    def open_dashboard_from_history(self):
        self.content_stack.setCurrentIndex(1)
        self._set_active_nav(self.btn_dashboard)

    def handle_dashboard_action(self, action_text):
        action = (action_text or "").strip().lower()
        if action in ("start a pomodoro", "plan recovery"):
            self.content_stack.setCurrentIndex(3)
            self._set_active_nav(self.btn_pomodoro)
            if action == "plan recovery":
                if hasattr(self.page_pomodoro, "prepare_recovery_break"):
                    try:
                        self.page_pomodoro.prepare_recovery_break(prefer_long=True)
                    except Exception:
                        pass
        elif action in ("schedule deep work", "block high priority"):
            self.content_stack.setCurrentIndex(0)
            self._set_active_nav(self.btn_tasks)
            if hasattr(self.page_tasks, "refresh_tasks"):
                try:
                    self.page_tasks.refresh_tasks()
                except Exception:
                    pass
        else:
            self.content_stack.setCurrentIndex(0)
            self._set_active_nav(self.btn_tasks)

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
            # Ensure task list reflects any settings changes (e.g., show completed)
            try:
                self.page_tasks.refresh_tasks()
            except Exception:
                pass

        # We keep this for compatibility, even if it doesn't change history looks
        if hasattr(self, 'page_history'):
            self.page_history.update_theme(theme)

        if hasattr(self, 'page_dashboard'):
            self.page_dashboard.update_theme(theme)

        if hasattr(self, 'page_report'):
            self.page_report.update_theme(theme)

        if hasattr(self, 'page_quick_stats'):
            self.page_quick_stats.update_theme(theme)
        if hasattr(self, 'page_settings'):
            try:
                if hasattr(self.page_settings, 'update_theme'):
                    self.page_settings.update_theme(theme)
            except Exception:
                pass
        # Pomodoro page has its own `apply_theme` which reloads settings like auto-start
        if hasattr(self, 'page_pomodoro'):
            try:
                if hasattr(self.page_pomodoro, 'apply_theme'):
                    self.page_pomodoro.apply_theme()
                elif hasattr(self.page_pomodoro, 'update_theme'):
                    self.page_pomodoro.update_theme(theme)
            except Exception:
                pass
        # Tasks page: let it reload settings (reminders, sounds)
        if hasattr(self, 'page_tasks'):
            try:
                if hasattr(self.page_tasks, 'apply_settings'):
                    self.page_tasks.apply_settings()
                elif hasattr(self.page_tasks, 'update_theme'):
                    self.page_tasks.update_theme(theme)
            except Exception:
                pass
        self._update_sidebar_logo()

    def _update_sidebar_logo(self):
        if not hasattr(self, "logo_icon"):
            return
        sidebar_w = self.sidebar.width() if hasattr(self, "sidebar") else self.width()
        sidebar_h = self.sidebar.height() if hasattr(self, "sidebar") else self.height()
        if hasattr(self, "sidebar_header_layout"):
            try:
                self.sidebar_header_layout.setContentsMargins(12, 12, 12, 12)
                self.sidebar_header_layout.setAlignment(
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
                )
            except Exception:
                pass

        # Compute header bounds and fit logo + text vertically without overlap.
        header_max_h = max(100, int(sidebar_h * 0.30))
        if hasattr(self, "sidebar_header"):
            self.sidebar_header.setMaximumHeight(header_max_h)
            header_h = self.sidebar_header.height() or header_max_h
        else:
            header_h = header_max_h

        margins = self.sidebar_header_layout.contentsMargins() if hasattr(self, "sidebar_header_layout") else None
        if margins:
            available_w = max(1, sidebar_w - margins.left() - margins.right())
            available_h = max(1, header_h - margins.top() - margins.bottom())
        else:
            available_w = max(1, sidebar_w - 20)
            available_h = max(1, header_h - 20)

        # Size title font first, then fit logo in remaining space.
        if hasattr(self, "logo_text"):
            font = self.logo_text.font()
            font.setPointSize(max(6, min(10, int(header_h / 14))))
            font.setBold(True)
            self.logo_text.setFont(font)
            text_h = QFontMetrics(font).height()
            self.logo_text.setFixedHeight(text_h)
            self.logo_text.setVisible(True)
        else:
            text_h = 0

        spacing = max(4, int(text_h * 0.6)) if hasattr(self, "sidebar_header_layout") else 6
        if hasattr(self, "sidebar_header_layout"):
            try:
                self.sidebar_header_layout.setSpacing(spacing)
            except Exception:
                pass

        available_h = max(1, available_h - text_h - spacing)

        target_w = max(40, min(120, available_w))
        target_h = max(40, min(120, available_h))
        target = min(target_w, target_h)
        self.logo_icon.setFixedSize(target, target)
        if self._logo_pixmap:
            inner = max(28, target - 14)
            scaled = self._logo_pixmap.scaled(
                inner,
                inner,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_icon.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_sidebar_logo()

    # --- STYLE LIGHT ---
    def set_light_theme(self):
        c = get_theme("Light")
        self.setStyleSheet(f"""
            /* GLOBAL */
            QMainWindow {{ background-color: {c['bg']}; color: {c['text']}; }}
            QWidget {{ color: {c['text']}; font-family: '{FONT_FAMILY}', 'Segoe UI'; }}
            QFrame#Sidebar {{ background-color: {c['card']}; border-right: 1px solid {c['border']}; }}
            QWidget#SidebarHeader {{ background-color: {c['card_alt']}; border-radius: 14px; margin: 12px; }}
            QLabel#SidebarLogo {{ background-color: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 6px; }}
            QLabel#SidebarTitle {{ font-weight: 800; color: {c['accent']}; }}
            QFrame#SidebarSeparator {{ background-color: {c['border']}; margin: 8px 10px; }}
            
            /* SIDEBAR BUTTONS */
            QFrame#Sidebar QPushButton[nav="true"] {{ background-color: transparent; padding: 12px 14px; border: none; border-radius: 10px; color: {c['deep']}; font-weight: bold; }}
            QFrame#Sidebar QPushButton[nav="true"]:hover {{ background-color: {c['accent_soft']}; color: {c['accent']}; }}
            QFrame#Sidebar QPushButton[nav="true"][active="true"] {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c['accent']}, stop:0.03 {c['accent']}, stop:0.03 {c['accent_soft']}, stop:1 {c['accent_soft']});
                color: {c['accent']};
            }}
            QFrame#Sidebar QPushButton[nav="true"][active="true"]:hover {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c['accent2']}, stop:0.03 {c['accent2']}, stop:0.03 {c['accent_soft']}, stop:1 {c['accent_soft']});
            }}
            
            /* SETTINGS SPECIFIC */
            QFrame#SettingsCard {{ background-color: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
            QLabel#SettingsLabel {{ color: {c['text']}; }}
            QComboBox {{ background-color: {c['input_bg']}; border: 1px solid {c['input_border']}; border-radius: 6px; padding: 5px; color: {c['text']}; }}
            QComboBox QAbstractItemView {{ background-color: {c['card']}; color: {c['text']}; selection-background-color: {c['accent_soft']}; selection-color: {c['accent']}; }}

            /* QMessageBox */
            QMessageBox {{ background-color: {c['card']}; }}
            QMessageBox QLabel {{ color: {c['text']}; }}
            QMessageBox QPushButton {{
                color: {c['text']};
                background-color: {c['accent_soft']};
                border: 1px solid {c['border']};
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QMessageBox QPushButton:hover {{ background-color: {c['border']}; }}
        """)

    # --- STYLE DARK ---
    def set_dark_theme(self):
        c = get_theme("Dark")
        self.setStyleSheet(f"""
            /* GLOBAL */
            QMainWindow {{ background-color: {c['bg']}; color: {c['text']}; }}
            QWidget {{ color: {c['text']}; font-family: '{FONT_FAMILY}', 'Segoe UI'; }}
            QFrame#Sidebar {{ background-color: {c['card']}; border-right: 1px solid {c['border']}; }}
            QWidget#SidebarHeader {{ background-color: {c['card_alt']}; border-radius: 14px; margin: 12px; }}
            QLabel#SidebarLogo {{ background-color: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 6px; }}
            QLabel#SidebarTitle {{ font-weight: 800; color: {c['accent']}; }}
            QFrame#SidebarSeparator {{ background-color: {c['border']}; margin: 8px 10px; }}
            
            /* SIDEBAR BUTTONS */
            QFrame#Sidebar QPushButton[nav="true"] {{ background-color: transparent; padding: 12px 14px; border: none; border-radius: 10px; color: {c['sub']}; font-weight: bold; }}
            QFrame#Sidebar QPushButton[nav="true"]:hover {{ background-color: {c['card_alt']}; color: {c['accent2']}; }}
            QFrame#Sidebar QPushButton[nav="true"][active="true"] {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c['accent2']}, stop:0.03 {c['accent2']}, stop:0.03 {c['card_alt']}, stop:1 {c['card_alt']});
                color: {c['accent']};
            }}
            QFrame#Sidebar QPushButton[nav="true"][active="true"]:hover {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c['accent']}, stop:0.03 {c['accent']}, stop:0.03 {c['card_alt']}, stop:1 {c['card_alt']});
            }}
            
            /* SETTINGS SPECIFIC */
            QFrame#SettingsCard {{ background-color: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
            QLabel#SettingsLabel {{ color: {c['text']}; }}
            QComboBox {{ background-color: {c['input_bg']}; border: 1px solid {c['input_border']}; border-radius: 6px; padding: 5px; color: {c['text']}; }}
            QComboBox QAbstractItemView {{ background-color: {c['input_bg']}; color: {c['text']}; selection-background-color: {c['accent2']}; selection-color: {c['text']}; }}

            /* QMessageBox */
            QMessageBox {{ background-color: {c['card']}; }}
            QMessageBox QLabel {{ color: {c['text']}; }}
            QMessageBox QPushButton {{
                color: {c['text']};
                background-color: {c['card_alt']};
                border: 1px solid {c['border']};
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QMessageBox QPushButton:hover {{ background-color: {c['border']}; }}
        """)


class _TransientWindowBlocker(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self._main_window = main_window
        self._suppress_until = 0.0
        self._debug = "--debug-windows" in sys.argv

    def suppress_for(self, ms):
        self._suppress_until = time.monotonic() + (ms / 1000.0)

    def eventFilter(self, obj, event):
        if not isinstance(obj, QWidget):
            return False

        et = event.type()
        if obj is self._main_window:
            return False

        # Proactively block top-level QLabel windows before they ever show.
        if isinstance(obj, QLabel) and obj.parent() is None:
            if et in (QEvent.Type.Polish, QEvent.Type.PolishRequest, QEvent.Type.Show):
                try:
                    obj.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
                except Exception:
                    pass
                if self._debug and et == QEvent.Type.Show:
                    try:
                        text = obj.text()
                    except Exception:
                        text = ""
                    try:
                        pix = obj.pixmap()
                    except Exception:
                        pix = None
                    print(f"[TransientBlocker] Blocked top-level QLabel text='{text}' has_pixmap={pix is not None}")
                try:
                    obj.hide()
                    if et == QEvent.Type.Show:
                        return True
                except Exception:
                    pass

        if et == QEvent.Type.Show and obj.isWindow():
            now = time.monotonic()
            if self._debug:
                try:
                    title = obj.windowTitle()
                    name = obj.objectName()
                    w = obj.width()
                    h = obj.height()
                    flags = int(obj.windowFlags())
                    parent = obj.parent().__class__.__name__ if obj.parent() else "None"
                    extra = ""
                    if isinstance(obj, QLabel):
                        try:
                            lbl_text = obj.text()
                            extra = f" text='{lbl_text}'"
                        except Exception:
                            extra = ""
                    print(f"[TransientBlocker] Show {obj.__class__.__name__} title='{title}' name='{name}' size={w}x{h} flags={flags} parent={parent}{extra}")
                except Exception:
                    pass
            if now < self._suppress_until:
                w = obj.width()
                h = obj.height()
                # Hide tiny/empty transient windows that can flash during page switches.
                if w <= 420 and h <= 180:
                    if self._debug:
                        title = obj.windowTitle()
                        print(f"[TransientBlocker] Hiding window: {obj.__class__.__name__} '{title}' {w}x{h}")
                    try:
                        obj.hide()
                        return True
                    except Exception:
                        return False
        return False

if __name__ == "__main__":
    try:
        init_db()
        app = QApplication(sys.argv)
        _install_qss_sanitizer()
        _install_qss_debug()
        
        icon_path = _app_icon_path()
        if icon_path:
            app.setWindowIcon(QIcon(icon_path))
            
        # Exit cleanly on Ctrl+C without a traceback.
        signal.signal(signal.SIGINT, lambda *_: app.quit())

        window = MainApp()
        window.showMaximized()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
