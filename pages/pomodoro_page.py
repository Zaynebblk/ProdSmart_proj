import json
import os
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QSpinBox, QApplication, QSystemTrayIcon,
                             QToolButton, QProgressBar, QScrollArea, QMessageBox, QSizePolicy, QGridLayout)
from PyQt6.QtCore import Qt, QTimer, QSize, QEvent, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPainterPath, QPen, QColor, QPixmap, QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QSoundEffect
from database.db_manager import get_db_connection
from pages.settings_page import Toggle

class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class PomodoroPage(QWidget):
    select_task_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        
        # Listes pour le style
        self.cards = []
        self.labels_main = []
        self.labels_sub = []
        self.spinboxes = []
        self.inputs_bg = []
        
        # Variables Timer & Settings State
        self.focus_time = 25
        self.short_break_time = 5
        self.long_break_time = 15
        self.intervals_goal = 4
        
        self.time_left = self.focus_time * 60
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.phase = "focus"
        self.sessions_completed = 0
        
        self.auto_start = False
        self.sound_effects = True
        self.enable_notifications = True
        
        # Sound Player Setup
        self.alarm_sound = QSoundEffect()
        sound_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "alarm.wav")
        if os.path.exists(sound_path):
            self.alarm_sound.setSource(QUrl.fromLocalFile(sound_path))
            self.alarm_sound.setVolume(0.5)

        self.last_notification_phase = None
        self._is_dark = False
        self._theme_colors = {}
        self._tray = None
        self._settings_path = None
        self._suppress_focus_mode_save = False
        
        # Task-linked session state
        self.current_task_id = None
        self.current_task_title = None

        self.setup_ui()
        self.apply_theme() # Load settings and colors
        self.connect_settings_signals() # Make spinboxes functional
        self._set_phase("focus", reset_time=True)

    def showEvent(self, event):
        self.apply_theme()
        super().showEvent(event)

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("PomodoroScrollContent")
        self.scroll_area.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll_area)

        self.main_layout = QHBoxLayout(self.scroll_content)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(30)

        # === GAUCHE ===
        self.left_container = QFrame()
        self.cards.append(self.left_container)
        
        self.left_vbox = QVBoxLayout(self.left_container)
        self.left_vbox.setContentsMargins(50, 40, 50, 40)
        
        self.header_title = QLabel("Pomodoro Timer")
        self.header_title.setStyleSheet("font-size: 28px; font-weight: 800;")
        self.labels_main.append(self.header_title)
        
        self.header_sub = QLabel("Deep work made simple")
        self.header_sub.setStyleSheet("font-size: 15px;")
        self.labels_sub.append(self.header_sub)

        # Current task card
        self.current_task_card = QFrame()
        self.current_task_card.setObjectName("CurrentTaskCard")
        current_layout = QVBoxLayout(self.current_task_card)
        current_layout.setContentsMargins(18, 16, 18, 16)

        header_row = QHBoxLayout()
        self.current_task_header = QLabel("CURRENT TASK")
        self.select_task_btn = QPushButton("Select Task")
        self.select_task_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_task_btn.clicked.connect(self.select_task_requested.emit)
        header_row.addWidget(self.current_task_header)
        header_row.addStretch()
        header_row.addWidget(self.select_task_btn)
        current_layout.addLayout(header_row)

        self.current_task_title_label = QLabel("No Task Selected")
        current_layout.addWidget(self.current_task_title_label)

        self.session_progress_bar = QProgressBar()
        self.session_progress_bar.setFixedHeight(8)
        current_layout.addWidget(self.session_progress_bar)

        # Focus mode card
        self.focus_mode_card = QFrame()
        self.focus_mode_card.setObjectName("FocusModeCard")
        focus_layout = QVBoxLayout(self.focus_mode_card)
        self.focus_mode_title = QLabel("Focus Mode Active")
        self.focus_mode_desc = QLabel("Notifications are currently blocked")
        self.focus_mode_toggle = Toggle(width=44)
        self.focus_mode_toggle.stateChanged.connect(self.on_focus_mode_toggled)
        focus_layout.addWidget(self.focus_mode_title)
        focus_layout.addWidget(self.focus_mode_desc)
        focus_layout.addWidget(self.focus_mode_toggle)

        current_layout.addWidget(self.focus_mode_card)
        
        self.left_vbox.addWidget(self.header_title)
        self.left_vbox.addWidget(self.header_sub)
        self.left_vbox.addWidget(self.current_task_card)

        self.badge = QLabel("✨ FOCUS TIME")
        self.badge.setFixedSize(130, 32)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_vbox.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignCenter)

        self.timer_label = QLabel("25:00")
        self.timer_label.setFixedSize(320, 320)
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_vbox.addWidget(self.timer_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start Session")
        self.btn_start.setFixedSize(160, 50)
        self.btn_start.clicked.connect(self.toggle_timer)
        
        self.btn_reset = QPushButton("↺ Reset")
        self.btn_reset.setFixedSize(100, 50)
        self.btn_reset.clicked.connect(self.reset_timer)
        # Stop button: stops current running session but does not reset completed counters
        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setFixedSize(100, 50)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_timer)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        self.left_vbox.addLayout(btn_layout)

        self.sessions_count = QLabel("0")
        self.sessions_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sessions_count.setStyleSheet("font-weight: 900; font-size: 32px;")
        self.labels_main.append(self.sessions_count)
        self.left_vbox.addWidget(self.sessions_count)
        self.left_vbox.addStretch()

        # === DROITE (Settings) ===
        self.settings_card = self.create_card("⚙ Settings")
        self.focus_input = self.add_styled_setting(self.settings_card, "Focus Duration", 25)
        self.short_input = self.add_styled_setting(self.settings_card, "Short Break", 5)
        self.long_input = self.add_styled_setting(self.settings_card, "Long Break", 15)
        self.interval_input = self.add_styled_setting(self.settings_card, "Intervals", 4)

        self.settings_stack = QWidget()
        settings_layout = QVBoxLayout(self.settings_stack)
        settings_layout.addWidget(self.settings_card)
        settings_layout.addStretch()

        self.main_layout.addWidget(self.left_container, stretch=1)
        self.main_layout.addWidget(self.settings_stack, stretch=0)

    # --- SETTINGS LOGIC ---
    def connect_settings_signals(self):
        """Connects spinboxes to save values to settings.json instantly"""
        self.focus_input.valueChanged.connect(lambda v: self._save_settings_value("focus_duration", v))
        self.short_input.valueChanged.connect(lambda v: self._save_settings_value("short_break", v))
        self.long_input.valueChanged.connect(lambda v: self._save_settings_value("long_break", v))
        self.interval_input.valueChanged.connect(lambda v: self._save_settings_value("intervals", v))

    def load_settings_data(self):
        theme, auto, notify, sound = "Light", False, True, True
        f_dur, s_brk, l_brk, inter = 25, 5, 15, 4
        
        self._settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")
        
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, "r") as f:
                    data = json.load(f)
                    theme = data.get("theme", "Light")
                    auto = data.get("auto_start_pomodoro", False)
                    notify = data.get("enable_notifications", True)
                    sound = data.get("sound_effects", True)
                    # Load durations
                    f_dur = data.get("focus_duration", 25)
                    s_brk = data.get("short_break", 5)
                    l_brk = data.get("long_break", 15)
                    inter = data.get("intervals", 4)
            except: pass

        # Update UI values without triggering save
        self.focus_input.blockSignals(True); self.focus_input.setValue(f_dur); self.focus_input.blockSignals(False)
        self.short_input.blockSignals(True); self.short_input.setValue(s_brk); self.short_input.blockSignals(False)
        self.long_input.blockSignals(True); self.long_input.setValue(l_brk); self.long_input.blockSignals(False)
        self.interval_input.blockSignals(True); self.interval_input.setValue(inter); self.interval_input.blockSignals(False)

        return theme, auto, notify, sound

    # --- TIMER CORE ---
    def toggle_timer(self):
        if self.timer.isActive():
            self.timer.stop()
            self.btn_start.setText("▶ Start Session")
        else:
            if not self.current_task_id:
                QMessageBox.warning(self, "No Task", "Please select a task first.")
                return
            self.timer.start(1000)
            self.btn_start.setText("⏸ Pause")

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            mins, secs = divmod(self.time_left, 60)
            self.timer_label.setText(f"{mins:02d}:{secs:02d}")
        else:
            self.timer.stop()
            self._on_phase_finished()

    def _on_phase_finished(self):
        if self.sound_effects:
            self.alarm_sound.play()
        
        if self.phase == "focus":
            self.sessions_completed += 1
            self.sessions_count.setText(str(self.sessions_completed))
            
            # Logic for Long Break vs Short Break
            if self.sessions_completed % self.interval_input.value() == 0:
                self._set_phase("long_break")
            else:
                self._set_phase("break")
        else:
            self._set_phase("focus")

        if self.auto_start:
            QTimer.singleShot(1000, self.toggle_timer)

    def _set_phase(self, phase, reset_time=True):
        self.phase = phase
        if phase == "focus":
            self.time_left = self.focus_input.value() * 60
            self.badge.setText("✨ FOCUS TIME")
        elif phase == "long_break":
            self.time_left = self.long_input.value() * 60
            self.badge.setText("🔋 LONG BREAK")
        else:
            self.time_left = self.short_input.value() * 60
            self.badge.setText("☕ BREAK TIME")
        
        mins, secs = divmod(self.time_left, 60)
        self.timer_label.setText(f"{mins:02d}:{secs:02d}")

    def reset_timer(self):
        self.timer.stop()
        self.btn_start.setText("▶ Start Session")
        self.sessions_completed = 0
        self.sessions_count.setText("0")
        self._set_phase("focus")

    def stop_timer(self):
        """Stop the current session without resetting completed session counters."""
        if self.timer.isActive():
            self.timer.stop()
        self.btn_start.setText("▶ Start Session")
        # Reset visible timer to full phase duration but keep sessions_completed
        self._set_phase("focus", reset_time=True)

    # --- UI & THEME HELPERS ---
    def apply_theme(self):
        raw_theme, auto, notify, sound = self.load_settings_data()
        self.auto_start, self.enable_notifications, self.sound_effects = auto, notify, sound
        is_dark = str(raw_theme).lower() == "dark"
        self._is_dark = is_dark
        
        c = {"bg": "#121212", "card": "#1e1e1e", "text": "#ffffff", "sub": "#a0a0a0", "in": "#2d2d2d", "brd": "#333333"} if is_dark else \
            {"bg": "#f8fafc", "card": "#ffffff", "text": "#1e293b", "sub": "#64748b", "in": "#f1f5f9", "brd": "#edf2f7"}
        
        self.setStyleSheet(f"background-color: {c['bg']};")
        for card in self.cards: card.setStyleSheet(f"background-color: {c['card']}; border-radius: 30px; border: 1px solid {c['brd']};")
        for lbl in self.labels_main: lbl.setStyleSheet(f"color: {c['text']}; background: transparent; border: none;")
        for lbl in self.labels_sub: lbl.setStyleSheet(f"color: {c['sub']}; background: transparent; border: none;")
        for ib in self.inputs_bg: ib.setStyleSheet(f"background-color: {c['in']}; border: 1px solid {c['brd']}; border-radius: 10px;")
        for sb in self.spinboxes: sb.setStyleSheet(f"color: {c['text']}; background: transparent; border: none; font-weight: bold;")
        
        self.timer_label.setStyleSheet(f"font-size: 85px; font-weight: 900; color: {c['text']}; border: 12px solid #3b82f6; border-radius: 160px;")
        self.badge.setStyleSheet("background-color: #eff6ff; color: #2563eb; border-radius: 16px; font-weight: bold;")
        self._sync_focus_mode_toggle()

    def create_card(self, title):
        card = QFrame()
        self.cards.append(card)
        layout = QVBoxLayout(card)
        t = QLabel(title)
        t.setStyleSheet("font-size: 18px; font-weight: 800;")
        self.labels_main.append(t)
        layout.addWidget(t)
        return card

    def add_styled_setting(self, card, label_text, default_val):
        lbl = QLabel(label_text); self.labels_sub.append(lbl)
        container = QFrame(); container.setFixedHeight(45); self.inputs_bg.append(container)
        lay = QHBoxLayout(container)
        spin = NoWheelSpinBox(); spin.setRange(1, 120); spin.setValue(default_val); self.spinboxes.append(spin)
        lay.addWidget(spin)
        card.layout().addWidget(lbl); card.layout().addWidget(container)
        return spin

    def _sync_focus_mode_toggle(self):
        self._suppress_focus_mode_save = True
        self.focus_mode_toggle.setChecked(not self.enable_notifications)
        self._suppress_focus_mode_save = False

    def on_focus_mode_toggled(self, state):
        if self._suppress_focus_mode_save: return
        self.enable_notifications = not state
        self.sound_effects = not state
        self._save_settings_value("enable_notifications", self.enable_notifications)
        self._save_settings_value("sound_effects", self.sound_effects)

    def _save_settings_value(self, key, value):
        if not self._settings_path: return
        try:
            with open(self._settings_path, "r") as f: data = json.load(f)
            data[key] = value
            with open(self._settings_path, "w") as f: json.dump(data, f, indent=4)
        except: pass

    def set_task(self, task_id, title):
        self.current_task_id = task_id
        self.current_task_title_label.setText(title)