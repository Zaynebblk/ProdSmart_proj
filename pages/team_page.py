from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QScrollArea, QLineEdit, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from pages.tasks_page import AddTaskDialog, TaskCard, ViewTaskDialog
from resources.priority import quadrant_from_flags
from resources.task_types import normalize_task_type
from resources.theme import get_theme, FONT_FAMILY, rgba
from resources.api_client import (
    ApiError,
    api_list_teams,
    api_create_team,
    api_join_team,
    api_get_team,
    api_list_team_tasks,
    api_create_team_task,
    api_update_team_task,
    api_delete_team_task,
    get_base_url,
)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class TeamPage(QWidget):
    task_added = pyqtSignal()
    team_pomodoro_requested = pyqtSignal(int, bool)
    def __init__(self):
        super().__init__()
        self.setObjectName("TeamPage")
        self.current_theme = "Light"
        self.current_team_id = None
        self.team_meta = {}
        self._tasks_cache = {}
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
        self._render_tasks(tasks)

    def _render_tasks(self, tasks):
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
                card = self._build_task_card(t)
                if card:
                    self.tasks_layout.addWidget(card)

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
        ViewTaskDialog(
            task.get("title") or "",
            task.get("description") or "",
            due_pretty,
            created_pretty,
            priority,
            task_type,
            0,
            0,
            [],
            self,
            theme=self.current_theme,
        ).exec()

    def start_pomodoro(self, t_id, title, priority=None, task_type=None):
        if not self.current_team_id:
            QMessageBox.information(self, "Team Focus", "Select a team before starting a team session.")
            return
        self.team_pomodoro_requested.emit(self.current_team_id, True)

    def _build_task_card(self, task):
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
            0,
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
