from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from datetime import datetime, timedelta
import random
import zlib
from database.db_manager import get_db_connection


class EnergyTrendWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.values = [0.7, 0.85, 0.95, 1.0, 0.9, 0.55, 0.7, 0.92, 0.88, 0.6]
        self.colors = {}
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_theme(self, colors):
        self.colors = colors or {}
        self.update()

    def set_data(self, values):
        if values:
            self.values = list(values)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        left_pad = 6
        right_pad = 6
        top_pad = 6
        bottom_pad = 10
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
        step = chart_rect.width() / max(count - 1, 1)
        points = []
        for idx, value in enumerate(values):
            x = chart_rect.left() + idx * step
            y = chart_rect.bottom() - (max(0.0, min(value, 1.0)) * chart_rect.height())
            points.append(QPointF(x, y))

        path = QPainterPath()
        path.moveTo(points[0])
        for pt in points[1:]:
            path.lineTo(pt)

        fill_path = QPainterPath(path)
        fill_path.lineTo(chart_rect.right(), chart_rect.bottom())
        fill_path.lineTo(chart_rect.left(), chart_rect.bottom())
        fill_path.closeSubpath()

        primary = QColor(self.colors.get("primary", "#11a4d4"))
        fill = QColor(primary)
        fill.setAlpha(60)
        painter.fillPath(fill_path, fill)

        pen = QPen(primary, 2.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)


