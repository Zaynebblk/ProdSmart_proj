from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen
from datetime import datetime, timedelta
import random
import zlib
from database.db_manager import get_db_connection


class FocusRingWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.percent = 0
        self.label = "Deep"
        self.colors = {}
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, percent, label):
        self.percent = max(0, min(int(percent), 100))
        self.label = label
        self.update()

    def set_theme(self, colors):
        self.colors = colors or {}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        size = min(rect.width(), rect.height()) - 8
        x = rect.center().x() - size / 2
        y = rect.center().y() - size / 2
        ring_rect = QRectF(x, y, size, size)

        base_color = QColor(self.colors.get("primary_soft_border", "#2f7c98"))
        arc_color = QColor(self.colors.get("primary", "#11a4d4"))

        pen_bg = QPen(base_color, 6)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(ring_rect, 0, 360 * 16)

        pen_fg = QPen(arc_color, 6)
        pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_fg)
        span = int(-self.percent * 360 / 100 * 16)
        painter.drawArc(ring_rect, 90 * 16, span)

        painter.setPen(QColor(self.colors.get("text", "#f1f5f9")))
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(ring_rect, Qt.AlignmentFlag.AlignCenter, f"{self.percent}%")

        label_rect = QRectF(ring_rect.left(), ring_rect.center().y() + 12, ring_rect.width(), 18)
        painter.setPen(QColor(self.colors.get("sub", "#94a3b8")))
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self.label)


class TimelineBarsWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.values = [60, 80, 95, 100, 90, 45, 70, 92, 88, 55]
        self.colors = {}
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, values):
        if values:
            self.values = list(values)
        self.update()

    def set_theme(self, colors):
        self.colors = colors or {}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        left_pad = 8
        right_pad = 8
        top_pad = 6
        bottom_pad = 8
        chart_rect = QRectF(
            rect.left() + left_pad,
            rect.top() + top_pad,
            rect.width() - left_pad - right_pad,
            rect.height() - top_pad - bottom_pad
        )

        values = self.values or []
        if not values:
            return

        count = len(values)
        gap = 6
        bar_w = (chart_rect.width() - gap * (count - 1)) / max(count, 1)
        primary = QColor(self.colors.get("primary", "#11a4d4"))

        for idx, val in enumerate(values):
            height = (max(0, min(val, 100)) / 100) * chart_rect.height()
            x = chart_rect.left() + idx * (bar_w + gap)
            y = chart_rect.bottom() - height
            bar_rect = QRectF(x, y, bar_w, height)
            shade = QColor(primary)
            if val < 60:
                shade.setAlpha(80)
            elif val < 85:
                shade.setAlpha(160)
            else:
                shade.setAlpha(220)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shade)
            painter.drawRoundedRect(bar_rect, 3, 3)


