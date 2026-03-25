import json
import os
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QSpinBox, QApplication, QSystemTrayIcon,
                             QToolButton, QProgressBar, QScrollArea, QMessageBox, QSizePolicy, QGridLayout, QStyle)
from PyQt6.QtCore import Qt, QTimer, QSize, QEvent, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPainterPath, QPen, QColor, QPixmap, QDesktopServices
from PyQt6.QtCore import QUrl
from database.db_manager import get_db_connection
from pages.settings_page import Toggle
from resources.theme import get_theme, FONT_FAMILY
try:
    import PyQt6.sip as sip
except Exception:
    try:
        import sip  # type: ignore
    except Exception:
        sip = None
from resources.priority import normalize_priority, priority_session_label

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
        
        # Variables Timer
        self.focus_time = 25
        self.time_left = self.focus_time * 60
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.phase = "focus"
        self.sessions_completed = 0
        self.auto_start = False
        self.sound_effects = True
        self.enable_notifications = True
        self.last_notification_phase = None
        self._is_dark = False
        self._theme_colors = {}
        self._tray = None
        self._settings_path = None
        self._suppress_focus_mode_save = False
        self._current_task_border_color = None
        self._current_task_style_base = ""
        self._pre_focus_notifications = None
        self._pre_focus_sound = None
        self._focus_assist_prompted = False
        self._force_system_focus_page = False

        # Task-linked session state
        self.current_task_id = None
        self.current_task_title = None
        self.current_task_priority = None
        self.session_started_at = None
        self.session_task_id = None
        self.session_task_title = None
        self.session_task_priority = None
        self.session_duration_min = None
        self.plan_enabled = True
        self.plan_index = 0
        self.plan_phases = []
        self.plan_focus_spins = []
        self.plan_break_spins = []
        self.plan_row_widgets = []
        self.plan_badges = []
        self.plan_rows = []
        self.plan_label_chips = []
        self._last_interval_value = None
        
        self.setup_ui()
        self._rebuild_plan_inputs()
        self._set_phase("focus", reset_time=True, notify=False)

    def showEvent(self, event):
        """S'active quand on clique sur l'onglet"""
        self.apply_theme()
        super().showEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_sizes()

    def _prune_dead_widgets(self):
        def _alive(widget):
            if widget is None:
                return False
            if sip:
                try:
                    if sip.isdeleted(widget):
                        return False
                except Exception:
                    pass
            try:
                widget.objectName()
            except RuntimeError:
                return False
            return True

        self.spinboxes = [w for w in self.spinboxes if _alive(w)]
        self.inputs_bg = [w for w in self.inputs_bg if _alive(w)]
        self.labels_main = [w for w in self.labels_main if _alive(w)]
        self.labels_sub = [w for w in self.labels_sub if _alive(w)]
        self.cards = [w for w in self.cards if _alive(w)]

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("PomodoroScrollContent")
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_area.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll_area)

        self.main_layout = QHBoxLayout(self.scroll_content)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(30)

        # === GAUCHE ===
        self.left_container = QFrame()
        self.cards.append(self.left_container)
        self.left_container.installEventFilter(self)
        
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
        self.current_task_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        current_layout = QVBoxLayout(self.current_task_card)
        current_layout.setContentsMargins(18, 16, 18, 16)
        current_layout.setSpacing(10)

        header_row = QHBoxLayout()
        self.current_task_header = QLabel("CURRENT TASK")
        self.current_task_header.setObjectName("CurrentTaskHeader")
        self.select_task_btn = QPushButton("Select Task")
        self.select_task_btn.setObjectName("SelectTaskBtn")
        self.select_task_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_task_btn.clicked.connect(self._request_task_selection)
        header_row.addWidget(self.current_task_header)
        header_row.addStretch()
        header_row.addWidget(self.select_task_btn)
        current_layout.addLayout(header_row)

        self.current_task_title_label = QLabel("No Task Selected")
        self.current_task_title_label.setObjectName("CurrentTaskTitle")
        self.current_task_title_label.setWordWrap(True)
        current_layout.addWidget(self.current_task_title_label)

        self.current_task_meta = QLabel("Session Type: -")
        self.current_task_meta.setObjectName("CurrentTaskMeta")
        self.current_task_meta.setWordWrap(True)
        self.labels_sub.append(self.current_task_meta)
        current_layout.addWidget(self.current_task_meta)

        progress_row = QHBoxLayout()
        self.session_progress_title = QLabel("Session Progress")
        self.session_progress_title.setObjectName("SessionProgressTitle")
        self.session_progress_value = QLabel("0%")
        self.session_progress_value.setObjectName("SessionProgressValue")
        progress_row.addWidget(self.session_progress_title)
        progress_row.addStretch()
        progress_row.addWidget(self.session_progress_value)
        current_layout.addLayout(progress_row)

        self.session_progress_bar = QProgressBar()
        self.session_progress_bar.setRange(0, 100)
        self.session_progress_bar.setValue(0)
        self.session_progress_bar.setTextVisible(False)
        self.session_progress_bar.setFixedHeight(8)
        current_layout.addWidget(self.session_progress_bar)

        self.focus_mode_card = QFrame()
        self.focus_mode_card.setObjectName("FocusModeCard")
        self.focus_mode_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        focus_layout = QVBoxLayout(self.focus_mode_card)
        focus_layout.setContentsMargins(12, 12, 12, 12)
        focus_layout.setSpacing(6)

        focus_title_row = QHBoxLayout()
        self.focus_mode_icon = QLabel("-")
        self.focus_mode_icon.setObjectName("FocusModeIcon")
        self.focus_mode_icon.setFixedSize(18, 18)
        self.focus_mode_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.focus_mode_title = QLabel("Focus Mode Active")
        self.focus_mode_title.setObjectName("FocusModeTitle")
        focus_title_row.addWidget(self.focus_mode_icon)
        focus_title_row.addSpacing(6)
        focus_title_row.addWidget(self.focus_mode_title)
        focus_title_row.addStretch()
        focus_layout.addLayout(focus_title_row)

        self.focus_mode_desc = QLabel("Notifications are currently blocked")
        self.focus_mode_desc.setObjectName("FocusModeDesc")
        self.focus_mode_desc.setWordWrap(True)
        focus_layout.addWidget(self.focus_mode_desc)

        self.focus_mode_toggle = Toggle(width=44)
        self.focus_mode_toggle.setObjectName("FocusModeToggle")
        self.focus_mode_toggle.stateChanged.connect(self.on_focus_mode_toggled)
        focus_layout.addWidget(self.focus_mode_toggle, alignment=Qt.AlignmentFlag.AlignLeft)

        self.focus_assist_btn = QPushButton("Open Settings")
        self.focus_assist_btn.setObjectName("FocusAssistBtn")
        self.focus_assist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.focus_assist_btn.clicked.connect(self.open_focus_assist_settings)
        focus_layout.addWidget(self.focus_assist_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        if os.name != "nt":
            self.focus_assist_btn.hide()

        current_layout.addWidget(self.focus_mode_card)
        
        self.left_vbox.addWidget(self.header_title)
        self.left_vbox.addWidget(self.header_sub)
        self.left_vbox.addWidget(self.current_task_card)
        self.left_vbox.addSpacing(20)

        self.badge = QLabel("FOCUS TIME")
        self.badge.setObjectName("PomodoroBadge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(130, 32)
        self.left_vbox.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignCenter)

        self.timer_label = QLabel("25:00")
        self.timer_label.setMinimumSize(220, 220)
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_vbox.addWidget(self.timer_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Break tips (shown only during breaks)
        self.tips_frame = QFrame()
        self.tips_frame.setObjectName("PomodoroTips")
        tips_layout = QVBoxLayout(self.tips_frame)
        tips_layout.setContentsMargins(16, 14, 16, 14)
        tips_layout.setSpacing(10)

        self.tips_title = QLabel("REFRESHMENT TIPS")
        self.tips_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tips_layout.addWidget(self.tips_title)

        tips_row1 = QHBoxLayout()
        tips_row1.setSpacing(8)
        self.btn_hydrate = QToolButton()
        self.btn_hydrate.setText("Hydrate")
        self.btn_stretch = QToolButton()
        self.btn_stretch.setText("Stretch")
        self.btn_step = QToolButton()
        self.btn_step.setText("Step Away")
        for b in (self.btn_hydrate, self.btn_stretch, self.btn_step):
            b.setFixedSize(100, 66)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(22, 22))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            tips_row1.addWidget(b)
        tips_layout.addLayout(tips_row1)

        tips_row2 = QHBoxLayout()
        tips_row2.setSpacing(10)
        self.btn_skip_break = QPushButton("Skip Break")
        self.btn_add_two = QPushButton("+2 Minutes")
        for b in (self.btn_skip_break, self.btn_add_two):
            b.setFixedHeight(34)
            b.setMinimumWidth(140)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            tips_row2.addWidget(b)
        tips_layout.addLayout(tips_row2)

        self.btn_skip_break.clicked.connect(self.skip_break)
        self.btn_add_two.clicked.connect(lambda: self.add_break_minutes(2))

        self.tips_frame.setVisible(False)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        self.btn_start = QPushButton("Start Session")
        self.btn_start.setFixedSize(160, 50)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.toggle_timer)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedSize(110, 50)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_timer)
        self.btn_stop.setVisible(False)
        
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setFixedSize(110, 50)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_timer)
        self.btn_reset_ref = self.btn_reset
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        self.left_vbox.addLayout(btn_layout)
        self._apply_control_icons()
        self.left_vbox.addWidget(self.tips_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self.left_vbox.addSpacing(30)
        self.separator = QFrame()
        self.separator.setFixedHeight(2)
        self.left_vbox.addWidget(self.separator)
        
        self.next_label = QLabel("Next Up: Short Break (5 min)")
        self.next_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labels_sub.append(self.next_label)
        self.left_vbox.addWidget(self.next_label)

        self.sessions_count = QLabel("0")
        self.sessions_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sessions_count.setStyleSheet("font-weight: 900; font-size: 32px;")
        self.labels_main.append(self.sessions_count)
        self.left_vbox.addWidget(self.sessions_count)
        self.left_vbox.addStretch()

        # === DROITE ===
        self.settings_card = self.create_card("Settings")
        self.focus_input = self.add_styled_setting(self.settings_card, "Focus Duration", 25)
        self.short_input = self.add_styled_setting(self.settings_card, "Short Break", 5)
        self.long_input = self.add_styled_setting(self.settings_card, "Long Break", 15)
        self.interval_input = self.add_styled_setting(self.settings_card, "Intervals", 4)
        self.interval_input.valueChanged.connect(self._on_interval_changed)

        self.plan_card = self.create_card("Custom Plan")
        self.plan_scroll = QScrollArea()
        self.plan_scroll.setWidgetResizable(True)
        self.plan_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.plan_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plan_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.plan_scroll.setFixedHeight(380)
        self.plan_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.plan_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.plan_container = QWidget()
        self.plan_container.setObjectName("PlanContainer")
        self.plan_container.setStyleSheet("background: transparent;")
        self.plan_layout = QVBoxLayout(self.plan_container)
        self.plan_layout.setContentsMargins(12, 12, 12, 12)
        self.plan_layout.setSpacing(12)
        self.plan_scroll.setWidget(self.plan_container)
        self.plan_card.layout().addWidget(self.plan_scroll)

        self.cycle_card = self.create_card("Current Cycle")
        self.total_stat = self.add_stat_line(self.cycle_card, "Total Time", "130m", True)

        self.settings_stack = QWidget()
        settings_layout = QVBoxLayout(self.settings_stack)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(25)
        settings_layout.addWidget(self.settings_card)
        settings_layout.addWidget(self.plan_card)
        settings_layout.addWidget(self.cycle_card)

        insert_idx = self.left_vbox.indexOf(self.tips_frame) + 1
        self.left_vbox.insertWidget(insert_idx, self.settings_stack)

        self.main_layout.addWidget(self.left_container, stretch=1)

    # --- THEME + SETTINGS ---
    def load_settings_data(self):
        """Cherche settings.json partout où il pourrait se cacher."""
        theme = "Light"
        auto_start = False
        enable_notifications = True
        sound_effects = True
        self._settings_path = None
        
        # 1. Chemin absolu du dossier où se trouve ce fichier (pages/)
        dir_pages = os.path.dirname(os.path.abspath(__file__))
        # 2. Chemin du dossier parent (racine du projet)
        dir_root = os.path.dirname(dir_pages)
        
        # Liste des endroits où chercher
        paths_to_check = [
            "settings.json",                          # Dossier d'exécution actuel
            os.path.join(dir_root, "settings.json"),  # Racine du projet (Prodsmart/)
            os.path.join(dir_pages, "settings.json")  # Dossier pages/
        ]

        found = False
        for path in paths_to_check:
            if os.path.exists(path):
                print(f"✅ SUCCÈS : settings.json trouvé ici : {path}")
                self._settings_path = path
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                        theme = data.get("theme", "Light")
                        auto_start = data.get("auto_start_pomodoro", False)
                        enable_notifications = data.get("enable_notifications", True)
                        sound_effects = data.get("sound_effects", True)
                        found = True
                        break # On arrête de chercher
                except Exception as e:
                    print(f"❌ Erreur lecture fichier {path}: {e}")
            else:
                print(f"🔍 Pas de fichier ici : {path}")

        if not found:
            print("⚠️ AUCUN fichier settings.json trouvé. Le thème restera 'Light'.")
            print("👉 Avez-vous cliqué sur 'Save Changes' dans l'onglet Settings ?")

        return theme, auto_start, enable_notifications, sound_effects

    def apply_theme(self):
        self._prune_dead_widgets()
        raw_theme, auto_start, enable_notifications, sound_effects = self.load_settings_data()
        self.auto_start = bool(auto_start)
        self.enable_notifications = bool(enable_notifications)
        self.sound_effects = bool(sound_effects)
        
        is_dark = str(raw_theme).strip().lower() == "dark"
        self._is_dark = is_dark
        
        print(f"🎨 Application du thème : {'DARK' if is_dark else 'LIGHT'}")

        base = get_theme("Dark" if is_dark else "Light")
        c = {
            "bg": base["bg"],
            "card": base["card"],
            "border": base["border"],
            "text_main": base["text"],
            "text_sub": base["sub"],
            "input_bg": base["input_bg"],
            "badge_bg": base["accent_soft"],
            "badge_text": base["accent"],
            "accent": base["accent"],
            "accent2": base["accent2"],
            "good": base["good"],
            "bad": base["bad"],
            "deep": base["deep"],
            "card_alt": base["card_alt"],
        }
        self._theme_colors = c

        self.setStyleSheet(f"background-color: {c['bg']}; font-family: '{FONT_FAMILY}', 'Segoe UI';")

        for card in self.cards:
            card.setStyleSheet(f"background-color: {c['card']}; border-radius: 30px; border: 1px solid {c['border']};")

        for lbl in self.labels_main:
            lbl.setStyleSheet(lbl.styleSheet() + f" color: {c['text_main']}; border: none; background: transparent;")

        for lbl in self.labels_sub:
            lbl.setStyleSheet(lbl.styleSheet() + f" color: {c['text_sub']}; border: none; background: transparent;")

        for sb in self.spinboxes:
            try:
                is_plan = sb.property("planSpin") is True
            except RuntimeError:
                continue
            if is_plan:
                sb.setStyleSheet(
                    f"QSpinBox {{ background: transparent; color: {c['text_main']}; border: none; "
                    f"padding: 0px 0px 0px 8px; font-weight: 700; font-size: 13px; }} "
                    f"QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}"
                )
            else:
                sb.setStyleSheet(
                    f"QSpinBox {{ background: transparent; color: {c['text_main']}; border: none; "
                    f"padding: 0px 0px 0px 10px; font-weight: bold; font-size: 15px; }} "
                    f"QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}"
                )

        for ib in self.inputs_bg:
            if ib.property("planInput") is True:
                ib.setStyleSheet(
                    f"background-color: {c['input_bg']}; border: 1px solid {c['border']}; border-radius: 10px;"
                )
            else:
                ib.setStyleSheet(
                    f"background-color: {c['input_bg']}; border: 1px solid {c['border']}; border-radius: 10px;"
                )

        if self.plan_badges:
            for badge in self.plan_badges:
                self._style_plan_badge(badge)

        if self.plan_label_chips:
            for chip in self.plan_label_chips:
                self._style_plan_chip(chip)

        if self.plan_rows:
            if self._is_dark:
                row_bg = c["card_alt"]
                row_border = c["border"]
            else:
                row_bg = c["card"]
                row_border = c["border"]
            for row in self.plan_rows:
                row.setStyleSheet(
                    f"QFrame#PlanRow {{ background-color: {row_bg}; border: 1px solid {row_border}; border-radius: 16px; }}"
                )

        self.badge.setStyleSheet(f"background-color: {c['badge_bg']}; color: {c['badge_text']}; border-radius: 16px; font-weight: bold; font-size: 11px;")
        
        self.timer_label.setStyleSheet(f"font-size: 85px; font-weight: 900; color: {c['text_main']}; background-color: {c['bg']}; border: 12px solid {c['accent']}; border-radius: 160px;")
        
        self.btn_reset_ref.setStyleSheet(f"background-color: {c['input_bg']}; color: {c['text_main']}; border-radius: 12px; font-weight: bold; border: none;")
        if hasattr(self, "btn_stop"):
            stop = c.get("bad", "#ef4444")
            stop_hover = c.get("input_bg", "#1f2937")
            self.btn_stop.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {stop}; border: 1px solid {stop}; "
                f"border-radius: 12px; font-weight: bold; }} "
                f"QPushButton:hover {{ background-color: {stop_hover}; }}"
            )
        
        sep_style = f"background-color: {c['border']}; border: none;"
        self.separator.setStyleSheet(sep_style)
        self._update_phase_badge()
        self._update_next_label()
        self._style_break_tips()
        self._style_current_task_card()
        self._sync_focus_mode_toggle()
        self._update_session_progress()
        self._apply_responsive_sizes()
        self._apply_control_icons()

    def _apply_control_icons(self):
        style = QApplication.style() if QApplication.instance() else None
        if style is None:
            return
        self._icon_play = style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self._icon_pause = style.standardIcon(QStyle.StandardPixmap.SP_MediaPause)
        self._icon_stop = style.standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self._icon_reset = style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)

        if hasattr(self, "btn_start"):
            self.btn_start.setIcon(self._icon_play)
            self.btn_start.setIconSize(QSize(16, 16))
        if hasattr(self, "btn_stop"):
            self.btn_stop.setIcon(self._icon_stop)
            self.btn_stop.setIconSize(QSize(16, 16))
        if hasattr(self, "btn_reset_ref"):
            self.btn_reset_ref.setIcon(self._icon_reset)
            self.btn_reset_ref.setIconSize(QSize(16, 16))
        self._set_start_button_icon(self.timer.isActive())

    def _set_start_button_icon(self, is_running):
        if not hasattr(self, "btn_start"):
            return
        if is_running:
            icon = getattr(self, "_icon_pause", None)
        else:
            icon = getattr(self, "_icon_play", None)
        if icon:
            self.btn_start.setIcon(icon)

    def _style_current_task_card(self):
        if not hasattr(self, "current_task_card"):
            return
        colors = self._theme_colors or {}
        card_bg = colors.get("card_alt", "#0f2238" if self._is_dark else "#ffffff")
        card_border = colors.get("border", "#25456B" if self._is_dark else "#BAD2E0")
        accent = colors.get("accent2", colors.get("accent", "#82AFF2"))
        text_main = colors.get("text_main", "#e2e8f0" if self._is_dark else "#113356")
        text_sub = colors.get("text_sub", "#94a3b8" if self._is_dark else "#47617C")
        progress_bg = colors.get("border", "#25456B" if self._is_dark else "#BAD2E0")
        progress_chunk = colors.get("accent", "#82AFF2" if self._is_dark else "#3078CD")
        focus_bg = colors.get("card", "#0f2238" if self._is_dark else "#ffffff")
        focus_border = colors.get("border", "#25456B" if self._is_dark else "#BAD2E0")
        toggle_off = colors.get("border", "#25456B" if self._is_dark else "#BAD2E0")
        toggle_on = colors.get("accent", "#82AFF2" if self._is_dark else "#3078CD")
        toggle_thumb = colors.get("text_main", "#e2e8f0" if self._is_dark else "#ffffff")

        self._current_task_border_color = card_border
        self._current_task_style_base = (
            "QFrame#CurrentTaskCard { "
            f"background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 16px; }} "
            "QFrame#CurrentTaskCard QLabel { background-color: transparent; border: none; } "
            "QFrame#CurrentTaskCard[error=\"true\"] { border: 1px solid #ef4444; }"
        )
        self.current_task_card.setStyleSheet(self._current_task_style_base)
        self.current_task_header.setStyleSheet(
            f"color: {accent}; font-size: 11px; font-weight: 700; background: transparent; border: none;"
        )
        self.current_task_title_label.setStyleSheet(
            f"color: {text_main}; font-size: 20px; font-weight: 800; background: transparent; border: none;"
        )
        self.session_progress_title.setStyleSheet(
            f"color: {text_sub}; font-size: 12px; font-weight: 600; background: transparent; border: none;"
        )
        self.session_progress_value.setStyleSheet(
            f"color: {accent}; font-size: 12px; font-weight: 700; background: transparent; border: none;"
        )
        self.session_progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {progress_bg}; border: none; border-radius: 4px; }}"
            f"QProgressBar::chunk {{ background-color: {progress_chunk}; border-radius: 4px; }}"
        )

        if hasattr(self, "select_task_btn"):
            self.select_task_btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {accent}; border: 1px solid {card_border}; "
                f"border-radius: 10px; padding: 4px 8px; font-size: 10px; font-weight: 700; }} "
                f"QPushButton:hover {{ border-color: {accent}; }}"
            )
        if hasattr(self, "focus_assist_btn"):
            self.focus_assist_btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {accent}; border: 1px solid {focus_border}; "
                f"border-radius: 10px; padding: 4px 8px; font-size: 10px; font-weight: 700; }} "
                f"QPushButton:hover {{ border-color: {accent}; }}"
            )
            self.focus_assist_btn.setIcon(self._make_external_link_icon(QColor(accent)))
            self.focus_assist_btn.setIconSize(QSize(12, 12))

        self.focus_mode_card.setStyleSheet(
            "QFrame#FocusModeCard { "
            f"background-color: {focus_bg}; border: 1px solid {focus_border}; border-radius: 12px; }} "
            "QFrame#FocusModeCard QLabel { background-color: transparent; border: none; }"
        )
        self.focus_mode_icon.setStyleSheet(
            f"background-color: {accent}; color: {card_bg}; border-radius: 9px; font-weight: 900; font-size: 12px;"
        )
        self.focus_mode_title.setStyleSheet(
            f"color: {text_main}; font-size: 12px; font-weight: 700; background: transparent; border: none;"
        )
        self.focus_mode_desc.setStyleSheet(
            f"color: {text_sub}; font-size: 11px; background: transparent; border: none;"
        )
        if hasattr(self, "focus_mode_toggle"):
            self.focus_mode_toggle._bg_color = toggle_off
            self.focus_mode_toggle._active_color = toggle_on
            self.focus_mode_toggle._circle_color = toggle_thumb
            self.focus_mode_toggle.update()

    def _sync_focus_mode_toggle(self):
        if not hasattr(self, "focus_mode_toggle"):
            return
        focus_mode_on = not self.enable_notifications
        self._suppress_focus_mode_save = True
        self.focus_mode_toggle.setChecked(focus_mode_on)
        self._suppress_focus_mode_save = False
        self._update_focus_mode_text(focus_mode_on)

    def _update_focus_mode_text(self, focus_mode_on):
        if focus_mode_on:
            self.focus_mode_title.setText("Focus Mode Active")
            self.focus_mode_desc.setText("Notifications and sounds are disabled")
        else:
            self.focus_mode_title.setText("Focus Mode Off")
            self.focus_mode_desc.setText("Notifications and sounds are enabled")

    def on_focus_mode_toggled(self, state):
        if self._suppress_focus_mode_save:
            return
        focus_mode_on = bool(state)
        if focus_mode_on:
            if self._pre_focus_notifications is None:
                self._pre_focus_notifications = self.enable_notifications
            if self._pre_focus_sound is None:
                self._pre_focus_sound = self.sound_effects
            self.enable_notifications = False
            self.sound_effects = False
        else:
            self.enable_notifications = True if self._pre_focus_notifications is None else self._pre_focus_notifications
            self.sound_effects = True if self._pre_focus_sound is None else self._pre_focus_sound
            self._pre_focus_notifications = None
            self._pre_focus_sound = None
        self._update_focus_mode_text(focus_mode_on)
        self._save_settings_value("enable_notifications", self.enable_notifications)
        self._save_settings_value("sound_effects", self.sound_effects)
        if focus_mode_on:
            self._open_focus_assist_if_possible(auto=True)

    def open_focus_assist_settings(self):
        self._open_focus_assist_if_possible(auto=False)

    def _open_focus_assist_if_possible(self, auto=False):
        opened = False
        if os.name == "nt":
            opened = self._open_windows_uri("ms-settings:")
        if not opened and not auto:
            QMessageBox.information(self, "Settings", "Unable to open Windows Settings.")

    def _open_windows_uri(self, uri):
        try:
            os.startfile(uri)
            return True
        except Exception:
            pass
        try:
            subprocess.Popen(["explorer.exe", uri], shell=False)
            return True
        except Exception:
            pass
        try:
            subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
            return True
        except Exception:
            pass
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", f"Start-Process '{uri}'"],
                shell=False
            )
            return True
        except Exception:
            pass
        try:
            return QDesktopServices.openUrl(QUrl(uri))
        except Exception:
            return False

    def _make_external_link_icon(self, color):
        size = 12
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # square
        painter.drawRect(1, 3, 8, 8)
        # arrow
        painter.drawLine(6, 1, 11, 1)
        painter.drawLine(11, 1, 11, 6)
        painter.drawLine(11, 1, 6, 6)
        painter.end()
        return QIcon(pix)

    def _save_settings_value(self, key, value):
        path = self._settings_path
        if not path or not os.path.exists(path):
            dir_pages = os.path.dirname(os.path.abspath(__file__))
            dir_root = os.path.dirname(dir_pages)
            candidates = [
                os.path.join(dir_root, "settings.json"),
                "settings.json",
                os.path.join(dir_pages, "settings.json"),
            ]
            for candidate in candidates:
                if os.path.exists(candidate):
                    path = candidate
                    self._settings_path = candidate
                    break
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data[key] = value
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            return

    # --- HELPERS ---
    def create_card(self, title):
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.cards.append(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 20, 25, 20)
        t = QLabel(title)
        t.setStyleSheet("font-size: 18px; font-weight: 800;")
        self.labels_main.append(t)
        layout.addWidget(t)
        return card

    def add_styled_setting(self, card, label_text, default_val):
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.labels_sub.append(lbl)
        
        container = QFrame()
        container.setFixedHeight(45)
        self.inputs_bg.append(container)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)

        spin = NoWheelSpinBox()
        spin.setRange(1, 120); spin.setValue(default_val)
        self.spinboxes.append(spin)

        btn_col = QFrame()
        btn_col.setFixedWidth(40)
        v_layout = QVBoxLayout(btn_col)
        v_layout.setContentsMargins(0, 0, 0, 0); v_layout.setSpacing(0)

        btn_up = QPushButton("▲"); btn_down = QPushButton("▼")
        btn_style = "QPushButton { background-color: transparent; border: none; color: #47617C; font-weight: bold; } QPushButton:hover { color: #3078CD; }"
        btn_up.setStyleSheet(btn_style); btn_down.setStyleSheet(btn_style)
        btn_up.setCursor(Qt.CursorShape.PointingHandCursor); btn_down.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_up.clicked.connect(lambda: spin.setValue(spin.value() + 1))
        btn_down.clicked.connect(lambda: spin.setValue(spin.value() - 1))

        v_layout.addWidget(btn_up); v_layout.addWidget(btn_down)
        layout.addWidget(spin); layout.addWidget(btn_col)

        spin.valueChanged.connect(self.sync_settings)
        card.layout().addWidget(lbl); card.layout().addWidget(container)
        return spin

    def _add_plan_setting(self, label_text, default_val, max_val=180):
        return None

    def _create_compact_spin(self, default_val, max_val=180):
        container = QFrame()
        container.setFixedHeight(36)
        container.setProperty("planInput", True)
        self.inputs_bg.append(container)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        spin = NoWheelSpinBox()
        spin.setRange(1, max_val)
        spin.setValue(default_val)
        spin.setFixedWidth(92)
        spin.setFixedHeight(30)
        spin.setProperty("planSpin", True)
        self.spinboxes.append(spin)

        btn_col = QFrame()
        btn_col.setFixedWidth(22)
        v_layout = QVBoxLayout(btn_col)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)

        btn_up = QPushButton("▲")
        btn_down = QPushButton("▼")
        btn_style = "QPushButton { background-color: transparent; border: none; color: #47617C; font-weight: bold; } QPushButton:hover { color: #3078CD; }"
        btn_up.setStyleSheet(btn_style)
        btn_down.setStyleSheet(btn_style)
        btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_down.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_up.clicked.connect(lambda: spin.setValue(spin.value() + 1))
        btn_down.clicked.connect(lambda: spin.setValue(spin.value() - 1))

        v_layout.addWidget(btn_up)
        v_layout.addWidget(btn_down)
        layout.addWidget(spin)
        layout.addWidget(btn_col)
        spin.valueChanged.connect(self._on_plan_changed)
        return container, spin

    def _style_plan_badge(self, badge):
        if badge is None:
            return
        colors = self._theme_colors or {}
        badge_bg = colors.get("accent_soft", "#e0f2fe")
        badge_border = colors.get("border", "#BAD2E0")
        badge_text = colors.get("accent", "#3078CD")
        try:
            badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            badge.setStyleSheet(
                f"background-color: {badge_bg}; color: {badge_text}; border: 1px solid {badge_border}; "
                f"border-radius: 12px; padding: 8px 10px; font-weight: 800; font-size: 11px;"
            )
        except RuntimeError:
            return

    def _style_plan_chip(self, chip):
        if chip is None:
            return
        colors = self._theme_colors or {}
        focus_bg = colors.get("accent_soft", "#e0f2fe")
        focus_border = colors.get("border", "#BAD2E0")
        focus_text = colors.get("accent", "#3078CD")
        break_bg = colors.get("card_alt", "#EEF5FA")
        break_border = colors.get("border", "#BAD2E0")
        break_text = colors.get("accent2", "#82AFF2")
        long_bg = colors.get("deep", "#25456B")
        long_border = colors.get("border", "#BAD2E0")
        long_text = colors.get("text_main", "#F8F6F2")
        name = chip.objectName()
        if name == "PlanChipFocus":
            bg, border, text = focus_bg, focus_border, focus_text
        elif name == "PlanChipLong":
            bg, border, text = long_bg, long_border, long_text
        else:
            bg, border, text = break_bg, break_border, break_text
        try:
            chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            chip.setStyleSheet(
                f"background-color: {bg}; color: {text}; border: 1px solid {border}; "
                f"border-radius: 10px; padding: 4px 10px; font-weight: 800; font-size: 10px;"
            )
        except RuntimeError:
            return

    def _add_plan_row(self, idx, focus_default, break_default, break_label):
        row = QFrame()
        row.setMinimumHeight(140)
        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row.setObjectName("PlanRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.plan_rows.append(row)

        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 6, 10, 14)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        badge = QLabel(f"Interval {idx}")
        badge.setObjectName("PlanBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(102)
        badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.plan_badges.append(badge)
        self._style_plan_badge(badge)

        header = QHBoxLayout()
        header.addStretch()
        header.addWidget(badge)
        header.addStretch()
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(18)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)

        focus_chip = QLabel("Focus")
        focus_chip.setObjectName("PlanChipFocus")
        focus_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        focus_chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.plan_label_chips.append(focus_chip)
        self._style_plan_chip(focus_chip)
        focus_container, focus_spin = self._create_compact_spin(focus_default, max_val=180)
        grid.addWidget(focus_chip, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(focus_container, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        break_chip = QLabel(break_label)
        chip_name = "PlanChipLong" if break_label == "Long Break" else "PlanChipBreak"
        break_chip.setObjectName(chip_name)
        break_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        break_chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.plan_label_chips.append(break_chip)
        self._style_plan_chip(break_chip)
        break_container, break_spin = self._create_compact_spin(break_default, max_val=90)
        grid.addWidget(break_chip, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(break_container, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(grid)

        layout.addStretch()

        self.plan_layout.addWidget(row)
        self.plan_row_widgets.append(row)
        return focus_spin, break_spin

    def add_stat_line(self, card, label_text, val_text, is_bold=False):
        row = QHBoxLayout()
        l = QLabel(label_text); v = QLabel(val_text)
        if is_bold:
            self.labels_main.append(l); self.labels_main.append(v)
            l.setStyleSheet("font-weight: 800;"); v.setStyleSheet("font-weight: 800;")
        else:
            self.labels_sub.append(l); self.labels_sub.append(v)
        row.addWidget(l); row.addStretch(); row.addWidget(v)
        card.layout().addLayout(row)
        return v

    def _on_interval_changed(self, *_):
        self._rebuild_plan_inputs()
        self._on_plan_changed()

    def _rebuild_plan_inputs(self):
        intervals = max(1, int(self.interval_input.value()))
        if self._last_interval_value == intervals and self.plan_focus_spins and self.plan_break_spins:
            return
        self._last_interval_value = intervals

        while self.plan_layout.count():
            item = self.plan_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.plan_row_widgets = []
        self.plan_focus_spins = []
        self.plan_break_spins = []
        self.plan_badges = []
        self.plan_rows = []
        self.plan_label_chips = []
        alive_spinboxes = []
        for sb in self.spinboxes:
            try:
                if sb is not None and sb.parent() is not None:
                    alive_spinboxes.append(sb)
            except RuntimeError:
                continue
        self.spinboxes = alive_spinboxes
        alive_inputs = []
        for ib in self.inputs_bg:
            try:
                if ib is not None and ib.parent() is not None:
                    alive_inputs.append(ib)
            except RuntimeError:
                continue
        self.inputs_bg = alive_inputs

        focus_default = int(self.focus_input.value())
        short_default = int(self.short_input.value())
        long_default = int(self.long_input.value())

        for idx in range(1, intervals + 1):
            break_label = "Long Break" if idx == intervals else f"Break {idx}"
            break_default = long_default if idx == intervals else short_default
            focus_spin, break_spin = self._add_plan_row(idx, focus_default, break_default, break_label)
            self.plan_focus_spins.append(focus_spin)
            self.plan_break_spins.append(break_spin)

        self._rebuild_plan_phases()
        self._sync_plan_stats()
        if hasattr(self, "plan_scroll"):
            try:
                self._update_plan_scroll_height(intervals)
                self.plan_scroll.verticalScrollBar().setValue(0)
            except Exception:
                pass
        self._apply_plan_styles()
        if hasattr(self, "plan_container"):
            try:
                self.plan_container.adjustSize()
                self.plan_container.updateGeometry()
            except Exception:
                pass

    def _apply_plan_styles(self):
        c = self._theme_colors or {}
        if c:
            for sb in self.spinboxes:
                if sb is None:
                    continue
                if sb.parent() is None:
                    continue
                try:
                    if sb.property("planSpin") is True:
                        sb.setStyleSheet(
                            f"QSpinBox {{ background: transparent; color: {c['text_main']}; border: none; "
                            f"padding: 0px 0px 0px 8px; font-weight: 700; font-size: 13px; }} "
                            f"QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}"
                        )
                    else:
                        sb.setStyleSheet(
                            f"QSpinBox {{ background: transparent; color: {c['text_main']}; border: none; padding: 0px 0px 0px 10px; "
                            f"font-weight: bold; font-size: 15px; }} QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}"
                        )
                except RuntimeError:
                    continue
            for ib in self.inputs_bg:
                if ib is None:
                    continue
                if ib.parent() is None:
                    continue
                try:
                    ib.setStyleSheet(f"background-color: {c['input_bg']}; border: 1px solid {c['border']}; border-radius: 10px;")
                except RuntimeError:
                    continue

        if self.plan_badges:
            for badge in self.plan_badges:
                self._style_plan_badge(badge)

        if self.plan_label_chips:
            for chip in self.plan_label_chips:
                self._style_plan_chip(chip)

        if self.plan_rows:
            if self._is_dark:
                row_bg = "#161d24"
                row_border = "#2b3440"
            else:
                row_bg = "#f8fafc"
                row_border = "#e2e8f0"
            for row in self.plan_rows:
                try:
                    row.setStyleSheet(
                        f"QFrame#PlanRow {{ background-color: {row_bg}; border: 1px solid {row_border}; border-radius: 16px; }}"
                    )
                except RuntimeError:
                    continue

    def _update_plan_scroll_height(self, intervals):
        if not hasattr(self, "plan_scroll") or not hasattr(self, "plan_layout"):
            return
        row_height = 140
        spacing = self.plan_layout.spacing()
        margins = self.plan_layout.contentsMargins()
        content_height = (intervals * row_height) + max(0, intervals - 1) * spacing + margins.top() + margins.bottom()
        min_height = 180
        max_height = 380
        target_height = max(min_height, min(max_height, content_height))
        self.plan_scroll.setFixedHeight(int(target_height))

    def _rebuild_plan_phases(self):
        self.plan_phases = []
        intervals = max(1, int(self.interval_input.value()))
        for idx in range(intervals):
            focus_minutes = int(self.plan_focus_spins[idx].value()) if idx < len(self.plan_focus_spins) else int(self.focus_input.value())
            self.plan_phases.append({
                "phase": "focus",
                "minutes": focus_minutes
            })
            break_minutes = int(self.plan_break_spins[idx].value()) if idx < len(self.plan_break_spins) else int(self.short_input.value())
            phase_type = "long_break" if idx == intervals - 1 else "short_break"
            self.plan_phases.append({
                "phase": phase_type,
                "minutes": break_minutes
            })

    def _current_plan_phase(self):
        if not self.plan_phases:
            return None
        idx = max(0, min(self.plan_index, len(self.plan_phases) - 1))
        return self.plan_phases[idx]

    def _next_plan_phase(self):
        if not self.plan_phases:
            return None
        next_idx = (self.plan_index + 1) % len(self.plan_phases)
        return self.plan_phases[next_idx]

    def _on_plan_changed(self, *_):
        self._rebuild_plan_phases()
        self._sync_plan_stats()
        if not self.timer.isActive():
            if not self.plan_phases:
                return
            self.plan_index = max(0, min(self.plan_index, len(self.plan_phases) - 1))
            self.phase = self.plan_phases[self.plan_index]["phase"]
            minutes = int(self.plan_phases[self.plan_index]["minutes"])
            self.time_left = minutes * 60
            self.timer_label.setText(f"{minutes:02d}:00")
            self._update_next_label()
            self._update_session_progress()

    def _sync_plan_stats(self):
        if not self.plan_phases:
            return
        total_minutes = sum(int(item["minutes"]) for item in self.plan_phases)
        self.total_stat.setText(f"{total_minutes}m")

    def sync_settings(self):
        sender = self.sender()
        f, s, l, i = self.focus_input.value(), self.short_input.value(), self.long_input.value(), self.interval_input.value()

        if sender is self.focus_input and self.plan_focus_spins:
            for spin in self.plan_focus_spins:
                spin.blockSignals(True)
                spin.setValue(int(f))
                spin.blockSignals(False)
        elif sender is self.short_input and self.plan_break_spins:
            for spin in self.plan_break_spins[:-1]:
                spin.blockSignals(True)
                spin.setValue(int(s))
                spin.blockSignals(False)
        elif sender is self.long_input and self.plan_break_spins:
            self.plan_break_spins[-1].blockSignals(True)
            self.plan_break_spins[-1].setValue(int(l))
            self.plan_break_spins[-1].blockSignals(False)

        if self.plan_phases:
            self._on_plan_changed()
        else:
            self.total_stat.setText(f"{(f * i) + (s * (i-1)) + l}m")
            if not self.timer.isActive():
                minutes = self._phase_minutes(self.phase)
                self.time_left = minutes * 60
                self.timer_label.setText(f"{minutes:02d}:00")
                self._update_next_label()
                self._update_session_progress()

    def _update_session_progress(self):
        if not hasattr(self, "session_progress_bar"):
            return
        if self.plan_phases and self.phase == "focus":
            total_minutes = max(1, int(self._phase_minutes(self.phase)))
        else:
            total_minutes = max(1, int(self.focus_input.value()))
        total_seconds = total_minutes * 60
        if self.phase == "focus":
            elapsed = max(0, total_seconds - int(self.time_left))
            percent = int(round((elapsed / total_seconds) * 100))
        else:
            percent = 0
        percent = max(0, min(100, percent))
        self.session_progress_bar.setValue(percent)
        if hasattr(self, "session_progress_value"):
            self.session_progress_value.setText(f"{percent}%")

    def toggle_timer(self):
        if self.timer.isActive():
            self.timer.stop()
            self._update_start_button(resume=True)
            if not self._should_disable_start():
                good = (self._theme_colors or {}).get("good", "#10b981")
                self.btn_start.setStyleSheet(f"background-color: {good}; color: white; border-radius: 12px; font-weight: bold; border: none;")
        else:
            if self._should_disable_start():
                self._show_task_required()
                return
            self._start_timer()

    def stop_timer(self):
        if self.phase != "focus":
            return
        if self.session_started_at is None:
            return
        self.timer.stop()
        self._log_session(status="stopped")
        self._set_phase("focus", reset_time=True, notify=False)

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            mins, secs = divmod(self.time_left, 60)
            self.timer_label.setText(f"{mins:02d}:{secs:02d}")
            self._update_session_progress()
        else:
            self.timer.stop()
            if self.plan_phases:
                current_minutes = int(self._phase_minutes(self.phase))
                if self.phase == "focus":
                    self._log_session(status="completed", duration_override=current_minutes)
                    self.sessions_completed += 1
                    self.sessions_count.setText(str(self.sessions_completed))

                self.plan_index += 1
                if self.plan_index >= len(self.plan_phases):
                    self.plan_index = 0
                    self.sessions_completed = 0
                    self.sessions_count.setText("0")

                next_phase = self.plan_phases[self.plan_index]["phase"]
                self._set_phase(next_phase, reset_time=True, notify=True)
                self._update_session_progress()
            else:
                if self.phase == "focus":
                    self._log_session(status="completed", duration_override=self.focus_input.value())
                    self.sessions_completed += 1
                    self.sessions_count.setText(str(self.sessions_completed))
                    next_phase = self._next_break_phase(pending_focus=False)
                else:
                    if self.phase == "long_break":
                        self.sessions_completed = 0
                        self.sessions_count.setText("0")
                    next_phase = "focus"

                self._set_phase(next_phase, reset_time=True, notify=True)
                self._update_session_progress()

            if self.auto_start:
                self._start_timer()
            else:
                self._update_start_button(resume=False)
                if not self._should_disable_start():
                    accent = (self._theme_colors or {}).get("accent", "#3078CD")
                    self.btn_start.setStyleSheet(f"background-color: {accent}; color: white; border-radius: 12px; font-weight: bold; border: none;")

    def reset_timer(self):
        if self.session_started_at is not None and self.phase == "focus":
            self._log_session(status="stopped")
        self.timer.stop()
        self.sessions_completed = 0
        self.sessions_count.setText("0")
        self.plan_index = 0
        # Reset settings to defaults
        for spin in (self.focus_input, self.short_input, self.long_input, self.interval_input):
            try:
                spin.blockSignals(True)
            except Exception:
                pass
        self.focus_input.setValue(25)
        self.short_input.setValue(5)
        self.long_input.setValue(15)
        self.interval_input.setValue(4)
        for spin in (self.focus_input, self.short_input, self.long_input, self.interval_input):
            try:
                spin.blockSignals(False)
            except Exception:
                pass
        self._rebuild_plan_inputs()
        self.current_task_id = None
        self.current_task_title = None
        self.current_task_priority = None
        if hasattr(self, "current_task_title_label"):
            self.current_task_title_label.setText("No Task Selected")
        if hasattr(self, "current_task_meta"):
            self.current_task_meta.setText("Session Type: -")
        self._set_phase("focus", reset_time=True, notify=False)
        self._update_start_button(resume=False)
        if not self._should_disable_start():
            accent = (self._theme_colors or {}).get("accent", "#3078CD")
            self.btn_start.setStyleSheet(f"background-color: {accent}; color: white; border-radius: 12px; font-weight: bold; border: none;")

    def set_task(self, task_id, title, priority=None):
        self.current_task_id = task_id
        self.current_task_title = title
        self.current_task_priority = normalize_priority(priority)
        safe_title = title.strip() if title else "No Task Selected"
        if hasattr(self, "current_task_title_label"):
            self.current_task_title_label.setText(safe_title)
        if hasattr(self, "current_task_meta"):
            if self.current_task_priority:
                session_label = priority_session_label(self.current_task_priority)
                self.current_task_meta.setText(f"Session Type: {session_label}")
            else:
                self.current_task_meta.setText("Session Type: -")
        if not self.timer.isActive():
            self._update_start_button(resume=False)

    def _has_task_selected(self):
        return self.current_task_id is not None and bool(str(self.current_task_title or "").strip())

    def _should_disable_start(self):
        return self.phase == "focus" and not self._has_task_selected()

    def _show_task_required(self):
        self._flash_task_card()

    def _flash_task_card(self):
        if not hasattr(self, "current_task_card"):
            return
        self.current_task_card.setProperty("error", True)
        self.current_task_card.style().unpolish(self.current_task_card)
        self.current_task_card.style().polish(self.current_task_card)
        self.current_task_card.update()
        QTimer.singleShot(900, self._clear_task_card_error)

    def _clear_task_card_error(self):
        if not hasattr(self, "current_task_card"):
            return
        self.current_task_card.setProperty("error", False)
        self.current_task_card.style().unpolish(self.current_task_card)
        self.current_task_card.style().polish(self.current_task_card)
        self.current_task_card.update()

    def _request_task_selection(self):
        self.select_task_requested.emit()

    def eventFilter(self, obj, event):
        if obj is self.left_container and event.type() == QEvent.Type.MouseButtonPress:
            if self._should_disable_start():
                try:
                    pos = event.position().toPoint()
                except Exception:
                    pos = event.pos()
                if self.btn_start.geometry().contains(pos):
                    self._flash_task_card()
                    return True
        return super().eventFilter(obj, event)

    def _phase_minutes(self, phase):
        if self.plan_phases:
            current = self._current_plan_phase()
            if current:
                return int(current["minutes"])
        if phase == "short_break":
            return self.short_input.value()
        if phase == "long_break":
            return self.long_input.value()
        return self.focus_input.value()

    def _next_break_phase(self, pending_focus=False):
        intervals = max(1, self.interval_input.value())
        count = self.sessions_completed + (1 if pending_focus else 0)
        if count % intervals == 0:
            return "long_break"
        return "short_break"

    def _phase_label(self, phase):
        if phase == "short_break":
            return "Short Break"
        if phase == "long_break":
            return "Long Break"
        return "Focus"

    def _update_next_label(self):
        if self.plan_phases:
            next_phase = self._next_plan_phase()
            if next_phase:
                mins = int(next_phase["minutes"])
                self.next_label.setText(f"Next Up: {self._phase_label(next_phase['phase'])} ({mins} min)")
                return
        if self.phase == "focus":
            next_phase = self._next_break_phase(pending_focus=True)
        else:
            next_phase = "focus"
        mins = self._phase_minutes(next_phase)
        self.next_label.setText(f"Next Up: {self._phase_label(next_phase)} ({mins} min)")

    def _update_phase_badge(self):
        colors = self._theme_colors or {}
        if self.phase == "focus":
            self.badge.setText("FOCUS TIME")
            bg = colors.get("badge_bg", colors.get("accent_soft", "#dbeafe"))
            fg = colors.get("badge_text", colors.get("accent", "#3078CD"))
        elif self.phase == "short_break":
            self.badge.setText("SHORT BREAK")
            bg = colors.get("card_alt", "#1b2f4d")
            fg = colors.get("accent2", "#82AFF2")
        else:
            self.badge.setText("LONG BREAK")
            bg = colors.get("deep", "#25456B")
            fg = colors.get("text_main", "#F8F6F2")
        self.badge.setStyleSheet(f"background-color: {bg}; color: {fg}; border-radius: 16px; font-weight: bold; font-size: 11px;")

    def _update_start_button(self, resume=False):
        colors = self._theme_colors or {}
        if self._should_disable_start():
            self.btn_start.setEnabled(False)
            self.btn_start.setText("Select Task")
            disabled_bg = colors.get("border", "#334155")
            disabled_text = colors.get("text_sub", "#94a3b8")
            self.btn_start.setStyleSheet(f"background-color: {disabled_bg}; color: {disabled_text}; border-radius: 12px; font-weight: bold; border: none;")
            self._set_start_button_icon(False)
            self._update_stop_button_visibility()
            return
        self.btn_start.setEnabled(True)
        phase_label = self._phase_label(self.phase)
        if resume:
            self.btn_start.setText(f"Resume {phase_label}")
        else:
            self.btn_start.setText(f"Start {phase_label}")
            accent = colors.get("accent", "#3078CD")
            self.btn_start.setStyleSheet(f"background-color: {accent}; color: white; border-radius: 12px; font-weight: bold; border: none;")
        self._set_start_button_icon(False)
        self._update_stop_button_visibility()

    def _update_stop_button_visibility(self):
        if not hasattr(self, "btn_stop"):
            return
        show = self.phase == "focus" and self.session_started_at is not None
        self.btn_stop.setVisible(bool(show))

    def _set_phase(self, phase, reset_time=True, notify=False):
        self.phase = phase
        if reset_time:
            minutes = self._phase_minutes(phase)
            self.time_left = minutes * 60
            self.timer_label.setText(f"{minutes:02d}:00")
        if phase != "focus":
            self.session_started_at = None
            self.session_task_id = None
            self.session_task_title = None
            self.session_task_priority = None
            self.session_duration_min = None
        self._update_phase_badge()
        self._update_next_label()
        self._update_start_button(resume=False)
        self._update_break_tips_visibility()
        self._update_session_progress()
        if notify:
            self._announce_phase_change(phase)

    def _start_timer(self):
        if self._should_disable_start():
            self._show_task_required()
            return
        self.timer.start(1000)
        self.btn_start.setText("Pause")
        self._set_start_button_icon(True)
        bad = (self._theme_colors or {}).get("bad", "#ef4444")
        self.btn_start.setStyleSheet(f"background-color: {bad}; color: white; border-radius: 12px; font-weight: bold; border: none;")
        if self.phase == "focus" and self.session_started_at is None:
            self.session_started_at = datetime.now()
            self.session_task_id = self.current_task_id
            self.session_task_title = self.current_task_title
            self.session_task_priority = self.current_task_priority
            self.session_duration_min = self._phase_minutes(self.phase)
        self._update_stop_button_visibility()

    def _ensure_tray(self):
        if self._tray is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ProdSmart.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setVisible(True)

    def _show_notification(self, title, message):
        if not self.enable_notifications:
            return
        self._ensure_tray()
        if self._tray:
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            print(f"[Pomodoro] {title}: {message}")

    def _play_sound(self):
        if not self.sound_effects:
            return
        QApplication.beep()

    def _announce_phase_change(self, phase):
        if self.last_notification_phase == phase:
            return
        self.last_notification_phase = phase
        label = self._phase_label(phase)
        mins = self._phase_minutes(phase)
        self._show_notification("Pomodoro", f"{label} started ({mins} min)")
        self._play_sound()

    def _update_break_tips_visibility(self):
        if hasattr(self, "tips_frame"):
            self.tips_frame.setVisible(self.phase in ("short_break", "long_break"))

    def _style_break_tips(self):
        if not hasattr(self, "tips_frame"):
            return
        colors = self._theme_colors or {}
        if self._is_dark:
            bg = colors.get("card_alt", "#112844")
            border = colors.get("border", "#25456B")
            title = colors.get("text_sub", "#BAD2E0")
            btn_bg = colors.get("card", "#0F2238")
            btn_border = colors.get("border", "#25456B")
            btn_text = colors.get("text_main", "#E6EEF5")
            btn_hover = colors.get("accent_soft", "#1B2F4D")
            action_bg = colors.get("accent_soft", "#1B2F4D")
            action_border = colors.get("accent2", "#3078CD")
            action_text = colors.get("accent", "#82AFF2")
        else:
            bg = colors.get("accent_soft", "#E6F0FA")
            border = colors.get("border", "#BAD2E0")
            title = colors.get("text_sub", "#47617C")
            btn_bg = colors.get("card", "#FFFFFF")
            btn_border = colors.get("border", "#BAD2E0")
            btn_text = colors.get("deep", "#25456B")
            btn_hover = colors.get("border", "#BAD2E0")
            action_bg = colors.get("accent_soft", "#E6F0FA")
            action_border = colors.get("accent", "#3078CD")
            action_text = colors.get("accent", "#3078CD")

        self.tips_frame.setStyleSheet(
            f"QFrame#PomodoroTips {{ background-color: {bg}; border: 1px solid {border}; border-radius: 16px; }}"
        )
        self.tips_title.setStyleSheet(f"color: {title}; font-size: 10px; font-weight: bold;")

        tip_style = (
            f"QToolButton {{ background-color: {btn_bg}; color: {btn_text}; border: 1px solid {btn_border}; "
            f"border-radius: 10px; padding: 6px 8px; font-size: 11px; font-weight: bold; }} "
            f"QToolButton:hover {{ background-color: {btn_hover}; }}"
        )
        for b in (self.btn_hydrate, self.btn_stretch, self.btn_step):
            b.setStyleSheet(tip_style)
        icon_color = colors.get("accent", "#3078CD")
        self._set_tip_icons(icon_color)

        action_style = (
            f"QPushButton {{ background-color: {action_bg}; color: {action_text}; border: 1px solid {action_border}; "
            f"border-radius: 10px; padding: 6px 10px; font-size: 11px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {btn_hover}; }}"
        )
        self.btn_skip_break.setStyleSheet(action_style)
        self.btn_add_two.setStyleSheet(action_style)

    def _apply_responsive_sizes(self):
        if not hasattr(self, "timer_label") or not hasattr(self, "left_container"):
            return
        width = self.left_container.width()
        if width <= 0:
            return
        try:
            margins = self.left_vbox.contentsMargins()
            width -= (margins.left() + margins.right())
        except Exception:
            pass

        size = int(width * 0.6)
        size = max(220, min(420, size))
        if self.timer_label.width() != size:
            self.timer_label.setFixedSize(size, size)

        if hasattr(self, "badge"):
            badge_w = max(110, min(200, int(size * 0.45)))
            self.badge.setFixedSize(badge_w, 32)

        btn_h = max(42, min(58, int(size * 0.16)))
        start_w = max(140, min(220, int(size * 0.5)))
        other_w = max(90, min(150, int(size * 0.35)))
        if hasattr(self, "btn_start"):
            self.btn_start.setFixedSize(start_w, btn_h)
        if hasattr(self, "btn_stop"):
            self.btn_stop.setFixedSize(other_w, btn_h)
        if hasattr(self, "btn_reset"):
            self.btn_reset.setFixedSize(other_w, btn_h)

        colors = self._theme_colors or {}
        accent = colors.get("accent", "#3078CD")
        text_main = colors.get("text_main", "#113356")
        bg = colors.get("bg", "#F8F6F2")
        border = max(8, int(round(size * 0.0375)))
        radius = size // 2
        font_size = max(56, min(110, int(size * 0.26)))
        self.timer_label.setStyleSheet(
            f"font-size: {font_size}px; font-weight: 900; color: {text_main}; "
            f"background-color: {bg}; border: {border}px solid {accent}; border-radius: {radius}px;"
        )

    def _set_tip_icons(self, color):
        icon_color = QColor(color)
        self.btn_hydrate.setIcon(self._make_tip_icon("hydrate", icon_color))
        self.btn_stretch.setIcon(self._make_tip_icon("stretch", icon_color))
        self.btn_step.setIcon(self._make_tip_icon("step", icon_color))

    def _make_tip_icon(self, kind, color):
        size = 24
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        if kind == "hydrate":
            path = QPainterPath()
            path.moveTo(12, 2)
            path.cubicTo(17, 7, 20, 11, 20, 15)
            path.cubicTo(20, 19, 16.5, 22, 12, 22)
            path.cubicTo(7.5, 22, 4, 19, 4, 15)
            path.cubicTo(4, 11, 7, 7, 12, 2)
            painter.drawPath(path)
        elif kind == "stretch":
            painter.drawEllipse(9, 2, 6, 6)  # head
            painter.drawLine(12, 8, 12, 16)  # body
            painter.drawLine(6, 9, 12, 12)   # left arm
            painter.drawLine(18, 9, 12, 12)  # right arm
            painter.drawLine(12, 16, 8, 22)  # left leg
            painter.drawLine(12, 16, 16, 22) # right leg
        else:  # "step"
            painter.drawRect(3, 4, 8, 16)    # door
            painter.drawLine(11, 12, 20, 12) # arrow
            painter.drawLine(17, 9, 20, 12)
            painter.drawLine(17, 15, 20, 12)

        painter.end()
        return QIcon(pix)

    def skip_break(self):
        if self.phase not in ("short_break", "long_break"):
            return
        self.timer.stop()
        if self.plan_phases:
            next_idx = (self.plan_index + 1) % len(self.plan_phases)
            self.plan_index = next_idx
            while self.plan_phases[self.plan_index]["phase"] != "focus":
                self.plan_index = (self.plan_index + 1) % len(self.plan_phases)
                if self.plan_index == 0:
                    self.sessions_completed = 0
                    self.sessions_count.setText("0")
            self._set_phase(self.plan_phases[self.plan_index]["phase"], reset_time=True, notify=True)
        else:
            self._set_phase("focus", reset_time=True, notify=True)
        if self.auto_start:
            self._start_timer()

    def add_break_minutes(self, minutes=2):
        if self.phase not in ("short_break", "long_break"):
            return
        self.time_left += int(minutes) * 60
        mins, secs = divmod(self.time_left, 60)
        self.timer_label.setText(f"{mins:02d}:{secs:02d}")

    def _elapsed_minutes(self):
        total_minutes = self.session_duration_min or self.focus_input.value()
        total_seconds = (total_minutes * 60) - self.time_left
        if total_seconds < 0:
            total_seconds = 0
        return max(1, int(round(total_seconds / 60.0))) if total_seconds > 0 else 0

    def _log_session(self, status="completed", duration_override=None):
        if self.session_started_at is None:
            self.session_started_at = datetime.now()
        ended_at = datetime.now()
        if duration_override is not None:
            duration_min = int(duration_override)
        else:
            duration_min = self._elapsed_minutes()
        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO pomodoro_sessions (task_id, task_title, task_priority, started_at, ended_at, duration_min, status) VALUES (?,?,?,?,?,?,?)",
                (
                    self.session_task_id,
                    self.session_task_title,
                    self.session_task_priority or self.current_task_priority,
                    self.session_started_at.strftime("%Y-%m-%d %H:%M:%S"),
                    ended_at.strftime("%Y-%m-%d %H:%M:%S"),
                    int(duration_min),
                    status,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            print("DB Error (Pomodoro):", exc)
        finally:
            self.session_started_at = None
            self.session_task_id = None
            self.session_task_title = None
            self.session_task_priority = None
            self.session_duration_min = None
        