class QuickStatsPage(QWidget):
    request_history = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_theme = "Light"
        self.colors = {}
        self.setObjectName("QuickStatsPage")

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
        self.header.setObjectName("QuickHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(6, 6, 6, 6)
        header_layout.setSpacing(10)

        self.back_btn = QPushButton("<")
        self.back_btn.setObjectName("QuickBackButton")
        self.back_btn.setFixedSize(36, 36)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.request_history.emit)

        self.header_title = QLabel("Quick Stats")
        self.header_title.setObjectName("QuickTitle")

        header_layout.addWidget(self.back_btn)
        header_layout.addStretch()
        header_layout.addWidget(self.header_title)
        header_layout.addStretch()
        self.content.addWidget(self.header)

        # Title block
        self.kicker = QLabel("Quick Stats")
        self.kicker.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.session_title = QLabel("Session")
        self.session_subtitle = QLabel("Session details")
        self.content.addWidget(self.kicker)
        self.content.addWidget(self.session_title)
        self.content.addWidget(self.session_subtitle)

        # Metrics grid
        self.metrics_container = QWidget()
        self.metrics_grid = QGridLayout(self.metrics_container)
        self.metrics_grid.setHorizontalSpacing(10)
        self.metrics_grid.setVerticalSpacing(10)
        self.metric_cards = []
        for idx, title in enumerate(("Focus Score", "Efficiency", "Distractions", "Energy")):
            card = QFrame()
            card.setObjectName("QuickMetricCard")
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
            row = idx // 2
            col = idx % 2
            self.metrics_grid.addWidget(card, row, col)
            self.metric_cards.append({
                "card": card,
                "title": title_lbl,
                "value": value_lbl,
                "delta": delta_lbl
            })
        self.content.addWidget(self.metrics_container)

        # Energy trend
        self.energy_title = QLabel("Energy Trend")
        self.energy_sub = QLabel("Based on focus peaks")
        self.content.addWidget(self.energy_title)
        self.content.addWidget(self.energy_sub)
        self.energy_chart = EnergyTrendWidget()
        self.content.addWidget(self.energy_chart)

        self.trend_labels = QHBoxLayout()
        self.trend_start = QLabel("Start")
        self.trend_mid1 = QLabel("15m")
        self.trend_mid2 = QLabel("30m")
        self.trend_end = QLabel("End")
        self.trend_labels.addWidget(self.trend_start)
        self.trend_labels.addStretch()
        self.trend_labels.addWidget(self.trend_mid1)
        self.trend_labels.addStretch()
        self.trend_labels.addWidget(self.trend_mid2)
        self.trend_labels.addStretch()
        self.trend_labels.addWidget(self.trend_end)
        self.content.addLayout(self.trend_labels)

        # Details
        self.details_container = QWidget()
        self.details_layout = QVBoxLayout(self.details_container)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(0)
        self.detail_rows = []
        for title in ("Start Time", "Duration", "Task Type"):
            row = QFrame()
            row.setObjectName("QuickDetailRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 8, 6, 8)
            row_layout.setSpacing(8)
            left = QLabel(title)
            right = QLabel("--")
            row_layout.addWidget(left)
            row_layout.addStretch()
            row_layout.addWidget(right)
            self.details_layout.addWidget(row)
            self.detail_rows.append({
                "row": row,
                "left": left,
                "right": right
            })
        self.content.addWidget(self.details_container)

        # Done button
        self.done_btn = QPushButton("Done")
        self.done_btn.setObjectName("QuickDoneButton")
        self.done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_btn.clicked.connect(self.request_history.emit)
        self.content.addWidget(self.done_btn)

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
        self.setStyleSheet(f"QWidget#QuickStatsPage {{ background: {c['bg']}; }}")
        self.header.setStyleSheet(
            f"QFrame#QuickHeader {{ background: {c['bg']}; border-bottom: 1px solid {c['primary_soft_border']}; }}"
        )
        self.back_btn.setStyleSheet(
            f"QPushButton#QuickBackButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 18px; color: {c['text']}; font-weight: 700; }}"
        )
        self.header_title.setStyleSheet(
            f"color: {c['text']}; font-size: 16px; font-weight: 800;"
        )
        self.kicker.setStyleSheet(
            f"color: {c['primary']}; font-size: 10px; font-weight: 900; text-transform: uppercase;"
        )
        self.session_title.setStyleSheet(
            f"color: {c['text']}; font-size: 18px; font-weight: 900;"
        )
        self.session_subtitle.setStyleSheet(
            f"color: {c['sub']}; font-size: 11px; font-weight: 600;"
        )

        for item in self.metric_cards:
            item["card"].setStyleSheet(
                f"QFrame#QuickMetricCard {{ background: {c['primary_soft']}; border: 1px solid {c['primary_soft_border']}; border-radius: 12px; }}"
            )
            item["title"].setStyleSheet(
                f"color: {c['sub']}; font-size: 9px; font-weight: 700; text-transform: uppercase;"
            )
            item["value"].setStyleSheet(
                f"color: {c['text']}; font-size: 18px; font-weight: 900;"
            )
            item["delta"].setStyleSheet(
                f"color: {c['good']}; font-size: 9px; font-weight: 700;"
            )

        self.energy_title.setStyleSheet(
            f"color: {c['text']}; font-size: 14px; font-weight: 800;"
        )
        self.energy_sub.setStyleSheet(
            f"color: {c['sub']}; font-size: 10px; font-weight: 600;"
        )
        for lbl in (self.trend_start, self.trend_mid1, self.trend_mid2, self.trend_end):
            lbl.setStyleSheet(
                f"color: {c['sub']}; font-size: 9px; font-weight: 800; text-transform: uppercase;"
            )

        for item in self.detail_rows:
            item["row"].setStyleSheet(
                f"QFrame#QuickDetailRow {{ border-bottom: 1px solid {c['primary_soft_border']}; }}"
            )
            item["left"].setStyleSheet(
                f"color: {c['sub']}; font-size: 10px; font-weight: 700;"
            )
            item["right"].setStyleSheet(
                f"color: {c['text']}; font-size: 10px; font-weight: 700;"
            )

        self.done_btn.setStyleSheet(
            f"QPushButton#QuickDoneButton {{ background: {c['primary']}; color: white; border: none; border-radius: 12px; padding: 10px; font-size: 12px; font-weight: 900; }}"
        )
        self.energy_chart.set_theme(c)

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

    def _seed_from(self, activity_id, dt_start, duration):
        raw = f"{activity_id}|{dt_start.isoformat() if dt_start else ''}|{duration}"
        return zlib.adler32(raw.encode("utf-8"))

    def _generate_energy_series(self, duration, seed):
        if duration <= 0:
            return [0.6, 0.72, 0.84, 0.9, 0.85, 0.7, 0.76, 0.88, 0.82, 0.65]
        count = 10 if duration <= 60 else 12
        rnd = random.Random(seed)
        base = 0.55 + min(duration, 120) / 220
        trend = rnd.uniform(-0.12, 0.12)
        values = []
        for idx in range(count):
            t = idx / max(count - 1, 1)
            drift = (t - 0.5) * trend * 2
            noise = rnd.uniform(-0.08, 0.08)
            dip = -0.06 if (0.35 < t < 0.55 and rnd.random() < 0.5) else 0
            val = base + drift + noise + dip
            values.append(max(0.35, min(1.0, val)))
        return values

    def _summarize_series(self, values):
        if not values:
            return {"avg": 0, "min": 0, "max": 0, "variability": 0}
        avg = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)
        return {
            "avg": avg,
            "min": min_val,
            "max": max_val,
            "variability": (max_val - min_val)
        }

    def _calc_efficiency(self, summary):
        avg = summary["avg"] * 100
        variability = summary["variability"] * 100
        score = avg - variability * 0.25 + 8
        return int(max(50, min(99, score)))

    def _calc_focus_score(self, summary):
        avg = summary["avg"]
        return min(9.9, max(3.5, avg * 9.5))

    def load_activity(self, activity_id):
        if not activity_id:
            return

        conn = get_db_connection()
        session = None
        task = None

        if activity_id.startswith("session:"):
            try:
                session_id = int(activity_id.split(":", 1)[1])
            except Exception:
                session_id = None
            if session_id is not None:
                session = conn.execute(
                    "SELECT id, task_id, task_title, started_at, ended_at, duration_min, status FROM pomodoro_sessions WHERE id = ?",
                    (session_id,)
                ).fetchone()
                if session and session["task_id"]:
                    task = conn.execute(
                        "SELECT id, title, is_completed, completed_at FROM tasks WHERE id = ?",
                        (session["task_id"],)
                    ).fetchone()
        elif activity_id.startswith("task:"):
            try:
                task_id = int(activity_id.split(":", 1)[1])
            except Exception:
                task_id = None
            if task_id is not None:
                task = conn.execute(
                    "SELECT id, title, is_completed, completed_at FROM tasks WHERE id = ?",
                    (task_id,)
                ).fetchone()
                session = conn.execute(
                    "SELECT id, task_id, task_title, started_at, ended_at, duration_min, status FROM pomodoro_sessions WHERE task_id = ? ORDER BY started_at DESC",
                    (task_id,)
                ).fetchone()

        conn.close()

        if session:
            dt_start = self._parse_dt(session["started_at"])
            duration = int(session["duration_min"] or 0)
            if session["ended_at"]:
                dt_end = self._parse_dt(session["ended_at"])
            else:
                dt_end = dt_start + timedelta(minutes=duration) if dt_start else None
            title = session["task_title"] or (task["title"] if task else "Focus Session")
            status = "Focus Session"
        elif task:
            dt_start = self._parse_dt(task["completed_at"])
            duration = 0
            dt_end = None
            title = task["title"]
            status = "Completed"
        else:
            dt_start = datetime.now()
            duration = 0
            dt_end = None
            title = "Session"
            status = "Session"

        date_label = dt_start.strftime("%b %d") if dt_start else "Recent"
        self.session_title.setText(title)
        self.session_subtitle.setText(f"{status} - {date_label}")

        seed = self._seed_from(activity_id, dt_start, duration)
        energy_values = self._generate_energy_series(duration, seed)
        summary = self._summarize_series(energy_values)
        focus_score = self._calc_focus_score(summary)
        efficiency = self._calc_efficiency(summary)
        distractions = max(0, min(6, int(round(summary["variability"] * 20)))) if duration else 0
        energy_text = "Stable" if summary["variability"] < 0.2 else "Variable"

        focus_delta = "+5%" if focus_score >= 7.5 else "-3%" if focus_score <= 5.5 else "+1%"
        eff_delta = "+4%" if efficiency >= 85 else "-3%" if efficiency <= 70 else "+1%"
        distraction_note = "No impact" if distractions <= 1 else "Minor impact"
        energy_note = "Constant" if energy_text == "Stable" else "Fluctuating"

        metrics = [
            (f"{focus_score:.1f}/10", focus_delta),
            (f"{efficiency}%", eff_delta),
            (f"{distractions} minor", distraction_note),
            (energy_text, energy_note)
        ]
        for idx, item in enumerate(self.metric_cards):
            value, delta = metrics[idx]
            item["value"].setText(value)
            item["delta"].setText(delta)

        start_time = dt_start.strftime("%I:%M %p").lstrip("0") if dt_start else "--"
        duration_text = f"{duration} mins" if duration else "--"
        task_type = "Deep Work" if status == "Focus Session" else "Completed"
        self.detail_rows[0]["right"].setText(start_time)
        self.detail_rows[1]["right"].setText(duration_text)
        self.detail_rows[2]["right"].setText(task_type)

        self.energy_chart.set_data(energy_values)
        self.trend_start.setText("Start")
        self.trend_mid1.setText("")
        self.trend_mid2.setText("")
        if duration > 0:
            if duration == 1:
                mid1 = None
                mid2 = None
            elif duration == 2:
                mid1 = 1
                mid2 = None
            else:
                mid1 = max(1, duration // 3)
                mid2 = max(mid1 + 1, (duration * 2) // 3)
                if mid2 >= duration:
                    mid2 = duration - 1
                if mid1 >= mid2:
                    mid1 = max(1, mid2 - 1)

            if mid1:
                self.trend_mid1.setText(f"{mid1} min")
            if mid2:
                self.trend_mid2.setText(f"{mid2} min")
            self.trend_end.setText(f"{duration} min")
        else:
            self.trend_end.setText("End")
