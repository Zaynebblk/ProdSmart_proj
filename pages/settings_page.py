import json
import os
import sys
import subprocess
from urllib.parse import urlparse
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, 
                             QPushButton, QMessageBox, QFrame, QHBoxLayout, 
                             QScrollArea, QCheckBox, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF, pyqtProperty
from PyQt6.QtGui import QPainter, QColor
from resources.theme import get_theme, FONT_FAMILY, rgba
from resources.api_client import check_server_ready, set_base_url
from resources.task_types import TASK_TYPES, UNCATEGORIZED_LABEL

# --- CUSTOM TOGGLE SWITCH CLASS ---
class Toggle(QCheckBox):
    """
    A custom QCheckBox that looks like a modern iOS/Android toggle switch.
    """
    def __init__(self, width=50, bg_color="#777", circle_color="#DDD", active_color="#3078CD"):
        super().__init__()
        self.setFixedSize(width, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Colors
        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color

        # Animation variable
        self._circle_position = 3
        
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(300)

        self.stateChanged.connect(self.start_transition)

    # Property for animation
    def get_circle_position(self):
        return self._circle_position

    def set_circle_position(self, pos):
        self._circle_position = pos
        self.update()

    circle_position = pyqtProperty(float, get_circle_position, set_circle_position)

    def start_transition(self, state):
        self.animation.stop()
        if state:
            self.animation.setEndValue(self.width() - 26)
        else:
            self.animation.setEndValue(3)
        self.animation.start()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw Background
        rect = QRectF(0, 0, self.width(), self.height())
        if self.isChecked():
            p.setBrush(QColor(self._active_color))
        else:
            p.setBrush(QColor(self._bg_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 14, 14)

        # Draw Circle
        p.setBrush(QColor(self._circle_color))
        p.drawEllipse(QRectF(self._circle_position, 3, 22, 22))
        p.end()


class NoWheelComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ensure_font_size()

    def _ensure_font_size(self):
        font = self.font()
        if font.pointSize() <= 0:
            font.setPointSize(10)
            self.setFont(font)
        view = self.view()
        if view:
            view_font = view.font()
            if view_font.pointSize() <= 0:
                view_font.setPointSize(10)
                view.setFont(view_font)

    def wheelEvent(self, event):
        event.ignore()


# --- MAIN SETTINGS PAGE ---
class SettingsPage(QWidget):
    settings_saved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("SettingsPage")
        self.setup_ui()
        self.load_current_setting()
        self.update_theme("Light")

    def setup_ui(self):
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll Area (in case settings get long)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Make scroll area background transparent
        self.scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget { background: transparent; }")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(40, 40, 40, 40)
        self.content_layout.setSpacing(25)

        # Title
        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #3078CD; margin-bottom: 10px;")
        self.page_title = title
        self.content_layout.addWidget(title)

        # --- STYLE FOR COMBOBOXES ---
        self.combo_style = """
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 5px 10px;
                background-color: #ffffff;
                color: #333333;
                font-size: 10.5pt;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #333333;
                selection-background-color: #3078CD;
                selection-color: #ffffff;
                outline: 0px;
            }
        """

        # --- SECTION 1: APPEARANCE ---
        self.content_layout.addWidget(self.create_section_header("Appearance"))
        
        self.card_theme = QFrame()
        self.card_theme.setObjectName("SettingsCard")
        theme_layout = QVBoxLayout(self.card_theme)
        theme_layout.setContentsMargins(20, 20, 20, 20)

        lbl_theme = QLabel("App Theme")
        lbl_theme.setObjectName("SettingsLabel")
        lbl_theme.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.combo_theme = NoWheelComboBox()
        self.combo_theme.addItems(["Light", "Dark"])
        self.combo_theme.setMinimumHeight(40)
        self.combo_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_theme.setStyleSheet(self.combo_style)
        
        theme_layout.addWidget(lbl_theme)
        theme_layout.addWidget(self.combo_theme)
        self.content_layout.addWidget(self.card_theme)


        # --- SECTION 2: TASK MANAGEMENT ---
        self.content_layout.addWidget(self.create_section_header("Task Management"))

        self.card_tasks = QFrame()
        self.card_tasks.setObjectName("SettingsCard")
        tasks_layout = QVBoxLayout(self.card_tasks)
        tasks_layout.setContentsMargins(20, 20, 20, 20)
        tasks_layout.setSpacing(20)

        # Default Important
        result_default_important = self.create_toggle_row(
            "Default important",
            "New tasks start marked as important"
        )
        self.toggle_default_important = result_default_important["toggle"]
        tasks_layout.addLayout(result_default_important["layout"])

        # Show Completed
        result_completed = self.create_toggle_row("Show completed tasks", "Display completed tasks in the task list")
        self.toggle_completed = result_completed['toggle']
        tasks_layout.addLayout(result_completed['layout'])

        # Task Reminders
        result_reminders = self.create_toggle_row("Task reminders", "Remind me about upcoming deadlines")
        self.toggle_reminders = result_reminders['toggle']
        tasks_layout.addLayout(result_reminders['layout'])

        # Task Type Filters
        lbl_type_filters = QLabel("Task type filters")
        lbl_type_filters.setObjectName("SettingsLabel")
        lbl_type_filters.setStyleSheet("font-size: 14px; font-weight: bold;")
        tasks_layout.addWidget(lbl_type_filters)

        self.type_checks = {}
        for type_label in TASK_TYPES + [UNCATEGORIZED_LABEL]:
            cb = QCheckBox(type_label)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setChecked(True)
            self.type_checks[type_label] = cb
            tasks_layout.addWidget(cb)
        
        # Reminder repeat interval (minutes)
        lbl_repeat = QLabel("Reminder repeat (min)")
        lbl_repeat.setObjectName("SettingsLabel")
        lbl_repeat.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.combo_repeat = NoWheelComboBox()
        self.combo_repeat.addItems(["5", "10", "15", "30"])
        self.combo_repeat.setMinimumHeight(40)
        self.combo_repeat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_repeat.setStyleSheet(self.combo_style)
        tasks_layout.addWidget(lbl_repeat)
        tasks_layout.addWidget(self.combo_repeat)
        
        self.content_layout.addWidget(self.card_tasks)


        # --- SECTION 3: GENERAL / POMODORO ---
        self.content_layout.addWidget(self.create_section_header("General"))

        self.card_general = QFrame()
        self.card_general.setObjectName("SettingsCard")
        general_layout = QVBoxLayout(self.card_general)
        general_layout.setContentsMargins(20, 20, 20, 20)
        general_layout.setSpacing(20)

        # Notifications
        result_notify = self.create_toggle_row("Enable notifications", "Receive alerts for upcoming tasks")
        self.toggle_notify = result_notify['toggle']
        general_layout.addLayout(result_notify['layout'])

        # Auto-Start Pomodoro
        result_autostart = self.create_toggle_row("Auto-start next session", "Automatically begin the next Pomodoro session")
        self.toggle_autostart = result_autostart['toggle']
        general_layout.addLayout(result_autostart['layout'])

        # Sounds
        result_sound = self.create_toggle_row("Sound effects", "Play sound when timer completes")
        self.toggle_sound = result_sound['toggle']
        general_layout.addLayout(result_sound['layout'])

        self.content_layout.addWidget(self.card_general)


        # --- SECTION 4: COLLABORATION ---
        self.content_layout.addWidget(self.create_section_header("Collaboration"))

        self.card_collab = QFrame()
        self.card_collab.setObjectName("SettingsCard")
        collab_layout = QVBoxLayout(self.card_collab)
        collab_layout.setContentsMargins(20, 20, 20, 20)
        collab_layout.setSpacing(12)

        lbl_server = QLabel("Server URL")
        lbl_server.setObjectName("SettingsLabel")
        lbl_server.setStyleSheet("font-size: 14px; font-weight: bold;")
        collab_layout.addWidget(lbl_server)

        self.input_cloud_url = QLineEdit()
        self.input_cloud_url.setPlaceholderText("http://127.0.0.1:8000")
        self.input_cloud_url.setMinimumHeight(40)
        self.input_cloud_url.setText("http://127.0.0.1:8000")
        collab_layout.addWidget(self.input_cloud_url)

        self.btn_start_server = QPushButton("Start Server")
        self.btn_start_server.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_server.clicked.connect(self.start_cloud_server)
        collab_layout.addWidget(self.btn_start_server)

        self.server_status = QLabel("Server status: unknown")
        self.server_status.setObjectName("SettingsLabel")
        self.server_status.setStyleSheet("font-size: 12px; color: #64748b;")
        collab_layout.addWidget(self.server_status)

        self.content_layout.addWidget(self.card_collab)


        # --- SAVE BUTTON ---
        self.content_layout.addSpacing(10)
        btn_save = QPushButton("Save Changes")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self.save_settings)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #3078CD; 
                color: white; 
                padding: 15px; 
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #25456B; }
        """)
        self.content_layout.addWidget(btn_save)
        self.save_button = btn_save
        self.content_layout.addStretch()

        # Finalize Scroll Area
        self.scroll.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll)

    # --- HELPERS ---
    def create_section_header(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("SettingsSection")
        return lbl

    def create_toggle_row(self, title, subtitle):
        """Creates a horizontal layout with Title/Subtitle on left and Toggle on right."""
        row_layout = QHBoxLayout()
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("SettingsLabel") # For Theme ID
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748b;")
        
        text_layout.addWidget(lbl_title)
        text_layout.addWidget(lbl_sub)
        
        toggle = Toggle()
        
        row_layout.addLayout(text_layout)
        row_layout.addStretch()
        row_layout.addWidget(toggle)
        
        return {'layout': row_layout, 'toggle': toggle}

    def get_settings_path(self):
        return os.path.join(os.getcwd(), "settings.json")

    def load_current_setting(self):
        try:
            path = self.get_settings_path()
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    
                    # Theme
                    theme = data.get("theme", "Light")
                    idx = self.combo_theme.findText(theme)
                    if idx >= 0: self.combo_theme.setCurrentIndex(idx)

                    # Default important
                    if "default_important" in data:
                        self.toggle_default_important.setChecked(bool(data.get("default_important", False)))
                    else:
                        prio = str(data.get("default_priority", "")).strip().lower()
                        self.toggle_default_important.setChecked(prio in ("high", "medium"))

                    # Toggles
                    self.toggle_completed.setChecked(data.get("show_completed", True))
                    self.toggle_reminders.setChecked(data.get("task_reminders", True))
                    # Reminder repeat minutes
                    repeat_min = str(data.get("reminder_repeat_minutes", 10))
                    idx_repeat = self.combo_repeat.findText(repeat_min)
                    if idx_repeat >= 0: self.combo_repeat.setCurrentIndex(idx_repeat)
                    self.toggle_notify.setChecked(data.get("enable_notifications", True))
                    self.toggle_autostart.setChecked(data.get("auto_start_pomodoro", False))
                    self.toggle_sound.setChecked(data.get("sound_effects", True))

                    type_filters = data.get("task_type_filters")
                    if isinstance(type_filters, list) and type_filters:
                        allowed = set(str(t) for t in type_filters)
                        for label, cb in self.type_checks.items():
                            cb.setChecked(label in allowed)
                    else:
                        for cb in self.type_checks.values():
                            cb.setChecked(True)

                    if hasattr(self, "input_cloud_url"):
                        cloud_url = str(data.get("cloud_base_url", "")).strip()
                        if not cloud_url:
                            cloud_url = "http://127.0.0.1:8000"
                        self.input_cloud_url.setText(cloud_url)
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        data = {
            "theme": self.combo_theme.currentText(),
            "default_important": self.toggle_default_important.isChecked(),
            "show_completed": self.toggle_completed.isChecked(),
            "task_reminders": self.toggle_reminders.isChecked(),
            "reminder_repeat_minutes": int(self.combo_repeat.currentText()),
            "enable_notifications": self.toggle_notify.isChecked(),
            "auto_start_pomodoro": self.toggle_autostart.isChecked(),
            "sound_effects": self.toggle_sound.isChecked(),
            "task_type_filters": [label for label, cb in self.type_checks.items() if cb.isChecked()],
        }
        if hasattr(self, "input_cloud_url"):
            data["cloud_base_url"] = self.input_cloud_url.text().strip()
        
        json_path = self.get_settings_path()
        try:
            existing = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r") as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}
            existing.update(data)
            data = existing
            with open(json_path, "w") as f:
                json.dump(data, f, indent=4)
            
            # Notify MainApp to update theme
            self.settings_saved.emit()
            
            QMessageBox.information(self, "Saved", "Settings saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save settings: {e}")

    def update_theme(self, theme):
        c = get_theme(theme)
        accent_soft = c.get("accent_soft", c["card"])
        deep = c.get("deep", c["accent"])
        self.setStyleSheet(
            f"QWidget#SettingsPage {{ background: {c['bg']}; font-family: '{FONT_FAMILY}', 'Segoe UI'; }}"
            f"QLabel#SettingsLabel {{ color: {c['text']}; }}"
            f"QCheckBox {{ color: {c['text']}; font-size: 12px; }}"
            f"QLabel#SettingsSection {{ color: {deep}; font-size: 18px; font-weight: 900; "
            f"padding-bottom: 6px; border-bottom: 2px solid {accent_soft}; letter-spacing: 0.5px; }}"
        )
        if hasattr(self, "page_title"):
            self.page_title.setStyleSheet(
                f"font-size: 32px; font-weight: bold; color: {c['accent']}; margin-bottom: 10px;"
            )

        self.combo_style = f"""
            QComboBox {{
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 5px 10px;
                background-color: {c['input_bg']};
                color: {c['text']};
                font-size: 10.5pt;
            }}
            QComboBox:hover {{
                border: 1px solid {c['accent']};
                background-color: {rgba(c['input_bg'], 0.96)};
            }}
            QComboBox:focus {{
                border: 1px solid {c['accent2']};
                background-color: {rgba(c['input_bg'], 0.94)};
            }}
            QComboBox::drop-down {{
                border: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['card']};
                color: {c['text']};
                selection-background-color: {c['accent']};
                selection-color: white;
                outline: 0px;
            }}
        """

        for combo in (self.combo_theme, self.combo_repeat):
            if not combo:
                continue
            combo.setStyleSheet(self.combo_style)
            try:
                combo._ensure_font_size()
            except Exception:
                pass

        if hasattr(self, "input_cloud_url"):
            self.input_cloud_url.setStyleSheet(
                f"QLineEdit {{ border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 10px; "
                f"background-color: {c['input_bg']}; color: {c['text']}; font-size: 10.5pt; }}"
                f"QLineEdit:focus {{ border: 1px solid {c['accent']}; }}"
            )
        if hasattr(self, "btn_start_server"):
            self.btn_start_server.setStyleSheet(
                f"QPushButton {{ background-color: {c['accent']}; color: white; border-radius: 8px; "
                f"padding: 10px 14px; font-weight: 700; }}"
                f"QPushButton:hover {{ background-color: {c['deep']}; }}"
            )

        card_bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {rgba(c['card'], 0.96)}, stop:1 {rgba(accent_soft, 0.35)})"
        for card in (self.card_theme, self.card_tasks, self.card_general, getattr(self, "card_collab", None)):
            if not card:
                continue
            card.setStyleSheet(
                f"QFrame#SettingsCard {{ background: {card_bg}; border: 1px solid {c['border']}; "
                f"border-left: 4px solid {c['accent']}; border-radius: 14px; }}"
            )

        if hasattr(self, "save_button"):
            self.save_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['accent']};
                    color: white;
                    padding: 15px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 16px;
                }}
                QPushButton:hover {{ background-color: {deep}; }}
            """)

        toggles = []
        for attr in ("toggle_completed", "toggle_reminders", "toggle_notify", "toggle_autostart", "toggle_sound", "toggle_default_important"):
            if hasattr(self, attr):
                toggles.append(getattr(self, attr))
        for t in toggles:
            try:
                t._bg_color = c["border"]
                t._active_color = c["accent"]
                t._circle_color = c["card"]
                t.update()
            except Exception:
                pass

        if hasattr(self, "server_status"):
            self.server_status.setStyleSheet(f"font-size: 12px; color: {c['sub']};")

    def _is_local_url(self, url):
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            return host in ("127.0.0.1", "localhost")
        except Exception:
            return False

    def start_cloud_server(self):
        url = ""
        if hasattr(self, "input_cloud_url"):
            url = self.input_cloud_url.text().strip()
        if not url:
            url = "http://127.0.0.1:8000"

        if not self._is_local_url(url):
            QMessageBox.information(
                self,
                "Server URL",
                "The Server URL points to another machine. Start the server on that machine, or change the URL to 127.0.0.1."
            )
            return

        try:
            set_base_url(url)
        except Exception:
            pass

        # If already running, no need to start a new one
        if check_server_ready(url, timeout=0.4):
            if hasattr(self, "server_status"):
                self.server_status.setText("Server status: running")
            QMessageBox.information(self, "Server", "Server is already running.")
            return

        server_path = os.path.join(os.getcwd(), "server", "main.py")
        if not os.path.exists(server_path):
            QMessageBox.warning(self, "Server", "Server entrypoint not found (server/main.py).")
            return

        creationflags = 0
        if os.name == "nt":
            try:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            except Exception:
                creationflags = 0

        try:
            subprocess.Popen(
                [sys.executable, server_path],
                cwd=os.getcwd(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            if hasattr(self, "server_status"):
                self.server_status.setText("Server status: starting...")
            QMessageBox.information(self, "Server", "Server started. Please try login again in a few seconds.")
        except Exception as e:
            QMessageBox.warning(self, "Server", f"Could not start server: {e}")
