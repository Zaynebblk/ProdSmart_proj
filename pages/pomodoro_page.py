import json
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QSpinBox)
from PyQt6.QtCore import Qt, QTimer

class PomodoroPage(QWidget):
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
        
        self.setup_ui()

    def showEvent(self, event):
        """S'active quand on clique sur l'onglet"""
        self.apply_theme()
        super().showEvent(event)

    def setup_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(30)

        # === GAUCHE ===
        self.left_container = QFrame()
        self.cards.append(self.left_container)
        
        left_vbox = QVBoxLayout(self.left_container)
        left_vbox.setContentsMargins(50, 40, 50, 40)
        
        self.header_title = QLabel("Pomodoro Timer")
        self.header_title.setStyleSheet("font-size: 28px; font-weight: 800;")
        self.labels_main.append(self.header_title)
        
        self.header_sub = QLabel("Deep work made simple")
        self.header_sub.setStyleSheet("font-size: 15px;")
        self.labels_sub.append(self.header_sub)
        
        left_vbox.addWidget(self.header_title)
        left_vbox.addWidget(self.header_sub)
        left_vbox.addStretch()

        self.badge = QLabel("✨ FOCUS TIME")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(130, 32)
        left_vbox.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignCenter)

        self.timer_label = QLabel("25:00")
        self.timer_label.setFixedSize(320, 320)
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_vbox.addWidget(self.timer_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start Session")
        self.btn_start.setFixedSize(160, 50)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.toggle_timer)
        
        self.btn_reset = QPushButton("↺ Reset")
        self.btn_reset.setFixedSize(100, 50)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_timer)
        self.btn_reset_ref = self.btn_reset
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        left_vbox.addLayout(btn_layout)

        left_vbox.addSpacing(30)
        self.separator = QFrame()
        self.separator.setFixedHeight(2)
        left_vbox.addWidget(self.separator)
        
        self.next_label = QLabel("Next Up: Short Break (5 min)")
        self.next_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labels_sub.append(self.next_label)
        left_vbox.addWidget(self.next_label)

        self.sessions_count = QLabel("0")
        self.sessions_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sessions_count.setStyleSheet("font-weight: 900; font-size: 32px;")
        self.labels_main.append(self.sessions_count)
        left_vbox.addWidget(self.sessions_count)
        left_vbox.addStretch()

        # === DROITE ===
        right_panel = QVBoxLayout()
        right_panel.setSpacing(25)

        self.settings_card = self.create_card("⚙ Settings")
        self.focus_input = self.add_styled_setting(self.settings_card, "Focus Duration", 25)
        self.short_input = self.add_styled_setting(self.settings_card, "Short Break", 5)
        self.long_input = self.add_styled_setting(self.settings_card, "Long Break", 15)
        self.interval_input = self.add_styled_setting(self.settings_card, "Intervals", 4)

        self.cycle_card = self.create_card("📊 Current Cycle")
        self.focus_stat = self.add_stat_line(self.cycle_card, "Focus Phase", "25m")
        self.break_stat = self.add_stat_line(self.cycle_card, "Short Break", "5m")
        self.long_stat = self.add_stat_line(self.cycle_card, "Long Break", "15m") 
        
        self.card_separator = QFrame()
        self.card_separator.setFixedHeight(2)
        self.cycle_card.layout().addWidget(self.card_separator)
        
        self.total_stat = self.add_stat_line(self.cycle_card, "Total Time", "130m", True)

        right_panel.addWidget(self.settings_card)
        right_panel.addWidget(self.cycle_card)
        right_panel.addStretch()
        self.main_layout.addWidget(self.left_container, stretch=2)
        self.main_layout.addLayout(right_panel, stretch=1)

    # --- THEME MANAGEMENT INTELLIGENT ---
    def load_theme_data(self):
        """Cherche settings.json partout où il pourrait se cacher."""
        theme = "Light"
        
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
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                        theme = data.get("theme", "Light")
                        found = True
                        break # On arrête de chercher
                except Exception as e:
                    print(f"❌ Erreur lecture fichier {path}: {e}")
            else:
                print(f"🔍 Pas de fichier ici : {path}")

        if not found:
            print("⚠️ AUCUN fichier settings.json trouvé. Le thème restera 'Light'.")
            print("👉 Avez-vous cliqué sur 'Save Changes' dans l'onglet Settings ?")

        return theme

    def apply_theme(self):
        raw_theme = self.load_theme_data()
        # Nettoyage de la chaine de caractères (enlever espaces, minuscules)
        is_dark = str(raw_theme).strip().lower() == "dark"
        
        print(f"🎨 Application du thème : {'DARK' if is_dark else 'LIGHT'}")

        if is_dark:
            c = {
                "bg": "#121212", "card": "#1e1e1e", "border": "#333333",
                "text_main": "#ffffff", "text_sub": "#a0a0a0",
                "input_bg": "#2d2d2d", "badge_bg": "#172554", "badge_text": "#93c5fd"
            }
        else:
            c = {
                "bg": "#f8fafc", "card": "#ffffff", "border": "#edf2f7",
                "text_main": "#1e293b", "text_sub": "#64748b",
                "input_bg": "#f1f5f9", "badge_bg": "#eff6ff", "badge_text": "#2563eb"
            }

        self.setStyleSheet(f"background-color: {c['bg']};")

        for card in self.cards:
            card.setStyleSheet(f"background-color: {c['card']}; border-radius: 30px; border: 1px solid {c['border']};")

        for lbl in self.labels_main:
            lbl.setStyleSheet(lbl.styleSheet() + f" color: {c['text_main']}; border: none; background: transparent;")

        for lbl in self.labels_sub:
            lbl.setStyleSheet(lbl.styleSheet() + f" color: {c['text_sub']}; border: none; background: transparent;")

        for sb in self.spinboxes:
            sb.setStyleSheet(f"QSpinBox {{ background: transparent; color: {c['text_main']}; border: none; padding-left: 10px; font-weight: bold; font-size: 15px; }} QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}")

        for ib in self.inputs_bg:
            ib.setStyleSheet(f"background-color: {c['input_bg']}; border: 1px solid {c['border']}; border-radius: 10px;")

        self.badge.setStyleSheet(f"background-color: {c['badge_bg']}; color: {c['badge_text']}; border-radius: 16px; font-weight: bold; font-size: 11px;")
        
        self.timer_label.setStyleSheet(f"font-size: 85px; font-weight: 900; color: {c['text_main']}; background-color: {c['bg']}; border: 12px solid #3b82f6; border-radius: 160px;")
        
        self.btn_reset_ref.setStyleSheet(f"background-color: {c['input_bg']}; color: {c['text_main']}; border-radius: 12px; font-weight: 700; border: none;")
        
        sep_style = f"background-color: {c['border']}; border: none;"
        self.separator.setStyleSheet(sep_style)
        self.card_separator.setStyleSheet(sep_style)

    # --- HELPERS ---
    def create_card(self, title):
        card = QFrame()
        card.setFixedWidth(320)
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

        spin = QSpinBox()
        spin.setRange(1, 120); spin.setValue(default_val)
        self.spinboxes.append(spin)

        btn_col = QFrame()
        btn_col.setFixedWidth(40)
        v_layout = QVBoxLayout(btn_col)
        v_layout.setContentsMargins(0, 0, 0, 0); v_layout.setSpacing(0)

        btn_up = QPushButton("▲"); btn_down = QPushButton("▼")
        btn_style = "QPushButton { background: transparent; border: none; color: #64748b; font-weight: bold; } QPushButton:hover { color: #3b82f6; }"
        btn_up.setStyleSheet(btn_style); btn_down.setStyleSheet(btn_style)
        btn_up.setCursor(Qt.CursorShape.PointingHandCursor); btn_down.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_up.clicked.connect(lambda: spin.setValue(spin.value() + 1))
        btn_down.clicked.connect(lambda: spin.setValue(spin.value() - 1))

        v_layout.addWidget(btn_up); v_layout.addWidget(btn_down)
        layout.addWidget(spin); layout.addWidget(btn_col)

        spin.valueChanged.connect(self.sync_settings)
        card.layout().addWidget(lbl); card.layout().addWidget(container)
        return spin

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

    def sync_settings(self):
        f, s, l, i = self.focus_input.value(), self.short_input.value(), self.long_input.value(), self.interval_input.value()
        self.focus_stat.setText(f"{f}m"); self.break_stat.setText(f"{s}m"); self.long_stat.setText(f"{l}m") 
        self.total_stat.setText(f"{(f * i) + (s * (i-1)) + l}m")
        if not self.timer.isActive():
            self.time_left = f * 60
            self.timer_label.setText(f"{f:02d}:00")

    def toggle_timer(self):
        if self.timer.isActive():
            self.timer.stop()
            self.btn_start.setText("▶ Resume")
            self.btn_start.setStyleSheet("background-color: #10b981; color: white; border-radius: 12px; font-weight: 700; border: none;")
        else:
            self.timer.start(1000)
            self.btn_start.setText("⏸ Pause")
            self.btn_start.setStyleSheet("background-color: #ef4444; color: white; border-radius: 12px; font-weight: 700; border: none;")

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            mins, secs = divmod(self.time_left, 60)
            self.timer_label.setText(f"{mins:02d}:{secs:02d}")
        else:
            self.timer.stop()
            self.btn_start.setText("▶ Start Session")

    def reset_timer(self):
        self.timer.stop()
        self.time_left = self.focus_input.value() * 60
        self.timer_label.setText(f"{self.focus_input.value():02d}:00")
        self.btn_start.setText("▶ Start Session")
        self.btn_start.setStyleSheet("background-color: #3b82f6; color: white; border-radius: 12px; font-weight: 700; border: none;")
        