class SessionReportPage(QWidget):
    request_history = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_theme = "Light"
        self.colors = {}
        self.current_period = "Today"
        self.setObjectName("ReportPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        root.addWidget(self.scroll)

        self.container = QWidget()
        self.content = QVBoxLayout(self.container)
        self.content.setContentsMargins(18, 16, 18, 24)
        self.content.setSpacing(16)
        self.scroll.setWidget(self.container)

        # Header
        self.header = QFrame()
        self.header.setObjectName("ReportHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(6, 6, 6, 6)
        header_layout.setSpacing(10)

        self.back_btn = QPushButton("<")
        self.back_btn.setObjectName("ReportBackButton")
        self.back_btn.setFixedSize(36, 36)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.request_history.emit)

        self.header_title = QLabel("Session Report")
        self.header_title.setObjectName("ReportTitle")

        header_layout.addWidget(self.back_btn)
        header_layout.addStretch()
        header_layout.addWidget(self.header_title)
        header_layout.addStretch()

        self.content.addWidget(self.header)

        # Date & time
        self.date_label = QLabel("Date")
        self.time_label = QLabel("Time")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content.addWidget(self.date_label)
        self.content.addWidget(self.time_label)

        # Period selector
        self.period_frame = QFrame()
        self.period_frame.setObjectName("ReportPeriod")
        period_layout = QHBoxLayout(self.period_frame)
        period_layout.setContentsMargins(4, 4, 4, 4)
        period_layout.setSpacing(4)

        self.period_group = QButtonGroup(self)
        self.period_today = QPushButton("Today")
        self.period_week = QPushButton("This Week")
        self.period_month = QPushButton("This Month")
        for btn in (self.period_today, self.period_week, self.period_month):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.period_group.addButton(btn)
            period_layout.addWidget(btn)
        self.period_today.setChecked(True)
        self.period_group.buttonClicked.connect(self._on_period_changed)
        self.content.addWidget(self.period_frame)

        # Summary cards
        self.summary_container = QWidget()
        self.summary_layout = QHBoxLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(12)
        self.summary_cards = []
        for title in ("Total Focus", "Efficiency", "Tasks"):
            card = QFrame()
            card.setObjectName("ReportSummaryCard")
            card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(6)
            title_lbl = QLabel(title)
            value_lbl = QLabel("0")
            delta_lbl = QLabel("+0%")
            card_layout.addWidget(title_lbl)
            card_layout.addWidget(value_lbl)
            card_layout.addWidget(delta_lbl)
            self.summary_layout.addWidget(card)
            self.summary_cards.append({
                "card": card,
                "title": title_lbl,
                "value": value_lbl,
                "delta": delta_lbl
            })
        self.content.addWidget(self.summary_container)

        # Focus breakdown
        self.breakdown_title = QLabel("Focus Breakdown")
        self.content.addWidget(self.breakdown_title)

        self.breakdown_frame = QFrame()
        self.breakdown_frame.setObjectName("ReportBreakdown")
        breakdown_layout = QHBoxLayout(self.breakdown_frame)
        breakdown_layout.setContentsMargins(16, 14, 16, 14)
        breakdown_layout.setSpacing(16)

        self.ring = FocusRingWidget()
        breakdown_layout.addWidget(self.ring)

        breakdown_right = QVBoxLayout()
        breakdown_right.setSpacing(10)
        self.deep_row = QLabel("Deep Focus")
        self.deep_value = QLabel("0m")
        self.minor_row = QLabel("Minor Distractions")
        self.minor_value = QLabel("0m")
        self.breakdown_note = QLabel(" ")
        self.breakdown_note.setWordWrap(True)

        breakdown_right.addWidget(self.deep_row)
        breakdown_right.addWidget(self.deep_value)
        breakdown_right.addWidget(self.minor_row)
        breakdown_right.addWidget(self.minor_value)
        breakdown_right.addWidget(self.breakdown_note)
        breakdown_layout.addLayout(breakdown_right)

        self.content.addWidget(self.breakdown_frame)

        # Timeline
        self.timeline_title = QLabel("Session Timeline")
        self.content.addWidget(self.timeline_title)

        self.timeline_frame = QFrame()
        self.timeline_frame.setObjectName("ReportTimeline")
        timeline_layout = QVBoxLayout(self.timeline_frame)
        timeline_layout.setContentsMargins(12, 10, 12, 10)
        timeline_layout.setSpacing(8)
        self.timeline_chart = TimelineBarsWidget()
        timeline_layout.addWidget(self.timeline_chart)

        timeline_labels = QHBoxLayout()
        self.timeline_start = QLabel("0m")
        self.timeline_mid = QLabel("0m")
        self.timeline_end = QLabel("0m")
        timeline_labels.addWidget(self.timeline_start)
        timeline_labels.addStretch()
        timeline_labels.addWidget(self.timeline_mid)
        timeline_labels.addStretch()
        timeline_labels.addWidget(self.timeline_end)
        timeline_layout.addLayout(timeline_labels)
        self.content.addWidget(self.timeline_frame)

        # Tasks
        self.tasks_title = QLabel("Tasks Completed")
        self.content.addWidget(self.tasks_title)
        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(10)
        self.content.addWidget(self.tasks_container)

        # Back to history
        self.back_action = QPushButton("Back to History")
        self.back_action.setObjectName("ReportPrimaryButton")
        self.back_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_action.clicked.connect(self.request_history.emit)
        self.content.addWidget(self.back_action)

        self.content.addStretch()

        self.update_theme("Light")

    def update_theme(self, theme):
        self.current_theme = theme
        if theme == "Dark":
            self.colors = {
                "bg": "#101d22",
                "card": "#0f1b20",
                "border": "#1f2a2f",
                "text": "#f1f5f9",
                "sub": "#94a3b8",
                "primary": "#11a4d4",
                "primary_soft": "rgba(17, 164, 212, 0.18)",
                "primary_soft_border": "rgba(17, 164, 212, 0.35)",
                "good": "#34d399",
                "bad": "#f87171",
            }
        else:
            self.colors = {
                "bg": "#f6f8f8",
                "card": "#ffffff",
                "border": "#e2e8f0",
                "text": "#0f172a",
                "sub": "#64748b",
                "primary": "#11a4d4",
                "primary_soft": "rgba(17, 164, 212, 0.12)",
                "primary_soft_border": "rgba(17, 164, 212, 0.25)",
                "good": "#10b981",
                "bad": "#ef4444",
            }

        self.apply_styles()

    def apply_styles(self):
        c = self.colors
        self.setStyleSheet(f"QWidget#ReportPage {{ background: {c['bg']}; }}")
        self.header.setStyleSheet(
            f"QFrame#ReportHeader {{ background: {c['bg']}; border-bottom: 1px solid {c['primary_soft_border']}; }}"
        )
        self.back_btn.setStyleSheet(
            f"QPushButton#ReportBackButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 18px; color: {c['text']}; font-weight: 700; }}"
        )
        self.header_title.setStyleSheet(
            f"color: {c['text']}; font-size: 16px; font-weight: 800;"
        )

        self.date_label.setStyleSheet(
            f"color: {c['primary']}; font-size: 12px; font-weight: 900; text-transform: uppercase;"
        )
        self.time_label.setStyleSheet(
            f"color: {c['sub']}; font-size: 11px; font-weight: 700;"
        )

        self.period_frame.setStyleSheet(
            f"QFrame#ReportPeriod {{ background: {c['primary_soft']}; border: 1px solid {c['primary_soft_border']}; border-radius: 10px; }}"
            "QPushButton { border: none; padding: 6px 10px; border-radius: 8px; font-size: 10px; font-weight: 800; }"
            f"QPushButton:checked {{ background: {c['card']}; color: {c['primary']}; }}"
            f"QPushButton:!checked {{ color: {c['sub']}; }}"
        )

        for item in self.summary_cards:
            item["card"].setStyleSheet(
                f"QFrame#ReportSummaryCard {{ background: {c['primary_soft']}; border: 1px solid {c['primary_soft_border']}; border-radius: 14px; }}"
            )
            item["title"].setStyleSheet(
                f"color: {c['sub']}; font-size: 10px; font-weight: 700;"
            )
            item["value"].setStyleSheet(
                f"color: {c['primary']}; font-size: 20px; font-weight: 900;"
            )
            item["delta"].setStyleSheet(
                f"color: {c['good']}; font-size: 10px; font-weight: 800;"
            )

        self.breakdown_title.setStyleSheet(
            f"color: {c['text']}; font-size: 16px; font-weight: 800;"
        )
        self.breakdown_frame.setStyleSheet(
            f"QFrame#ReportBreakdown {{ background: {c['primary_soft']}; border: 1px solid {c['primary_soft_border']}; border-radius: 16px; }}"
        )
        self.deep_row.setStyleSheet(
            f"color: {c['text']}; font-size: 12px; font-weight: 700;"
        )
        self.deep_value.setStyleSheet(
            f"color: {c['text']}; font-size: 12px; font-weight: 900;"
        )
        self.minor_row.setStyleSheet(
            f"color: {c['text']}; font-size: 12px; font-weight: 700;"
        )
        self.minor_value.setStyleSheet(
            f"color: {c['text']}; font-size: 12px; font-weight: 900;"
        )
        self.breakdown_note.setStyleSheet(
            f"color: {c['sub']}; font-size: 10px; font-weight: 600;"
        )
        self.ring.set_theme(c)

        self.timeline_title.setStyleSheet(
            f"color: {c['text']}; font-size: 16px; font-weight: 800;"
        )
        self.timeline_frame.setStyleSheet(
            f"QFrame#ReportTimeline {{ background: {c['primary_soft']}; border: 1px solid {c['primary_soft_border']}; border-radius: 14px; }}"
        )
        self.timeline_chart.set_theme(c)
        for lbl in (self.timeline_start, self.timeline_mid, self.timeline_end):
            lbl.setStyleSheet(
                f"color: {c['sub']}; font-size: 9px; font-weight: 800;"
            )

        self.tasks_title.setStyleSheet(
            f"color: {c['text']}; font-size: 16px; font-weight: 800;"
        )

        self.back_action.setStyleSheet(
            f"QPushButton#ReportPrimaryButton {{ background: {c['primary']}; color: white; border: none; border-radius: 14px; padding: 10px; font-size: 12px; font-weight: 900; }}"
        )

    def _parse_dt(self, value):
        if not value:
            return None
        raw = str(value)
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt)
            except Exception:
                continue
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return None

    def _format_time(self, dt):
        return dt.strftime("%I:%M %p").lstrip("0") if dt else ""

    def _seed_from(self, activity_id, dt_start, duration):
        raw = f"{activity_id}|{dt_start.isoformat() if dt_start else ''}|{duration}"
        return zlib.adler32(raw.encode("utf-8"))

    def _period_bounds(self):
        today = datetime.now().date()
        if self.current_period == "Week":
            start = today - timedelta(days=6)
            end = today
        elif self.current_period == "Month":
            start = today - timedelta(days=29)
            end = today
        else:
            start = today
            end = today
        return start, end

    def _on_period_changed(self, button):
        label = button.text().strip() if button else "Today"
        if label == "This Week":
            self.current_period = "Week"
        elif label == "This Month":
            self.current_period = "Month"
        elif label == "Today":
            self.current_period = "Today"
        else:
            return
        self._refresh_report()

    def _generate_timeline(self, duration, seed):
        if duration <= 0:
            return [60, 75, 85, 90, 80, 70, 65, 70]
        count = 10 if duration <= 60 else 12
        rnd = random.Random(seed)
        base = 55 + min(duration, 120) * 0.25
        trend = rnd.uniform(-10, 10)
        values = []
        for idx in range(count):
            t = idx / max(count - 1, 1)
            drift = (t - 0.5) * trend * 2
            noise = rnd.uniform(-12, 12)
            dip = -8 if (0.35 < t < 0.55 and rnd.random() < 0.5) else 0
            val = base + drift + noise + dip
            values.append(int(max(35, min(100, val))))
        return values

    def _summarize_timeline(self, values):
        if not values:
            return {
                "avg": 0,
                "min": 0,
                "max": 0,
                "variability": 0,
                "peak_idx": 0,
                "min_idx": 0,
                "first_avg": 0,
                "second_avg": 0
            }
        avg = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)
        peak_idx = values.index(max_val)
        min_idx = values.index(min_val)
        mid = max(1, len(values) // 2)
        first_avg = sum(values[:mid]) / mid
        second_avg = sum(values[mid:]) / max(len(values) - mid, 1)
        return {
            "avg": avg,
            "min": min_val,
            "max": max_val,
            "variability": max_val - min_val,
            "peak_idx": peak_idx,
            "min_idx": min_idx,
            "first_avg": first_avg,
            "second_avg": second_avg
        }

    def _calc_efficiency(self, summary):
        avg = summary["avg"]
        variability = summary["variability"]
        score = avg - variability * 0.2 + 10
        return int(max(50, min(99, score)))

    def _calc_focus_score(self, summary):
        avg = summary["avg"]
        return min(9.9, max(3.5, (avg / 100) * 9.5))

    def _calc_deep_pct(self, summary):
        avg = summary["avg"]
        variability = summary["variability"]
        pct = 50 + (avg - 50) * 1.1 - variability * 0.15
        return int(max(55, min(95, pct)))


    def load_report(self, activity_id=None):
        self._refresh_report()

    def _refresh_report(self):
        start_date, end_date = self._period_bounds()
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        try:
            sessions_all = conn.execute(
                "SELECT id, task_id, task_title, started_at, ended_at, duration_min, status "
                "FROM pomodoro_sessions WHERE started_at >= ? AND started_at <= ?",
                (start_str, end_str)
            ).fetchall()
        except Exception:
            sessions_all = []

        try:
            tasks_all = conn.execute(
                "SELECT id, title, is_completed, completed_at FROM tasks "
                "WHERE completed_at >= ? AND completed_at <= ?",
                (start_str, end_str)
            ).fetchall()
        except Exception:
            tasks_all = []
        try:
            session_task_ids = {row["task_id"] for row in sessions_all if row["task_id"] is not None}
            task_ids = {row["id"] for row in tasks_all}
            missing = list(session_task_ids - task_ids)
            if missing:
                placeholders = ",".join(["?"] * len(missing))
                extra = conn.execute(
                    f"SELECT id, title, is_completed, completed_at FROM tasks WHERE id IN ({placeholders})",
                    tuple(missing)
                ).fetchall()
                tasks_all = list(tasks_all) + list(extra)
        except Exception:
            tasks_all = list(tasks_all)
        finally:
            conn.close()

        sessions_filtered = list(sessions_all)
        tasks_filtered = list(tasks_all)

        dt_start = None
        dt_end = None
        total_minutes = 0
        for row in sessions_filtered:
            dt = self._parse_dt(row["started_at"])
            mins = int(row["duration_min"] or 0)
            total_minutes += mins
            if dt and (dt_start is None or dt < dt_start):
                dt_start = dt
            if dt:
                end_dt = self._parse_dt(row["ended_at"]) if row["ended_at"] else dt + timedelta(minutes=mins)
                if end_dt and (dt_end is None or end_dt > dt_end):
                    dt_end = end_dt

        if self.current_period == "Today":
            date_text = datetime.now().strftime("%b %d, %Y")
        else:
            date_text = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

        if len(sessions_filtered) == 1 and dt_start and dt_end:
            time_text = f"{self._format_time(dt_start)} - {self._format_time(dt_end)} ({total_minutes} mins)"
        elif total_minutes > 0:
            time_text = f"Total focus: {total_minutes} mins"
        else:
            time_text = "No sessions in this range"
        self.date_label.setText(date_text)
        self.time_label.setText(time_text)

        if self.current_period == "Week":
            period_label = "This Week"
        elif self.current_period == "Month":
            period_label = "This Month"
        else:
            period_label = "Today"
        self.header_title.setText(f"Session Report - {period_label}")

        seed = self._seed_from(f"{self.current_period}:{date_text}", dt_start or datetime.now(), total_minutes)
        timeline_values = self._generate_timeline(total_minutes, seed)
        summary = self._summarize_timeline(timeline_values)
        if total_minutes > 0:
            efficiency = self._calc_efficiency(summary)
            deep_pct = self._calc_deep_pct(summary)
        else:
            efficiency = 0
            deep_pct = 0
        deep_minutes = int(round(total_minutes * deep_pct / 100)) if total_minutes else 0
        minor_minutes = max(total_minutes - deep_minutes, 0)

        tasks_list = []
        minutes_by_task = {}
        for row in sessions_filtered:
            t_id = row["task_id"]
            t_title = row["task_title"] or "Focus Session"
            mins = int(row["duration_min"] or 0)
            key = (t_id, t_title)
            minutes_by_task[key] = minutes_by_task.get(key, 0) + mins

        completed_map = {row["id"]: row for row in tasks_filtered if row["is_completed"]}
        for (t_id, t_title), mins in minutes_by_task.items():
            is_done = t_id in completed_map if t_id is not None else False
            completed_at = completed_map[t_id]["completed_at"] if is_done else None
            tasks_list.append({
                "title": t_title,
                "minutes": mins,
                "done": is_done,
                "completed_at": completed_at
            })

        for row in tasks_filtered:
            key = (row["id"], row["title"])
            if key not in minutes_by_task:
                tasks_list.append({
                    "title": row["title"],
                    "minutes": 0,
                    "done": True,
                    "completed_at": row["completed_at"]
                })

        def _task_sort_key(item):
            done_rank = 1 if item.get("done") else 0
            completed_dt = self._parse_dt(item.get("completed_at")) if item.get("done") else None
            completed_ts = completed_dt.timestamp() if completed_dt else 0
            return (done_rank, completed_ts, item.get("minutes", 0))

        if tasks_list:
            tasks_list.sort(key=_task_sort_key, reverse=True)

        total_tasks_count = len(tasks_list)
        self.summary_cards[0]["value"].setText(f"{total_minutes}m")
        self.summary_cards[1]["value"].setText(f"{efficiency}%")
        self.summary_cards[2]["value"].setText(str(total_tasks_count))

        focus_baseline = 45
        focus_delta = int(round(((total_minutes - focus_baseline) / max(focus_baseline, 1)) * 100)) if total_minutes else 0
        focus_prefix = "+" if focus_delta >= 0 else ""
        self.summary_cards[0]["delta"].setText(f"{focus_prefix}{focus_delta}%")

        eff_baseline = 75
        eff_delta = int(round(((efficiency - eff_baseline) / max(eff_baseline, 1)) * 100)) if efficiency else 0
        eff_prefix = "+" if eff_delta >= 0 else ""
        self.summary_cards[1]["delta"].setText(f"{eff_prefix}{eff_delta}%")

        tasks_baseline = 3
        tasks_delta = int(round(((total_tasks_count - tasks_baseline) / max(tasks_baseline, 1)) * 100))
        tasks_prefix = "+" if tasks_delta >= 0 else ""
        self.summary_cards[2]["delta"].setText(f"{tasks_prefix}{tasks_delta}%")

        self.ring.set_data(deep_pct, "Deep")
        self.deep_row.setText("Deep Focus")
        self.deep_value.setText(f"{deep_minutes} min")
        self.minor_row.setText("Minor Distractions")
        self.minor_value.setText(f"{minor_minutes} min")
        if total_minutes > 0:
            peak_min = int(round((summary["peak_idx"] / max(len(timeline_values) - 1, 1)) * total_minutes))
            self.breakdown_note.setText(f"Peak focus around {peak_min} min into the session.")
        else:
            self.breakdown_note.setText("No timing data available for this session.")

        self.timeline_chart.set_data(timeline_values)
        self.timeline_start.setText("0m")
        mid = max(1, total_minutes // 2)
        self.timeline_mid.setText(f"{mid}m")
        self.timeline_end.setText(f"{total_minutes}m")

        while self.tasks_layout.count():
            item = self.tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tasks_list:
            tasks_list = []

        for task_item in tasks_list:
            row = QFrame()
            row.setObjectName("ReportTaskRow")
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(10)

            title = QLabel(task_item["title"])
            subtitle = QLabel(f"{task_item['minutes']} mins spent")
            title.setStyleSheet(f"color: {self.colors['text']}; font-size: 12px; font-weight: 700;")
            subtitle.setStyleSheet(f"color: {self.colors['sub']}; font-size: 10px; font-weight: 600;")
            text_col = QVBoxLayout()
            text_col.setSpacing(4)
            text_col.addWidget(title)
            text_col.addWidget(subtitle)

            status = QLabel("DONE" if task_item["done"] else "PARTIAL")
            status_color = "#34d399" if task_item["done"] else self.colors["primary"]
            status.setStyleSheet(
                f"color: {status_color}; background: rgba(17, 164, 212, 0.12); font-size: 9px; font-weight: 800; padding: 4px 8px; border-radius: 10px;"
            )

            row_layout.addLayout(text_col)
            row_layout.addStretch()
            row_layout.addWidget(status)
            row.setStyleSheet(
                f"QFrame#ReportTaskRow {{ background: {self.colors['card']}; border: 1px solid {self.colors['primary_soft_border']}; border-radius: 12px; }}"
            )
            self.tasks_layout.addWidget(row)

