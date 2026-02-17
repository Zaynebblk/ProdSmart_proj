import json
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, 
                             QPushButton, QMessageBox, QFrame, QHBoxLayout, 
                             QScrollArea, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF, pyqtProperty
from PyQt6.QtGui import QPainter, QColor

# --- CUSTOM TOGGLE SWITCH CLASS ---
class Toggle(QCheckBox):
    """
    A custom QCheckBox that looks like a modern iOS/Android toggle switch.
    """
    def __init__(self, width=50, bg_color="#777", circle_color="#DDD", active_color="#3b82f6"):
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


# --- MAIN SETTINGS PAGE ---
class SettingsPage(QWidget):
    settings_saved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_current_setting()

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
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #3b82f6; margin-bottom: 10px;")
        self.content_layout.addWidget(title)

        # --- STYLE FOR COMBOBOXES ---
        self.combo_style = """
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 5px 10px;
                background-color: #ffffff;
                color: #333333;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #333333;
                selection-background-color: #3b82f6;
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
        
        self.combo_theme = QComboBox()
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

        # Default Priority
        lbl_prio = QLabel("Default task priority")
        lbl_prio.setObjectName("SettingsLabel")
        lbl_prio.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.combo_priority = QComboBox()
        
        # --- MODIFIED LINE: ADDED "Too Low" ---
        self.combo_priority.addItems(["Too Low", "Low", "Medium", "High"])
        
        self.combo_priority.setMinimumHeight(40)
        self.combo_priority.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_priority.setStyleSheet(self.combo_style)

        tasks_layout.addWidget(lbl_prio)
        tasks_layout.addWidget(self.combo_priority)

        # Show Completed
        result_completed = self.create_toggle_row("Show completed tasks", "Display completed tasks in the task list")
        self.toggle_completed = result_completed['toggle']
        tasks_layout.addLayout(result_completed['layout'])

        # Task Reminders
        result_reminders = self.create_toggle_row("Task reminders", "Remind me about upcoming deadlines")
        self.toggle_reminders = result_reminders['toggle']
        tasks_layout.addLayout(result_reminders['layout'])
        
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


        # --- SAVE BUTTON ---
        self.content_layout.addSpacing(10)
        btn_save = QPushButton("Save Changes")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self.save_settings)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; 
                color: white; 
                padding: 15px; 
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.content_layout.addWidget(btn_save)
        self.content_layout.addStretch()

        # Finalize Scroll Area
        self.scroll.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll)

    # --- HELPERS ---
    def create_section_header(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("SettingsLabel")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 10px;")
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

                    # Task Defaults
                    prio = data.get("default_priority", "Medium")
                    idx_prio = self.combo_priority.findText(prio)
                    if idx_prio >= 0: self.combo_priority.setCurrentIndex(idx_prio)

                    # Toggles
                    self.toggle_completed.setChecked(data.get("show_completed", True))
                    self.toggle_reminders.setChecked(data.get("task_reminders", True))
                    self.toggle_notify.setChecked(data.get("enable_notifications", True))
                    self.toggle_autostart.setChecked(data.get("auto_start_pomodoro", False))
                    self.toggle_sound.setChecked(data.get("sound_effects", True))
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        data = {
            "theme": self.combo_theme.currentText(),
            "default_priority": self.combo_priority.currentText(),
            "show_completed": self.toggle_completed.isChecked(),
            "task_reminders": self.toggle_reminders.isChecked(),
            "enable_notifications": self.toggle_notify.isChecked(),
            "auto_start_pomodoro": self.toggle_autostart.isChecked(),
            "sound_effects": self.toggle_sound.isChecked()
        }
        
        json_path = self.get_settings_path()
        try:
            with open(json_path, "w") as f:
                json.dump(data, f, indent=4)
            
            # Notify MainApp to update theme
            self.settings_saved.emit()
            
            QMessageBox.information(self, "Saved", "Settings saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save settings: {e}")