from datetime import datetime
import json
import os
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QScrollArea, QLineEdit, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QTimer
from pages.tasks_page import AddTaskDialog, TaskCard, ViewTaskDialog
from database.db_manager import get_db_connection
from resources.priority import quadrant_from_flags, normalize_priority
from resources.task_types import normalize_task_type
from resources.theme import get_theme, FONT_FAMILY, rgba
from resources.time_format import format_duration_minutes
from resources.api_client import (
    ApiError,
    api_list_teams,
    api_create_team,
    api_join_team,
    api_get_team,
    api_list_team_members,
    api_list_team_tasks,
    api_create_team_task,
    api_update_team_task,
    api_delete_team_task,
    api_list_team_messages,
    api_send_team_message,
    get_base_url,
)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class TeamPage(QWidget):
    task_added = pyqtSignal()
    team_pomodoro_requested = pyqtSignal(int, bool)
    team_task_pomodoro_requested = pyqtSignal(str, str, object, object)
    def __init__(self):
        super().__init__()
        self.setObjectName("TeamPage")
        self.current_theme = "Light"
        self.current_team_id = None
        self.team_meta = {}
        self._tasks_cache = {}
        self.chat_timer = QTimer()
        self.chat_timer.timeout.connect(self.refresh_chat)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        root.addWidget(self.scroll)

        self.content = QWidget()
        self.scroll.setWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(18)

        self.title = QLabel("Team Workspace")
        self.title.setObjectName("TeamTitle")
        layout.addWidget(self.title)

        self.server_label = QLabel(f"Server: {get_base_url()}")
        self.server_label.setObjectName("TeamServer")
        layout.addWidget(self.server_label)

        team_bar = QFrame()
        team_bar.setObjectName("TeamBar")
        bar_layout = QHBoxLayout(team_bar)
        bar_layout.setContentsMargins(12, 12, 12, 12)
        bar_layout.setSpacing(10)

        self.team_combo = NoWheelComboBox()
        self.team_combo.setMinimumWidth(240)
        self.team_combo.currentIndexChanged.connect(self.on_team_changed)
        bar_layout.addWidget(self.team_combo, stretch=1)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_teams)
        bar_layout.addWidget(self.btn_refresh)

        self.btn_create = QPushButton("Create Team")
        self.btn_create.clicked.connect(self.create_team)
        bar_layout.addWidget(self.btn_create)

        self.btn_join = QPushButton("Join Team")
        self.btn_join.clicked.connect(self.join_team)
        bar_layout.addWidget(self.btn_join)

        layout.addWidget(team_bar)

        self.join_code_label = QLabel("Join code: -")
        self.join_code_label.setObjectName("TeamJoinCode")
        layout.addWidget(self.join_code_label)

        self.members_card = QFrame()
        self.members_card.setObjectName("TeamMembersCard")
        members_layout = QVBoxLayout(self.members_card)
        members_layout.setContentsMargins(16, 14, 16, 14)
        members_layout.setSpacing(12)

        members_header = QHBoxLayout()
        self.members_title = QLabel("Team Members")
        self.members_title.setObjectName("TeamMembersTitle")
        self.members_count = QLabel("0 ACTIVE")
        self.members_count.setObjectName("TeamMembersCount")
        members_header.addWidget(self.members_title)
        members_header.addStretch()
        members_header.addWidget(self.members_count)
        members_layout.addLayout(members_header)

        self.members_list = QVBoxLayout()
        self.members_list.setSpacing(10)
        self.members_list.setContentsMargins(2, 2, 2, 2)

        self.members_container = QWidget()
        self.members_container.setLayout(self.members_list)
        self.members_scroll = QScrollArea()
        self.members_scroll.setWidgetResizable(True)
        self.members_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.members_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.members_scroll.setWidget(self.members_container)
        self.members_scroll.setFixedHeight(240)
        members_layout.addWidget(self.members_scroll)

        self.members_empty = QLabel("No members yet.")
        self.members_empty.setObjectName("TeamEmpty")
        self.members_list.addWidget(self.members_empty)

        self.chat_card = QFrame()
        self.chat_card.setObjectName("TeamChatCard")
        chat_layout = QVBoxLayout(self.chat_card)
        chat_layout.setContentsMargins(16, 14, 16, 14)
        chat_layout.setSpacing(12)

        chat_header = QHBoxLayout()
        self.chat_title = QLabel("Team Chat")
        self.chat_title.setObjectName("TeamChatTitle")
        self.chat_hint = QLabel("")
        self.chat_hint.setObjectName("TeamChatHint")
        chat_header.addWidget(self.chat_title)
        chat_header.addStretch()

        chat_header.addWidget(self.chat_hint)
        chat_layout.addLayout(chat_header)

        self.chat_list = QVBoxLayout()
        self.chat_list.setSpacing(12)
        self.chat_list.setContentsMargins(6, 6, 6, 6)

        self.chat_container = QWidget()
        self.chat_container.setLayout(self.chat_list)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.chat_scroll.setWidget(self.chat_container)
        self.chat_scroll.setFixedHeight(300)
        chat_layout.addWidget(self.chat_scroll)

        self.chat_empty = QLabel("No messages yet.")
        self.chat_empty.setObjectName("TeamEmpty")
        self.chat_list.addWidget(self.chat_empty)

        chat_input_row = QHBoxLayout()
        chat_input_row.setSpacing(10)

        self.chat_input_card = QFrame()
        self.chat_input_card.setObjectName("TeamChatInputCard")
        input_layout = QHBoxLayout(self.chat_input_card)
        input_layout.setContentsMargins(14, 6, 14, 6)
        input_layout.setSpacing(8)

        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("TeamChatInput")
        self.chat_input.setPlaceholderText("Message the team...")
        self.chat_input.setFixedHeight(32)
        self.chat_input.setFrame(False)
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_layout.addWidget(self.chat_input, 1)

        chat_input_row.addWidget(self.chat_input_card, 1)

        self.chat_send_btn = QPushButton(">")
        self.chat_send_btn.setObjectName("TeamChatSend")
        self.chat_send_btn.setFixedSize(44, 44)
        self.chat_send_btn.clicked.connect(self.send_chat_message)
        chat_input_row.addWidget(self.chat_send_btn)
        chat_layout.addLayout(chat_input_row)
        layout.addWidget(self.members_card)
        layout.addWidget(self.chat_card)

        tasks_header = QHBoxLayout()
        self.tasks_title = QLabel("Team Tasks")
        self.tasks_title.setObjectName("TeamSectionTitle")
        tasks_header.addWidget(self.tasks_title)
        tasks_header.addStretch()
        self.btn_add_task = QPushButton("Add Task")
        self.btn_add_task.clicked.connect(self.add_task)
        tasks_header.addWidget(self.btn_add_task)
        layout.addLayout(tasks_header)

        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(14)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self.tasks_container)

        self.empty_label = QLabel("No team tasks yet.")
        self.empty_label.setObjectName("TeamEmpty")
        self.tasks_layout.addWidget(self.empty_label)

    def update_theme(self, theme):
        self.current_theme = theme
        c = get_theme(theme)
        self.setStyleSheet(
            f"QWidget#TeamPage {{ background: {c['bg']}; font-family: '{FONT_FAMILY}', 'Segoe UI'; }}"
            f"QLabel#TeamTitle {{ color: {c['text']}; font-size: 30px; font-weight: 900; }}"
            f"QLabel#TeamServer {{ color: {c['sub']}; font-size: 12px; }}"
            f"QFrame#TeamBar {{ background: {rgba(c['card'], 0.96)}; border: 1px solid {c['border']}; border-radius: 14px; }}"
            f"QComboBox {{ background: {c['input_bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 10px; color: {c['text']}; }}"
            f"QPushButton {{ background: {c['accent']}; color: white; border-radius: 8px; padding: 8px 14px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: {c['deep']}; }}"
            f"QLabel#TeamJoinCode {{ color: {c['sub']}; font-weight: 600; }}"
            f"QLabel#TeamSectionTitle {{ color: {c['text']}; font-size: 18px; font-weight: 800; }}"
            f"QLabel#TeamEmpty {{ color: {c['sub']}; font-size: 12px; }}"
            f"QFrame#TeamMembersCard {{ background: {rgba(c['card_alt'], 0.92)}; border: 1px solid {rgba(c['border'], 0.7)}; border-radius: 18px; }}"
            f"QFrame#TeamChatCard {{ background: {rgba(c['card_alt'], 0.92)}; border: 1px solid {rgba(c['border'], 0.7)}; border-radius: 18px; }}"
            f"QLabel#TeamMembersTitle {{ color: {c['text']}; font-size: 14px; font-weight: 800; }}"
            f"QLabel#TeamChatTitle {{ color: {c['text']}; font-size: 14px; font-weight: 800; }}"
            f"QLabel#TeamMembersCount {{ background: transparent; color: {c['sub']}; padding: 2px 2px; font-size: 10px; font-weight: 800; }}"
            f"QLabel#TeamChatHint {{ background: {rgba(c['accent'], 0.2)}; color: {c['accent']}; border-radius: 10px; padding: 2px 8px; font-size: 9px; font-weight: 800; }}"
            f"QFrame#TeamChatInputCard {{ background: {rgba(c['card_alt'], 0.85)}; border: 1px solid {rgba(c['border'], 0.7)}; border-radius: 22px; }}"
            f"QLineEdit#TeamChatInput {{ background: transparent; border: none; padding: 0 4px; color: {c['text']}; font-size: 12px; }}"
            f"QPushButton#TeamChatSend {{ background: {c['primary_gradient']}; color: white; border-radius: 22px; padding: 0; font-weight: 900; }}"
            f"QPushButton#TeamChatSend:hover {{ background: {c['accent']}; }}"
        )
        if hasattr(self, "members_container"):
            self.members_container.setStyleSheet("QWidget { background: transparent; }")
        if hasattr(self, "chat_container"):
            self.chat_container.setStyleSheet(
                f"QWidget {{ background: {rgba(c['card'], 0.85)}; border: 1px solid {rgba(c['border'], 0.6)}; border-radius: 16px; }}"
            )
        for i in range(self.tasks_layout.count()):
            item = self.tasks_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget and hasattr(widget, "update_theme"):
                try:
                    widget.update_theme(theme)
                except Exception:
                    pass

    def refresh_teams(self):
        self.server_label.setText(f"Server: {get_base_url()}")
        try:
            res = api_list_teams()
        except ApiError as e:
            QMessageBox.warning(self, "Team Error", str(e))
            return
        teams = res.get("teams", []) if isinstance(res, dict) else []
        self.team_combo.blockSignals(True)
        self.team_combo.clear()
        self.team_meta = {}
        if not teams:
            self.team_combo.addItem("No teams yet", None)
        else:
            for t in teams:
                team_id = t.get("id")
                name = t.get("name") or f"Team {team_id}"
                self.team_combo.addItem(name, team_id)
                self.team_meta[team_id] = t
        self.team_combo.blockSignals(False)
        self.on_team_changed(self.team_combo.currentIndex())

    def on_team_changed(self, idx):
        team_id = self.team_combo.currentData()
        self.current_team_id = team_id
        if not team_id:
            self.join_code_label.setText("Join code: -")
            self._render_tasks([])
            self._render_members([])
            self._render_chat([])
            if self.chat_timer.isActive():
                self.chat_timer.stop()
            return
        try:
            info = api_get_team(team_id)
            join_code = info.get("join_code") if isinstance(info, dict) else None
            if join_code:
                self.join_code_label.setText(f"Join code: {join_code}")
            else:
                self.join_code_label.setText("Join code: -")
        except ApiError:
            self.join_code_label.setText("Join code: -")
        self.refresh_members()
        self.refresh_chat()
        if not self.chat_timer.isActive():
            self.chat_timer.start(5000)
        self.refresh_tasks()

    def refresh_tasks(self):
        if not self.current_team_id:
            self._render_tasks([])
            return
        try:
            res = api_list_team_tasks(self.current_team_id)
        except ApiError as e:
            QMessageBox.warning(self, "Team Tasks", str(e))
            return
        tasks = res.get("tasks", []) if isinstance(res, dict) else []
        self._tasks_cache = {t.get("id"): t for t in tasks if isinstance(t, dict)}
        focus_map = self._load_focus_minutes(tasks)
        self._render_tasks(tasks, focus_map)

    def refresh_members(self):
        if not self.current_team_id:
            self._render_members([])
            return
        try:
            res = api_list_team_members(self.current_team_id)
        except ApiError as e:
            QMessageBox.warning(self, "Team Members", str(e))
            return
        members = res.get("members", []) if isinstance(res, dict) else []
        self._render_members(members)

    def refresh_chat(self):
        if not self.current_team_id:
            self._render_chat([])
            return
        try:
            res = api_list_team_messages(self.current_team_id, limit=50)
        except ApiError:
            return
        except Exception:
            return
        messages = res.get("messages", []) if isinstance(res, dict) else []
        self._render_chat(messages)

    def pause_network(self):
        if self.chat_timer.isActive():
            self.chat_timer.stop()

    def send_chat_message(self):
        if not self.current_team_id:
            QMessageBox.information(self, "Team Chat", "Please select a team first.")
            return
        msg = self.chat_input.text().strip() if hasattr(self, "chat_input") else ""
        if not msg:
            return
        try:
            api_send_team_message(self.current_team_id, msg)
        except ApiError as e:
            QMessageBox.warning(self, "Team Chat", str(e))
            return
        self.chat_input.clear()
        self.refresh_chat()

    def _render_tasks(self, tasks, focus_map=None):
        while self.tasks_layout.count():
            item = self.tasks_layout.takeAt(0)
            widget = item.widget()
            if widget:
                self.tasks_layout.removeWidget(widget)
                if widget is not self.empty_label:
                    widget.deleteLater()
        try:
            self.empty_label.hide()
        except Exception:
            pass
        if not tasks:
            try:
                self.empty_label.show()
            except Exception:
                pass
            self.tasks_layout.addWidget(self.empty_label)
        else:
            for t in tasks:
                focus_minutes = 0
                if focus_map is not None:
                    try:
                        focus_minutes = int(focus_map.get(t.get("id"), 0) or 0)
                    except Exception:
                        focus_minutes = 0
                card = self._build_task_card(t, focus_minutes)
                if card:
                    self.tasks_layout.addWidget(card)

    def _current_username(self):
        settings_path = os.path.join(os.getcwd(), "settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("cloud_username")
        except Exception:
            return None
        return None

    def _member_avatar_colors(self, username):
        c = get_theme(self.current_theme)
        palette = [c["accent"], c["accent2"], c["deep"], c["chip_text"]]
        key = sum(ord(ch) for ch in (username or "")) % len(palette)
        base = palette[key]
        return rgba(base, 0.22), base

    def _build_member_card(self, username, role):
        c = get_theme(self.current_theme)
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {c['card']}; border: 1px solid {rgba(c['border'], 0.6)}; border-radius: 16px; }}"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        initials = "".join([part[:1] for part in re.split(r"[^A-Za-z0-9]+", username or "") if part])[:2].upper()
        if not initials:
            initials = "U"
        if (role or "").lower() == "owner":
            avatar_bg = rgba(c["accent"], 0.28)
            avatar_fg = c["accent"]
        else:
            avatar_bg = rgba(c["chip_text"], 0.2)
            avatar_fg = c["text"]
        avatar = QLabel(initials)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(44, 44)
        avatar.setStyleSheet(
            f"background: {avatar_bg}; color: {avatar_fg}; border-radius: 20px; font-weight: 800;"
        )
        layout.addWidget(avatar)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name = QLabel(username or "Unknown")
        name.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {c['text']};")
        role_text = "Lead Designer" if (role or "").lower() == "owner" else "Team Member"
        subtitle = QLabel(role_text)
        subtitle.setStyleSheet(f"font-size: 10px; color: {c['sub']}; font-weight: 600;")
        name_col.addWidget(name)
        name_col.addWidget(subtitle)
        layout.addLayout(name_col)
        layout.addStretch()

        badge_text = (role or "member").upper()
        if (role or "").lower() == "owner":
            badge_bg = rgba(c["accent"], 0.22)
            badge_fg = c["accent"]
        else:
            badge_bg = rgba(c["chip_text"], 0.18)
            badge_fg = c["sub"]
        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"background: {badge_bg}; color: {badge_fg}; border-radius: 10px; padding: 2px 10px; "
            f"font-size: 9px; font-weight: 800; letter-spacing: 1px;"
        )
        layout.addWidget(badge)
        return card

    def _render_members(self, members):
        while self.members_list.count():
            item = self.members_list.takeAt(0)
            widget = item.widget()
            if widget:
                self.members_list.removeWidget(widget)
                if widget is not self.members_empty:
                    widget.deleteLater()
        try:
            self.members_empty.hide()
        except Exception:
            pass
        if not members:
            try:
                self.members_empty.show()
            except Exception:
                pass
            self.members_list.addWidget(self.members_empty)
            if hasattr(self, "members_count"):
                self.members_count.setText("0 ACTIVE")
            return
        if hasattr(self, "members_count"):
            self.members_count.setText(f"{len(members)} ACTIVE")
        for m in members:
            username = m.get("username") if isinstance(m, dict) else None
            role = m.get("role") if isinstance(m, dict) else None
            card = self._build_member_card(username, role)
            self.members_list.addWidget(card)

    def _render_chat(self, messages):
        c = get_theme(self.current_theme)
        while self.chat_list.count():
            item = self.chat_list.takeAt(0)
            widget = item.widget()
            if widget:
                self.chat_list.removeWidget(widget)
                if widget is not self.chat_empty:
                    widget.deleteLater()
        try:
            self.chat_empty.hide()
        except Exception:
            pass
        if not messages:
            try:
                self.chat_empty.show()
            except Exception:
                pass
            self.chat_list.addWidget(self.chat_empty)
            if hasattr(self, "chat_hint"):
                self.chat_hint.setText("Live")
            self._update_chat_avatars([])
            return
        if hasattr(self, "chat_hint"):
            self.chat_hint.setText("")

        current_user = (self._current_username() or "").strip().lower()
        participants = []
        for msg in messages:
            username = msg.get("username") if isinstance(msg, dict) else None
            if not username:
                continue
            uname = str(username)
            if uname not in participants:
                participants.append(uname)
        self._update_chat_avatars(participants)
        for msg in messages:
            username = msg.get("username") if isinstance(msg, dict) else None
            text = msg.get("message") if isinstance(msg, dict) else None
            created_at = msg.get("created_at") if isinstance(msg, dict) else None
            is_own = bool(current_user and username and str(username).strip().lower() == current_user)

            bubble = QFrame()
            if is_own:
                bubble_bg = c["card"]
                border = rgba(c["border"], 0.7)
            else:
                bubble_bg = c["card_alt"]
                border = rgba(c["border"], 0.5)
            bubble.setStyleSheet(
                f"QFrame {{ background: {bubble_bg}; border: 1px solid {border}; border-radius: 14px; }}"
            )
            bubble.setMaximumWidth(520)
            bubble_layout = QVBoxLayout(bubble)
            bubble_layout.setContentsMargins(12, 10, 12, 10)
            bubble_layout.setSpacing(4)

            header = QHBoxLayout()
            if not is_own:
                name = QLabel(str(username or "User").upper())
                name.setStyleSheet(f"font-size: 9px; font-weight: 800; color: {c['accent']}; letter-spacing: 1px;")
                header.addWidget(name)
            header.addStretch()
            stamp = self._format_chat_time(created_at)
            if stamp:
                time_lbl = QLabel(stamp)
                time_lbl.setStyleSheet(f"font-size: 9px; color: {c['sub']};")
                header.addWidget(time_lbl)
            bubble_layout.addLayout(header)

            body = QLabel(text or "")
            body.setWordWrap(True)
            body.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {c['text']};")
            bubble_layout.addWidget(body)

            wrapper = QWidget()
            row = QHBoxLayout(wrapper)
            row.setContentsMargins(0, 0, 0, 0)
            if is_own:
                row.addStretch()
                row.addWidget(bubble)
            else:
                row.addWidget(bubble)
                row.addStretch()
            self.chat_list.addWidget(wrapper)

        try:
            bar = self.chat_scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        except Exception:
            pass

    def _update_chat_avatars(self, usernames):
        return

    def _format_chat_time(self, raw):
        if not raw:
            return ""
        raw_text = str(raw).replace("T", " ").split(".")[0]
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(raw_text, fmt)
                return dt.strftime("%I:%M %p").lstrip("0")
            except Exception:
                continue
        return raw_text

    def create_team(self):
        name, ok = self._prompt_text("Create Team", "Team name")
        if not ok or not name:
            return
        try:
            api_create_team(name)
        except ApiError as e:
            QMessageBox.warning(self, "Create Team", str(e))
            return
        self.refresh_teams()

    def join_team(self):
        code, ok = self._prompt_text("Join Team", "Join code")
        if not ok or not code:
            return
        try:
            api_join_team(code)
        except ApiError as e:
            QMessageBox.warning(self, "Join Team", str(e))
            return
        self.refresh_teams()

    def add_task(self):
        if not self.current_team_id:
            QMessageBox.information(self, "Team Tasks", "Please select a team first.")
            return
        dlg = AddTaskDialog(self, "New Team Task", theme=self.current_theme)
        if dlg.exec():
            data = dlg.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "Team Tasks", "Title is required.")
                return
            try:
                api_create_team_task(
                    self.current_team_id,
                    data["title"],
                    data.get("description", ""),
                    data.get("date"),
                    data.get("important"),
                    data.get("task_type"),
                )
            except ApiError as e:
                QMessageBox.warning(self, "Team Tasks", str(e))
                return
            self.refresh_tasks()

    def set_task_completed(self, task_id, is_completed):
        if not self.current_team_id or not task_id:
            return
        try:
            api_update_team_task(self.current_team_id, task_id, is_completed=is_completed)
        except ApiError as e:
            QMessageBox.warning(self, "Team Tasks", str(e))
        self.refresh_tasks()

    def mark_task_completed(self, task_id, checked):
        self.set_task_completed(task_id, bool(checked))

    def delete_task(self, task_id):
        if not self.current_team_id or not task_id:
            return
        try:
            api_delete_team_task(self.current_team_id, task_id)
        except ApiError as e:
            QMessageBox.warning(self, "Team Tasks", str(e))
        self.refresh_tasks()

    def edit_task(self, t_id):
        task = self._tasks_cache.get(t_id)
        if not task:
            return
        dlg = AddTaskDialog(self, "Edit Team Task", theme=self.current_theme)
        dlg.load_data(
            task.get("title") or "",
            task.get("description") or "",
            task.get("due_date") or "",
            bool(task.get("is_important")),
            task.get("task_type"),
        )
        if dlg.exec():
            data = dlg.get_data()
            try:
                api_update_team_task(
                    self.current_team_id,
                    t_id,
                    title=data.get("title"),
                    description=data.get("description"),
                    due_date=data.get("date"),
                    is_important=data.get("important"),
                    task_type=data.get("task_type"),
                )
            except ApiError as e:
                QMessageBox.warning(self, "Team Tasks", str(e))
                return
            self.refresh_tasks()

    def show_task_details(self, t_id):
        task = self._tasks_cache.get(t_id)
        if not task:
            return
        due_pretty = self._pretty_due(task.get("due_date"))
        created_pretty = self._pretty_created(task.get("created_date"), task.get("created_at"))
        is_imp = bool(task.get("is_important"))
        is_urg = task.get("is_urgent")
        if is_urg is None:
            is_urg = self._deadline_is_urgent(task.get("due_date"))
        priority = task.get("priority") or quadrant_from_flags(is_urg, is_imp)
        task_type = normalize_task_type(task.get("task_type"))
        total_focus_min = 0
        total_sessions = 0
        sessions_widgets = []
        session_key = None
        if self.current_team_id:
            session_key = self._team_session_key(self.current_team_id, t_id)
        if session_key:
            conn = None
            try:
                conn = get_db_connection()
                total_row = conn.execute(
                    "SELECT COALESCE(SUM(duration_min), 0) FROM pomodoro_sessions WHERE task_id=? AND status='completed'",
                    (session_key,)
                ).fetchone()
                if total_row:
                    total_focus_min = int(total_row[0] or 0)

                total_sessions_row = conn.execute(
                    "SELECT COUNT(*) FROM pomodoro_sessions WHERE task_id=?",
                    (session_key,)
                ).fetchone()
                if total_sessions_row:
                    total_sessions = int(total_sessions_row[0] or 0)

                sess_rows = conn.execute(
                    "SELECT started_at, duration_min, status FROM pomodoro_sessions WHERE task_id=? ORDER BY started_at DESC",
                    (session_key,)
                ).fetchall()
                for started_at, duration_min, status in sess_rows:
                    display_time = "Unknown time"
                    if started_at:
                        raw = str(started_at).split(".")[0]
                        dt = None
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                            try:
                                dt = datetime.strptime(raw, fmt)
                                break
                            except ValueError:
                                continue
                        if dt:
                            display_time = dt.strftime("%b %d, %H:%M")
                    dur = int(duration_min or 0)
                    st = str(status or "").lower()
                    status_text = st if st else "completed"
                    lbl = QLabel(f"{display_time}  -  {format_duration_minutes(dur)}  ({status_text})")
                    lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
                    sessions_widgets.append(lbl)
            except Exception:
                sessions_widgets = []
            finally:
                if conn:
                    conn.close()
        ViewTaskDialog(
            task.get("title") or "",
            task.get("description") or "",
            due_pretty,
            created_pretty,
            priority,
            task_type,
            total_focus_min,
            total_sessions,
            sessions_widgets,
            self,
            theme=self.current_theme,
        ).exec()

    def start_pomodoro(self, t_id, title, priority=None, task_type=None):
        if not self.current_team_id:
            QMessageBox.information(self, "Team Focus", "Select a team before starting a team session.")
            return
        session_key = self._team_session_key(self.current_team_id, t_id)
        prio = normalize_priority(priority) or "too low"
        self.team_task_pomodoro_requested.emit(session_key, title, prio, normalize_task_type(task_type))

    def _build_task_card(self, task, focus_minutes=0):
        if not isinstance(task, dict):
            return None
        due_pretty = self._pretty_due(task.get("due_date"))
        created_pretty = self._pretty_created(task.get("created_date"), task.get("created_at"))
        is_imp = bool(task.get("is_important"))
        is_urg = task.get("is_urgent")
        if is_urg is None:
            is_urg = self._deadline_is_urgent(task.get("due_date"))
        priority = task.get("priority") or quadrant_from_flags(is_urg, is_imp)
        task_type = normalize_task_type(task.get("task_type"))
        card = TaskCard(
            task.get("id"),
            task.get("title") or "",
            task.get("description") or "",
            due_pretty,
            created_pretty,
            priority,
            focus_minutes,
            self,
            bool(task.get("is_completed")),
            task_type,
        )
        card.update_theme(self.current_theme)
        return card

    def _pretty_due(self, due_date_str):
        if not due_date_str:
            return "No Deadline"
        d = QDate.fromString(str(due_date_str)[:10], "yyyy-MM-dd")
        if d.isValid():
            return d.toString("dddd d MMMM yyyy")
        return str(due_date_str)

    def _pretty_created(self, created_date_str, created_at_str=None):
        raw = created_date_str or created_at_str
        if not raw:
            return "Unknown"
        raw = str(raw)
        date_part = raw[:10]
        d = QDate.fromString(date_part, "yyyy-MM-dd")
        if d.isValid():
            return d.toString("d MMM yyyy")
        return date_part

    def _deadline_is_urgent(self, due_date_str):
        if not due_date_str:
            return 0
        try:
            due = QDate.fromString(str(due_date_str)[:10], "yyyy-MM-dd")
        except Exception:
            return 0
        if not due.isValid():
            return 0
        today = QDate.currentDate()
        days_to = today.daysTo(due)
        return 1 if days_to <= 2 else 0

    def _team_session_key(self, team_id, task_id):
        return f"team:{team_id}:{task_id}"

    def _load_focus_minutes(self, tasks):
        if not self.current_team_id:
            return {}
        if not tasks:
            return {}
        keys = []
        task_ids = []
        for t in tasks:
            if not isinstance(t, dict):
                continue
            t_id = t.get("id")
            if t_id is None:
                continue
            keys.append(self._team_session_key(self.current_team_id, t_id))
            task_ids.append(t_id)
        if not keys:
            return {}

        conn = None
        rows = []
        try:
            conn = get_db_connection()
            placeholders = ",".join("?" for _ in keys)
            rows = conn.execute(
                f"SELECT task_id, COALESCE(SUM(duration_min), 0) "
                f"FROM pomodoro_sessions "
                f"WHERE task_id IN ({placeholders}) AND status IN ('completed', 'stopped') "
                f"GROUP BY task_id",
                tuple(keys),
            ).fetchall()
        except Exception:
            rows = []
        finally:
            if conn:
                conn.close()

        minutes_by_key = {row[0]: int(row[1] or 0) for row in rows}
        focus_map = {}
        for idx, t_id in enumerate(task_ids):
            key = keys[idx]
            focus_map[t_id] = minutes_by_key.get(key, 0)
        return focus_map

    def _prompt_text(self, title, placeholder):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel(placeholder)
        input_box = QLineEdit()
        layout.addWidget(label)
        layout.addWidget(input_box)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_ok = QPushButton("OK")
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return input_box.text().strip(), ok
