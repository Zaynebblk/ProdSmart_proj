from datetime import datetime, timedelta
from math import ceil

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QProgressBar,
    QSizePolicy,
    QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QLinearGradient, QColor
from database.db_manager import get_db_connection


def _heatmap_time_labels_2h():
    labels = []
    for hour in range(0, 24, 2):
        end = hour + 2
        end_label = "24:00" if end == 24 else f"{end:02d}:00"
        labels.append(f"{hour:02d}:00-{end_label}")
    return labels


class FocusConsistencyChart(QFrame):
    def __init__(self):
        super().__init__()
        self.values = [0.2] * 7
        self.labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.colors = {}
        self.is_dark = False
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, values, labels=None):
        if values:
            padded = list(values) + [0.0] * (7 - len(values))
            self.values = padded[:7]
        if labels:
            padded = list(labels) + [""] * (7 - len(labels))
            self.labels = padded[:7]
        self.update()

    def set_theme(self, colors, theme):
        self.colors = colors or {}
        self.is_dark = theme == "Dark"
        self.update()

    def paintEvent(self, event):
        if not self.values:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        left_pad = 12
        right_pad = 12
        top_pad = 12
        bottom_pad = 28
        chart_rect = QRectF(
            rect.left() + left_pad,
            rect.top() + top_pad,
            rect.width() - left_pad - right_pad,
            rect.height() - top_pad - bottom_pad
        )

        values = list(self.values)
        max_val = max(values) if values else 1
        if max_val <= 0:
            max_val = 1
        if max_val > 1:
            values = [v / max_val for v in values]

        points = []
        span = 6 if len(values) > 1 else 1
        for idx, value in enumerate(values):
            x = chart_rect.left() + (chart_rect.width() / span) * idx
            y = chart_rect.bottom() - (value * chart_rect.height())
            points.append(QPointF(x, y))

        path = QPainterPath()
        path.moveTo(points[0])
        for i in range(1, len(points)):
            path.lineTo(points[i])

        fill_path = QPainterPath(path)
        fill_path.lineTo(chart_rect.right(), chart_rect.bottom())
        fill_path.lineTo(chart_rect.left(), chart_rect.bottom())
        fill_path.closeSubpath()

        line_color = QColor(self.colors.get("accent", "#38BDF8"))
        gradient = QLinearGradient(chart_rect.topLeft(), chart_rect.bottomLeft())
        gradient.setColorAt(0, QColor(line_color.red(), line_color.green(), line_color.blue(), 110))
        gradient.setColorAt(1, QColor(line_color.red(), line_color.green(), line_color.blue(), 0))

        painter.fillPath(fill_path, gradient)

        pen = QPen(line_color, 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

        # Markers per day (to show exact zeros)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(line_color)
        for pt in points:
            painter.drawEllipse(pt, 4, 4)

        label_color = QColor(self.colors.get("sub", "#94A3B8"))
        painter.setPen(label_color)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        for idx, label in enumerate(self.labels):
            if not label:
                continue
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label)
            x = points[idx].x() - text_width / 2
            y = rect.bottom() - 6
            painter.drawText(QPointF(x, y), label)


class HeatmapWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.values = [[0] * 12 for _ in range(3)]
        self.day_labels = ["M", "T", "W"]
        self.time_labels = _heatmap_time_labels_2h()
        self.colors = {}
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, values, day_labels=None, time_labels=None):
        if values:
            self.values = values
        if day_labels:
            self.day_labels = list(day_labels)
        if time_labels:
            self.time_labels = list(time_labels)
        self.update()

    def set_theme(self, colors, theme):
        self.colors = colors or {}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rows = len(self.values)
        cols = len(self.values[0]) if rows else 0
        if rows == 0 or cols == 0:
            return

        rect = QRectF(self.rect())
        right_pad = 16
        top_pad = 24
        bottom_pad = 34
        legend_height = 18

        label_color = QColor(self.colors.get("sub", "#94A3B8"))
        label_font = painter.font()
        label_font.setPointSize(9)
        label_font.setBold(True)

        day_font = painter.font()
        day_font.setPointSize(10)
        day_font.setBold(True)

        painter.setFont(day_font)
        metrics = painter.fontMetrics()
        max_day_label_w = max(
            (metrics.horizontalAdvance(label) for label in self.day_labels[:rows] if label),
            default=0
        )
        label_gap = 10
        left_pad = max(28, max_day_label_w + label_gap + 2)

        grid_rect = QRectF(
            rect.left() + left_pad,
            rect.top() + top_pad,
            rect.width() - left_pad - right_pad,
            rect.height() - top_pad - bottom_pad
        )

        gap = 8
        cell_w = (grid_rect.width() - gap * (cols - 1)) / cols
        cell_h = (grid_rect.height() - gap * (rows - 1)) / rows

        painter.setPen(label_color)
        painter.setFont(label_font)

        # Time labels
        for c, label in enumerate(self.time_labels[:cols]):
            text_width = painter.fontMetrics().horizontalAdvance(label)
            x = grid_rect.left() + c * (cell_w + gap) + (cell_w - text_width) / 2
            y = rect.top() + 16
            painter.drawText(QPointF(x, y), label)

        # Day labels
        day_label_color = QColor(self.colors.get("text", "#0B132B"))
        painter.setPen(day_label_color)
        painter.setFont(day_font)
        for r, label in enumerate(self.day_labels[:rows]):
            label_rect = QRectF(
                rect.left(),
                grid_rect.top() + r * (cell_h + gap),
                left_pad - label_gap,
                cell_h
            )
            painter.drawText(
                label_rect,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                label
            )

        heat_colors = [
            QColor(self.colors.get("heat0", "#1F2937")),
            QColor(self.colors.get("heat1", "#0B4A6E")),
            QColor(self.colors.get("heat2", "#0284C7")),
            QColor(self.colors.get("heat3", "#38BDF8")),
        ]

        for r in range(rows):
            for c in range(cols):
                value = self.values[r][c]
                color = heat_colors[max(0, min(value, 3))]
                x = grid_rect.left() + c * (cell_w + gap)
                y = grid_rect.top() + r * (cell_h + gap)
                cell_rect = QRectF(x, y, cell_w, cell_h)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(cell_rect, 6, 6)

        # Legend
        legend_y = rect.bottom() - legend_height
        painter.setPen(label_color)
        painter.drawText(QPointF(rect.left() + left_pad - 12, legend_y + 12), "Less productive")

        legend_x = rect.left() + left_pad + 120
        box_size = 12
        for idx, color in enumerate(heat_colors):
            box_rect = QRectF(legend_x + idx * (box_size + 6), legend_y, box_size, box_size)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(box_rect, 3, 3)

        painter.setPen(label_color)
        painter.drawText(QPointF(legend_x + len(heat_colors) * (box_size + 6) + 8, legend_y + 12), "Peak Flow")


class VelocityChartWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.counts = [0] * 7
        self.capacity = [0] * 7
        self.labels = ["M", "T", "W", "T", "F", "S", "S"]
        self.point_value = 0
        self.point_index = 3
        self.colors = {}
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, counts, capacity, labels=None, point_value=0, point_index=3):
        if counts:
            self.counts = list(counts) + [0] * (7 - len(counts))
            self.counts = self.counts[:7]
        if capacity:
            self.capacity = list(capacity) + [0] * (7 - len(capacity))
            self.capacity = self.capacity[:7]
        if labels:
            self.labels = list(labels) + [""] * (7 - len(labels))
            self.labels = self.labels[:7]
        self.point_value = point_value
        self.point_index = max(0, min(point_index, 6))
        self.update()

    def set_theme(self, colors, theme):
        self.colors = colors or {}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        left_pad = 20
        right_pad = 16
        top_pad = 18
        bottom_pad = 34
        chart_rect = QRectF(
            rect.left() + left_pad,
            rect.top() + top_pad,
            rect.width() - left_pad - right_pad,
            rect.height() - top_pad - bottom_pad
        )

        max_val = max(max(self.counts), max(self.capacity), self.point_value, 1)

        grid_color = QColor(self.colors.get("chart_grid", "#1F2937"))
        painter.setPen(QPen(grid_color, 1))
        for i in range(3):
            y = chart_rect.top() + (chart_rect.height() / 2) * i
            painter.drawLine(QPointF(chart_rect.left(), y), QPointF(chart_rect.right(), y))

        def to_point(idx, value):
            x = chart_rect.left() + (chart_rect.width() / 6) * idx
            y = chart_rect.bottom() - (value / max_val) * chart_rect.height()
            return QPointF(x, y)

        capacity_color = QColor(self.colors.get("capacity", "#A855F7"))
        cap_pen = QPen(capacity_color, 3, Qt.PenStyle.DotLine)
        cap_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(cap_pen)

        cap_path = QPainterPath()
        cap_points = [to_point(i, v) for i, v in enumerate(self.capacity)]
        cap_path.moveTo(cap_points[0])
        for i in range(1, len(cap_points)):
            cap_path.lineTo(cap_points[i])
        painter.drawPath(cap_path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(capacity_color)
        for pt in cap_points:
            painter.drawEllipse(pt, 4, 4)

        point_color = QColor(self.colors.get("accent", "#38BDF8"))
        point_y = chart_rect.bottom() - (self.point_value / max_val) * chart_rect.height() if max_val else chart_rect.bottom()
        painter.setPen(QPen(point_color, 2))
        painter.drawLine(QPointF(chart_rect.left(), point_y), QPointF(chart_rect.right(), point_y))

        marker = QPointF(
            chart_rect.left() + (chart_rect.width() / 6) * self.point_index,
            point_y
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(point_color)
        painter.drawEllipse(marker, 5, 5)

        painter.setPen(point_color)
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QPointF(marker.x() - 6, point_y - 8), f"{self.point_value}")

        label_color = QColor(self.colors.get("sub", "#94A3B8"))
        painter.setPen(label_color)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        for idx, label in enumerate(self.labels):
            text_width = painter.fontMetrics().horizontalAdvance(label)
            x = chart_rect.left() + (chart_rect.width() / 6) * idx - text_width / 2
            y = rect.bottom() - 6
            painter.drawText(QPointF(x, y), label)

class PomodoroBarChart(QFrame):
    def __init__(self):
        super().__init__()
        self.values = [0] * 7
        self.labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.colors = {}
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, values, labels=None):
        if values:
            padded = list(values) + [0] * (7 - len(values))
            self.values = padded[:7]
        if labels:
            padded = list(labels) + [""] * (7 - len(labels))
            self.labels = padded[:7]
        self.update()

    def set_theme(self, colors, theme):
        self.colors = colors or {}
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        left_pad = 16
        right_pad = 16
        top_pad = 12
        bottom_pad = 26
        chart_rect = QRectF(
            rect.left() + left_pad,
            rect.top() + top_pad,
            rect.width() - left_pad - right_pad,
            rect.height() - top_pad - bottom_pad
        )

        values = list(self.values)
        max_val = max(values) if values else 1
        if max_val <= 0:
            max_val = 1

        bar_count = len(values)
        gap = 8
        bar_w = (chart_rect.width() - gap * (bar_count - 1)) / bar_count

        accent = QColor(self.colors.get("accent", "#38BDF8"))
        accent2 = QColor(self.colors.get("accent2", "#22D3EE"))
        grid = QColor(self.colors.get("chart_grid", "#1F2937"))

        painter.setPen(QPen(grid, 1))
        for i in range(1, 3):
            y = chart_rect.top() + (chart_rect.height() / 3) * i
            painter.drawLine(QPointF(chart_rect.left(), y), QPointF(chart_rect.right(), y))

        for idx, value in enumerate(values):
            x = chart_rect.left() + idx * (bar_w + gap)
            h = (value / max_val) * chart_rect.height()
            y = chart_rect.bottom() - h
            gradient = QLinearGradient(QPointF(x, y), QPointF(x, chart_rect.bottom()))
            gradient.setColorAt(0, accent2)
            gradient.setColorAt(1, accent)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w, h), 6, 6)

        label_color = QColor(self.colors.get("sub", "#94A3B8"))
        painter.setPen(label_color)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        for idx, label in enumerate(self.labels):
            if not label:
                continue
            text_width = painter.fontMetrics().horizontalAdvance(label)
            x = chart_rect.left() + idx * (bar_w + gap) + (bar_w - text_width) / 2
            y = rect.bottom() - 6
            painter.drawText(QPointF(x, y), label)

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_theme = "Light"
        self.cards = []
        self.section_titles = []
        self.labels_main = []
        self.labels_sub = []
        self.badges = []
        self.progress_bars = []
        self.energy_bars = []
        self.consistency_chart = None
        self.heatmap_chart = None
        self.velocity_chart = None
        self.consistency_labels_data = []
        self.heatmap_day_labels_data = []
        self.heatmap_time_labels_data = []
        self.velocity_day_labels_data = []
        self.refresh_button = None
        self.schedule_button = None
        self.header_status = None
        self._colors = {}
        self.pomo_minutes_week = 0
        self.pomo_sessions_week = 0
        self.pomo_minutes_total = 0
        self.pomo_sessions_total = 0
        self.pomo_avg_minutes = 0
        self.pomo_best_day_label = "-"
        self.pomo_best_day_minutes = 0
        self.pomo_day_minutes = [0, 0, 0, 0, 0, 0, 0]
        self.pomo_day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        self.setObjectName("DashboardPage")
        self._set_default_metrics()
        self._build_ui()
        self.update_theme("Light")
        self._load_metrics_from_db()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self.content = QVBoxLayout(container)
        self.content.setContentsMargins(32, 24, 32, 24)
        self.content.setSpacing(18)

        self.scroll.setWidget(container)
        root.addWidget(self.scroll)

        # Header
        header = QFrame()
        header.setObjectName("DashHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(12)

        header_left = QVBoxLayout()
        header_left.setSpacing(6)

        self.kicker = QLabel("AI DASHBOARD")
        self.title = QLabel("Focus Overview")
        self.subtitle = QLabel("Weekly insights to keep you in flow")

        self.kicker.setObjectName("DashKicker")
        self.title.setObjectName("DashTitle")
        self.subtitle.setObjectName("DashSubtitle")

        header_left.addWidget(self.kicker)
        header_left.addWidget(self.title)
        header_left.addWidget(self.subtitle)

        header_layout.addLayout(header_left)
        header_layout.addStretch()

        self.header_chip = QLabel("Live")
        self.header_chip.setObjectName("DashChip")
        self.header_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_chip.setFixedSize(60, 26)
        self.header_chip.setProperty("state", "live")
        self.header_status = QLabel("Updated just now")
        self.header_status.setObjectName("DashStatus")

        header_right = QVBoxLayout()
        header_right.setSpacing(6)
        header_right.addWidget(self.header_chip, alignment=Qt.AlignmentFlag.AlignRight)
        header_right.addWidget(self.header_status, alignment=Qt.AlignmentFlag.AlignRight)
        header_layout.addLayout(header_right)

        self.content.addWidget(header)

        # Top cards
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        focus_card = self._make_card("Focus Score")
        focus_layout = focus_card.layout()
        focus_layout.setSpacing(8)

        self.focus_score = QLabel("82")
        self.focus_score.setObjectName("DashScore")
        self.labels_main.append(self.focus_score)

        self.focus_delta = QLabel("+5% vs last week")
        self.focus_delta.setObjectName("DashDelta")
        self.labels_sub.append(self.focus_delta)

        self.focus_bar = QProgressBar()
        self.focus_bar.setRange(0, 100)
        self.focus_bar.setValue(82)
        self.focus_bar.setTextVisible(False)
        self.focus_bar.setFixedHeight(10)
        self.progress_bars.append(self.focus_bar)

        focus_layout.addWidget(self.focus_score)
        focus_layout.addWidget(self.focus_bar)
        focus_layout.addWidget(self.focus_delta)
        focus_layout.addStretch()

        energy_card = self._make_card("Energy Level")
        energy_layout = energy_card.layout()
        energy_layout.setSpacing(10)

        bars_row = QHBoxLayout()
        bars_row.setSpacing(6)
        bar_heights = [12, 20, 28, 22, 14]
        for h in bar_heights:
            bar = QFrame()
            bar.setFixedSize(10, h)
            bar.setObjectName("DashEnergyBar")
            bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.energy_bars.append(bar)
            bars_row.addWidget(bar, alignment=Qt.AlignmentFlag.AlignBottom)
        bars_row.addStretch()

        self.energy_label = QLabel("Peak")
        self.energy_label.setObjectName("DashEnergy")
        self.labels_main.append(self.energy_label)

        self.energy_note = QLabel("Next drop: 3:00 PM")
        self.labels_sub.append(self.energy_note)

        energy_layout.addLayout(bars_row)
        energy_layout.addWidget(self.energy_label)
        energy_layout.addWidget(self.energy_note)
        energy_layout.addStretch()

        pomodoro_card = self._make_card("Pomodoro")
        pomodoro_layout = pomodoro_card.layout()
        pomodoro_layout.setSpacing(8)

        self.pomo_minutes_label = QLabel("0 min")
        self.pomo_minutes_label.setObjectName("DashScore")
        self.labels_main.append(self.pomo_minutes_label)

        self.pomo_sessions_label = QLabel("0 sessions this week")
        self.labels_sub.append(self.pomo_sessions_label)

        pomodoro_layout.addWidget(self.pomo_minutes_label)
        pomodoro_layout.addWidget(self.pomo_sessions_label)
        self.pomo_avg_label = QLabel("Avg session: 0 min")
        self.labels_sub.append(self.pomo_avg_label)
        pomodoro_layout.addWidget(self.pomo_avg_label)

        self.pomo_best_label = QLabel("Best day: -")
        self.labels_sub.append(self.pomo_best_label)
        pomodoro_layout.addWidget(self.pomo_best_label)
        pomodoro_layout.addStretch()

        top_row.addWidget(focus_card)
        top_row.addWidget(energy_card)
        top_row.addWidget(pomodoro_card)
        self.content.addLayout(top_row)

        # AI Insights
        ai_header = self._section_header("AI Insights")
        self.content.addLayout(ai_header)

        primary = QFrame()
        primary.setObjectName("DashPrimary")
        primary.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        primary_layout = QVBoxLayout(primary)
        primary_layout.setContentsMargins(20, 18, 20, 18)
        primary_layout.setSpacing(10)

        badge = QLabel("Recommended")
        badge.setObjectName("DashBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(110, 24)
        self.badges.append(badge)

        title = QLabel("Best time for deep work")
        title.setObjectName("DashCardTitle")
        self.labels_main.append(title)

        desc = QLabel(
            "High focus window starting at 10:30 AM. Block 90 minutes for design work."
        )
        desc.setWordWrap(True)
        self.labels_sub.append(desc)

        btn = QPushButton("Schedule Deep Work")
        btn.setObjectName("DashAction")
        btn.clicked.connect(self._on_schedule_clicked)
        self.schedule_button = btn

        primary_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)
        primary_layout.addWidget(title)
        primary_layout.addWidget(desc)
        primary_layout.addStretch()
        primary_layout.addWidget(btn)

        secondary = QFrame()
        secondary.setObjectName("DashSecondary")
        secondary.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        secondary_layout = QHBoxLayout(secondary)
        secondary_layout.setContentsMargins(16, 14, 16, 14)
        secondary_layout.setSpacing(12)

        icon = QFrame()
        icon.setFixedSize(40, 40)
        icon.setObjectName("DashIcon")
        icon.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        sec_text = QVBoxLayout()
        sec_title = QLabel("Low energy task")
        sec_title.setObjectName("DashCardTitle")
        self.labels_main.append(sec_title)
        sec_desc = QLabel("Save inbox cleanup for 4:00 PM when energy dips.")
        sec_desc.setWordWrap(True)
        self.labels_sub.append(sec_desc)
        sec_text.addWidget(sec_title)
        sec_text.addWidget(sec_desc)

        secondary_layout.addWidget(icon)
        secondary_layout.addLayout(sec_text)
        secondary_layout.addStretch()

        self.content.addWidget(primary)
        self.content.addWidget(secondary)

        # Weekly Predictions
        weekly_header = self._section_header("Weekly Predictions")
        self.content.addLayout(weekly_header)

        completion = self._make_card("Estimated Project Completion")
        completion_layout = completion.layout()
        completion_layout.setSpacing(8)

        completion_row = QHBoxLayout()
        self.completion_label = QLabel("Fri, Oct 27")
        self.completion_label.setObjectName("DashAccent")
        self.labels_main.append(self.completion_label)
        completion_row.addWidget(self.completion_label)
        completion_row.addStretch()

        self.completion_bar = QProgressBar()
        self.completion_bar.setRange(0, 100)
        self.completion_bar.setValue(65)
        self.completion_bar.setTextVisible(False)
        self.completion_bar.setFixedHeight(10)
        self.progress_bars.append(self.completion_bar)

        self.completion_note = QLabel("65% predicted progress")
        self.labels_sub.append(self.completion_note)

        completion_layout.addLayout(completion_row)
        completion_layout.addWidget(self.completion_bar)
        completion_layout.addWidget(self.completion_note)

        consistency = self._make_card("Focus Consistency")
        consistency_layout = consistency.layout()
        consistency_layout.setSpacing(10)

        self.consistency_chart = FocusConsistencyChart()
        consistency_layout.addWidget(self.consistency_chart)

        heatmap = self._make_card("Productivity Heatmap")
        heatmap_layout = heatmap.layout()
        heatmap_layout.setSpacing(10)

        self.heatmap_chart = HeatmapWidget()
        heatmap_layout.addWidget(self.heatmap_chart)

        velocity = self._make_card("Predicted Velocity")
        velocity_layout = velocity.layout()
        velocity_layout.setSpacing(10)

        self.velocity_chart = VelocityChartWidget()
        velocity_layout.addWidget(self.velocity_chart)

        weekly_row = QHBoxLayout()
        weekly_row.addWidget(completion)
        weekly_row.addWidget(consistency)
        self.content.addLayout(weekly_row)

        pomodoro_trend = self._make_card("Pomodoro Trend")
        pomodoro_trend_layout = pomodoro_trend.layout()
        pomodoro_trend_layout.setSpacing(10)
        self.pomo_chart = PomodoroBarChart()
        pomodoro_trend_layout.addWidget(self.pomo_chart)
        self.content.addWidget(pomodoro_trend)

        self.content.addWidget(heatmap)
        self.content.addWidget(velocity)

        self.content.addStretch()

    def _make_card(self, title_text):
        card = QFrame()
        card.setObjectName("DashCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title = QLabel(title_text)
        title.setObjectName("DashCardTitle")
        self.labels_main.append(title)
        layout.addWidget(title)

        self.cards.append(card)
        return card

    def _section_header(self, title_text):
        row = QHBoxLayout()
        title = QLabel(title_text)
        title.setObjectName("DashSection")
        self.section_titles.append(title)
        row.addWidget(title)
        row.addStretch()
        if title_text == "AI Insights":
            btn = QPushButton("Refresh")
            btn.setObjectName("DashLink")
            btn.clicked.connect(self._on_refresh_clicked)
            self.refresh_button = btn
            row.addWidget(btn)
        return row

    def _set_default_metrics(self):
        self.focus_value = 0
        self.focus_delta_value = 0
        self.energy_values = [12, 12, 12, 12, 12]
        self.energy_level_text = "No data"
        self.energy_drop_text = "Need more history"
        self.pomo_minutes_week = 0
        self.pomo_sessions_week = 0
        self.pomo_minutes_total = 0
        self.pomo_sessions_total = 0
        self.pomo_avg_minutes = 0
        self.pomo_best_day_label = "-"
        self.pomo_best_day_minutes = 0
        self.pomo_day_minutes = [0, 0, 0, 0, 0, 0, 0]
        self.pomo_day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.consistency_levels = [0, 0, 0, 0, 0, 0, 0]
        self.consistency_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.consistency_labels_data = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.heatmap_values = [
            [0] * 12,
            [0] * 12,
            [0] * 12
        ]
        self.heatmap_day_labels_data = ["Mon", "Tue", "Wed"]
        self.heatmap_time_labels_data = _heatmap_time_labels_2h()
        self.velocity_values = [4, 4, 4, 4, 4, 4, 4]
        self.velocity_counts = [0, 0, 0, 0, 0, 0, 0]
        self.velocity_capacity = [0, 0, 0, 0, 0, 0, 0]
        self.velocity_point_value = 0
        self.velocity_point_index = 3
        self.velocity_day_labels_data = ["M", "T", "W", "T", "F", "S", "S"]
        self.completion_value = 0
        self.completion_date = "No forecast"

    def _apply_metrics(self):
        self.focus_score.setText(str(self.focus_value))
        self.focus_bar.setValue(self.focus_value)
        delta_prefix = "+" if self.focus_delta_value >= 0 else ""
        self.focus_delta.setText(f"{delta_prefix}{self.focus_delta_value}% vs last week")
        self.focus_delta.setProperty("trend", "up" if self.focus_delta_value >= 0 else "down")

        self.energy_label.setText(self.energy_level_text)
        self.energy_note.setText(self.energy_drop_text)
        for bar, height in zip(self.energy_bars, self.energy_values):
            bar.setFixedHeight(height)

        if hasattr(self, "pomo_minutes_label"):
            self.pomo_minutes_label.setText(self._format_minutes(self.pomo_minutes_week))
        if hasattr(self, "pomo_sessions_label"):
            self.pomo_sessions_label.setText(f"{self.pomo_sessions_week} sessions this week")
        if hasattr(self, "pomo_avg_label"):
            self.pomo_avg_label.setText(f"Avg session: {self._format_minutes(self.pomo_avg_minutes)}")
        if hasattr(self, "pomo_best_label"):
            if self.pomo_best_day_minutes > 0:
                best_txt = f"Best day: {self.pomo_best_day_label} ({self._format_minutes(self.pomo_best_day_minutes)})"
            else:
                best_txt = "Best day: -"
            self.pomo_best_label.setText(best_txt)

        self.completion_bar.setValue(self.completion_value)
        self.completion_label.setText(self.completion_date)
        self.completion_note.setText(f"{self.completion_value}% predicted progress")

        if self.consistency_chart:
            self.consistency_chart.set_data(self.consistency_values, self.consistency_labels_data)

        if self.heatmap_chart:
            self.heatmap_chart.set_data(
                self.heatmap_values,
                self.heatmap_day_labels_data,
                self.heatmap_time_labels_data
            )

        if self.velocity_chart:
            counts = self.velocity_counts if self.velocity_counts else self.velocity_values
            self.velocity_chart.set_data(
                counts,
                self.velocity_capacity if self.velocity_capacity else counts,
                self.velocity_day_labels_data,
                self.velocity_point_value,
                self.velocity_point_index
            )
        if hasattr(self, "pomo_chart") and self.pomo_chart:
            self.pomo_chart.set_data(self.pomo_day_minutes, self.pomo_day_labels)

        self._apply_dynamic_styles()

    def _on_refresh_clicked(self):
        self._load_metrics_from_db()

    def refresh_dashboard(self):
        """Public method to refresh dashboard metrics (used by MainApp)."""
        self._load_metrics_from_db()

    def _on_schedule_clicked(self):
        self.header_chip.setProperty("state", "saved")
        self.header_chip.setText("Saved")
        self._set_status("Deep work scheduled")
        self._apply_dynamic_styles()
        QTimer.singleShot(2200, self._reset_header_chip)

    def _reset_header_chip(self):
        self.header_chip.setProperty("state", "live")
        self.header_chip.setText("Live")
        self._set_status("Ready for the next action")
        self._apply_dynamic_styles()

    def _set_status(self, text):
        if self.header_status:
            self.header_status.setText(text)

    def _format_minutes(self, minutes):
        minutes = int(minutes or 0)
        if minutes >= 60:
            hours = minutes // 60
            rem = minutes % 60
            if rem == 0:
                return f"{hours}h"
            return f"{hours}h {rem}m"
        return f"{minutes} min"

    def _parse_date(self, value):
        if not value:
            return None, False
        text = str(value).strip()
        if not text:
            return None, False
        text = text.split(".")[0]
        if "T" in text:
            text = text.replace("T", " ")
        formats = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")
        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed, fmt != "%Y-%m-%d"
            except ValueError:
                continue
        return None, False

    def _load_metrics_from_db(self):
        tasks = []
        select_cols = []
        conn = get_db_connection()
        try:
            info = conn.execute("PRAGMA table_info(tasks)").fetchall()
            if not info:
                self._set_default_metrics()
                self._apply_metrics()
                self._set_status("No history yet")
                return
            cols = {row[1] for row in info}
            base_cols = ["id", "title", "priority", "created_date", "due_date", "is_completed", "completed_at"]
            select_cols = [col for col in base_cols if col in cols]
            if not select_cols:
                self._set_default_metrics()
                self._apply_metrics()
                self._set_status("No history yet")
                return
            rows = conn.execute(f"SELECT {', '.join(select_cols)} FROM tasks").fetchall()
        except Exception as exc:
            print("DB Error (Dashboard):", exc)
            rows = []
        finally:
            conn.close()

        for row in rows:
            data = {}
            for idx, col in enumerate(select_cols):
                data[col] = row[idx]
            tasks.append(data)

        if not tasks:
            self._set_default_metrics()
            now = datetime.now().strftime("%I:%M %p").lstrip("0")
            self._set_status(f"Updated {now}")
            self.header_chip.setProperty("state", "live")
            self.header_chip.setText("Live")
            self._load_pomodoro_metrics()
            self._apply_metrics()
            return

        today = datetime.now().date()
        last_7_start = today - timedelta(days=6)
        prev_7_start = today - timedelta(days=13)
        prev_7_end = today - timedelta(days=7)

        created_dates = []
        completed_dates = []
        completed_times = []
        completed_total = 0

        for task in tasks:
            created_dt, _ = self._parse_date(task.get("created_date"))
            if not created_dt:
                created_dt, _ = self._parse_date(task.get("due_date"))
            if created_dt:
                created_dates.append(created_dt.date())

            is_completed = int(task.get("is_completed") or 0) == 1
            if is_completed:
                completed_total += 1
                completed_dt, has_time = self._parse_date(task.get("completed_at"))
                if completed_dt:
                    completed_dates.append(completed_dt.date())
                    if has_time:
                        completed_times.append(completed_dt)
                else:
                    if created_dt:
                        completed_dates.append(created_dt.date())

        created_last7 = sum(1 for d in created_dates if last_7_start <= d <= today)
        created_prev7 = sum(1 for d in created_dates if prev_7_start <= d <= prev_7_end)
        completed_last7 = sum(1 for d in completed_dates if last_7_start <= d <= today)
        completed_prev7 = sum(1 for d in completed_dates if prev_7_start <= d <= prev_7_end)

        total_tasks = len(tasks)
        overall_rate = completed_total / total_tasks if total_tasks else 0
        focus_rate = completed_last7 / created_last7 if created_last7 else overall_rate
        prev_rate = completed_prev7 / created_prev7 if created_prev7 else (focus_rate if created_last7 else overall_rate)

        self.focus_value = int(round(focus_rate * 100))
        self.focus_delta_value = int(round((focus_rate - prev_rate) * 100))

        # Energy level from completion times (fallback to last 5 days)
        bucket_counts = [0, 0, 0, 0, 0]
        time_buckets = [(6, 9), (9, 12), (12, 15), (15, 18), (18, 21)]
        recent_cutoff = today - timedelta(days=14)
        for dt in completed_times:
            if dt.date() < recent_cutoff:
                continue
            for idx, (start, end) in enumerate(time_buckets):
                if start <= dt.hour < end:
                    bucket_counts[idx] += 1
                    break

        if sum(bucket_counts) == 0:
            last_5_days = [today - timedelta(days=4 - i) for i in range(5)]
            bucket_counts = [sum(1 for d in completed_dates if d == day) for day in last_5_days]
            energy_has_time = False
        else:
            energy_has_time = True

        max_bucket = max(bucket_counts) if bucket_counts else 0
        if max_bucket == 0:
            self.energy_values = [12, 12, 12, 12, 12]
            self.energy_level_text = "No data"
            self.energy_drop_text = "Need more history"
        else:
            self.energy_values = [12 + int(round((count / max_bucket) * 18)) for count in bucket_counts]
            avg_bucket = sum(bucket_counts) / len(bucket_counts)
            if max_bucket >= max(2, avg_bucket * 1.5):
                self.energy_level_text = "Peak"
            elif max_bucket >= avg_bucket * 1.1:
                self.energy_level_text = "Steady"
            else:
                self.energy_level_text = "Low"
            if energy_has_time:
                drop_labels = ["9:00 AM", "12:00 PM", "3:00 PM", "6:00 PM", "9:00 PM"]
                min_idx = bucket_counts.index(min(bucket_counts))
                self.energy_drop_text = f"Next drop: {drop_labels[min_idx]}"
            else:
                self.energy_drop_text = "Need more history"

        # Focus consistency (last 7 days)
        last_7_days = [today - timedelta(days=6 - i) for i in range(7)]
        day_counts = [sum(1 for d in completed_dates if d == day) for day in last_7_days]
        max_day = max(day_counts) if day_counts else 0
        self.consistency_levels = []
        self.consistency_values = []
        for count in day_counts:
            if max_day == 0 or count == 0:
                level = 0
                value = 0.0
            else:
                ratio = count / max_day
                value = ratio
                if ratio <= 0.33:
                    level = 1
                elif ratio <= 0.66:
                    level = 2
                else:
                    level = 3
            self.consistency_levels.append(level)
            self.consistency_values.append(value)

        self.consistency_labels_data = [day.strftime("%a") for day in last_7_days]

        # Heatmap (last 3 days, 2-hour buckets across full day)
        last_3_days = [today - timedelta(days=2 - i) for i in range(3)]
        bucket_labels = _heatmap_time_labels_2h()
        bucket_count = len(bucket_labels)
        heat_counts = [[0 for _ in range(bucket_count)] for _ in range(3)]

        def heat_bucket(hour):
            return hour // 2

        for dt in completed_times:
            if dt.date() in last_3_days:
                row_idx = last_3_days.index(dt.date())
                bucket = heat_bucket(dt.hour)
                heat_counts[row_idx][bucket] += 1

        has_heat_time = any(sum(row) > 0 for row in heat_counts)
        if not has_heat_time:
            fallback_counts = [sum(1 for d in completed_dates if d == day) for day in last_3_days]
            max_fallback = max(fallback_counts) if fallback_counts else 0
            self.heatmap_values = []
            for count in fallback_counts:
                if max_fallback == 0 or count == 0:
                    level = 0
                else:
                    ratio = count / max_fallback
                    if ratio <= 0.33:
                        level = 1
                    elif ratio <= 0.66:
                        level = 2
                    else:
                        level = 3
                self.heatmap_values.append([level] * bucket_count)
        else:
            max_heat = max(max(row) for row in heat_counts) if heat_counts else 0
            self.heatmap_values = []
            for row in heat_counts:
                levels = []
                for count in row:
                    if max_heat == 0 or count == 0:
                        level = 0
                    else:
                        ratio = count / max_heat
                        if ratio <= 0.33:
                            level = 1
                        elif ratio <= 0.66:
                            level = 2
                        else:
                            level = 3
                    levels.append(level)
                self.heatmap_values.append(levels)

        self.heatmap_day_labels_data = [day.strftime("%a") for day in last_3_days]
        self.heatmap_time_labels_data = bucket_labels

        # Velocity (last 7 days completions)
        max_velocity = max(day_counts) if day_counts else 0
        if max_velocity == 0:
            self.velocity_values = [4 for _ in range(7)]
        else:
            self.velocity_values = [
                4 + int(round((count / max_velocity) * 8)) for count in day_counts
            ]

        self.velocity_day_labels_data = [day.strftime("%a")[0] for day in last_7_days]
        self.velocity_counts = day_counts
        avg_velocity = sum(day_counts) / len(day_counts) if day_counts else 0
        self.velocity_capacity = []
        for i, count in enumerate(day_counts):
            left = day_counts[i - 1] if i > 0 else count
            right = day_counts[i + 1] if i < len(day_counts) - 1 else count
            smooth = (left + count + right) / 3
            capacity = max(smooth, avg_velocity) + avg_velocity * 0.2
            self.velocity_capacity.append(round(capacity, 2))
        self.velocity_point_value = sum(day_counts)
        self.velocity_point_index = last_7_days.index(today) if today in last_7_days else 3

        # Completion forecast
        remaining = max(total_tasks - completed_total, 0)
        if remaining == 0 and total_tasks > 0:
            self.completion_date = "All caught up"
        else:
            avg_recent = completed_last7 / 7 if completed_last7 > 0 else 0
            if avg_recent == 0 and completed_dates:
                first_done = min(completed_dates)
                days_span = max((today - first_done).days + 1, 1)
                avg_recent = len(completed_dates) / days_span
            if avg_recent > 0:
                days_left = ceil(remaining / avg_recent)
                forecast = today + timedelta(days=days_left)
                self.completion_date = forecast.strftime("%a, %b %d")
            else:
                self.completion_date = "No forecast"

        self.completion_value = int(round(overall_rate * 100))

        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        self._set_status(f"Updated {now}")
        self.header_chip.setProperty("state", "live")
        self.header_chip.setText("Live")
        self._load_pomodoro_metrics()
        self._apply_metrics()

    def _load_pomodoro_metrics(self):
        self.pomo_minutes_week = 0
        self.pomo_sessions_week = 0
        self.pomo_minutes_total = 0
        self.pomo_sessions_total = 0
        today = datetime.now().date()
        last_7_start = today - timedelta(days=6)

        conn = get_db_connection()
        try:
            info = conn.execute("PRAGMA table_info(pomodoro_sessions)").fetchall()
            if not info:
                return
            rows = conn.execute(
                "SELECT started_at, duration_min, status FROM pomodoro_sessions"
            ).fetchall()
        except Exception as exc:
            print("DB Error (Pomodoro Stats):", exc)
            rows = []
        finally:
            conn.close()

        day_map = {i: 0 for i in range(7)}
        for started_at, duration_min, status in rows:
            if status and str(status).lower() != "completed":
                continue
            dur = int(duration_min or 0)
            self.pomo_minutes_total += dur
            self.pomo_sessions_total += 1
            dt, _ = self._parse_date(started_at)
            if dt and last_7_start <= dt.date() <= today:
                self.pomo_minutes_week += dur
                self.pomo_sessions_week += 1
                day_index = (dt.date() - last_7_start).days
                if 0 <= day_index <= 6:
                    day_map[day_index] += dur

        self.pomo_day_minutes = [day_map[i] for i in range(7)]
        self.pomo_day_labels = [(last_7_start + timedelta(days=i)).strftime("%a") for i in range(7)]
        if self.pomo_sessions_week > 0:
            self.pomo_avg_minutes = int(round(self.pomo_minutes_week / max(self.pomo_sessions_week, 1)))
        else:
            self.pomo_avg_minutes = 0

        if self.pomo_day_minutes:
            max_val = max(self.pomo_day_minutes)
            if max_val > 0:
                best_idx = self.pomo_day_minutes.index(max_val)
                self.pomo_best_day_minutes = max_val
                self.pomo_best_day_label = self.pomo_day_labels[best_idx]

    def _apply_dynamic_styles(self):
        if not self._colors:
            return
        colors = self._colors
        trend = self.focus_delta.property("trend")
        delta_color = colors["good"] if trend == "up" else colors["bad"]
        self.focus_delta.setStyleSheet(
            f"color: {delta_color}; font-size: 11px; font-weight: 700;"
        )

        max_energy = max(self.energy_values) if self.energy_values else 1
        for bar, value in zip(self.energy_bars, self.energy_values):
            if value >= max_energy * 0.85:
                c = colors["accent"]
            elif value >= max_energy * 0.65:
                c = colors["accent2"]
            else:
                c = colors["border"]
            bar.setStyleSheet(f"QFrame#DashEnergyBar {{ background: {c}; border-radius: 4px; }}")

        state = self.header_chip.property("state") or "live"
        if state == "saved":
            chip_bg = colors["good"]
            chip_text = "#ffffff"
        else:
            chip_bg = colors["chip"]
            chip_text = colors["chip_text"]
        self.header_chip.setStyleSheet(
            f"background: {chip_bg}; color: {chip_text}; border-radius: 12px; font-size: 11px; font-weight: 800;"
        )

    def update_theme(self, theme):
        self.current_theme = theme
        if theme == "Dark":
            colors = {
                "bg": "#0B0F1A",
                "card": "#121828",
                "border": "#22304A",
                "text": "#F8FAFC",
                "sub": "#94A3B8",
                "accent": "#38BDF8",
                "accent2": "#22D3EE",
                "accent_soft": "#0B3A5A",
                "chip": "#0B3A5A",
                "chip_text": "#7DD3FC",
                "primary": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0B3A5A, stop:1 #0F172A)",
                "secondary": "#111827",
                "shadow": "#0B1220",
                "heat0": "#1F2937",
                "heat1": "#0B4A6E",
                "heat2": "#0284C7",
                "heat3": "#38BDF8",
                "velocity": "#38BDF8",
                "capacity": "#A855F7",
                "chart_grid": "#1F2937",
                "good": "#22C55E",
                "bad": "#F87171",
            }
        else:
            colors = {
                "bg": "#F4F7FF",
                "card": "#FFFFFF",
                "border": "#D6E4FF",
                "text": "#0B132B",
                "sub": "#5B6B8A",
                "accent": "#2563EB",
                "accent2": "#06B6D4",
                "accent_soft": "#DBEAFE",
                "chip": "#E0F2FF",
                "chip_text": "#2563EB",
                "primary": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #E0F2FF, stop:1 #DBEAFE)",
                "secondary": "#F8FAFF",
                "shadow": "#DCE7FF",
                "heat0": "#E2E8F0",
                "heat1": "#93C5FD",
                "heat2": "#60A5FA",
                "heat3": "#2563EB",
                "velocity": "#2563EB",
                "capacity": "#7C3AED",
                "chart_grid": "#E2E8F0",
                "good": "#22C55E",
                "bad": "#EF4444",
            }

        self._colors = colors

        self.setStyleSheet(
            "QWidget#DashboardPage { background: %s; }" % colors["bg"]
        )

        self.kicker.setStyleSheet(
            "color: %s; font-size: 11px; font-weight: 800;" % colors["accent"]
        )
        self.title.setStyleSheet(
            "color: %s; font-size: 30px; font-weight: 900;" % colors["text"]
        )
        self.subtitle.setStyleSheet(
            "color: %s; font-size: 13px; font-weight: 600;" % colors["sub"]
        )
        if self.header_status:
            self.header_status.setStyleSheet(
                "color: %s; font-size: 11px; font-weight: 600;" % colors["sub"]
            )

        for title in self.section_titles:
            title.setStyleSheet(
                "color: %s; font-size: 16px; font-weight: 800;" % colors["text"]
            )

        for lbl in self.labels_main:
            if lbl.objectName() == "DashScore":
                lbl.setStyleSheet(
                    "color: %s; font-size: 34px; font-weight: 900;" % colors["text"]
                )
            elif lbl is self.energy_label:
                lbl.setStyleSheet(
                    "color: %s; font-size: 18px; font-weight: 800;" % colors["accent"]
                )
            elif lbl.objectName() == "DashCardTitle":
                lbl.setStyleSheet(
                    "color: %s; font-size: 14px; font-weight: 800;" % colors["text"]
                )
            elif lbl.objectName() == "DashAccent":
                lbl.setStyleSheet(
                    "color: %s; font-size: 12px; font-weight: 800;" % colors["accent"]
                )
            else:
                lbl.setStyleSheet(
                    "color: %s; font-size: 13px; font-weight: 700;" % colors["text"]
                )

        for lbl in self.labels_sub:
            if lbl.objectName() in ("DashDay", "DashDaySmall"):
                lbl.setStyleSheet(
                    "color: %s; font-size: 10px; font-weight: 700;" % colors["sub"]
                )
            else:
                lbl.setStyleSheet(
                    "color: %s; font-size: 11px; font-weight: 600;" % colors["sub"]
                )

        for card in self.cards:
            card.setStyleSheet(
                "QFrame#DashCard { background: %s; border: 1px solid %s; border-radius: 20px; }" %
                (colors["card"], colors["border"])
            )

        header = self.findChild(QFrame, "DashHeader")
        if header:
            header.setStyleSheet(
                "QFrame#DashHeader { background: %s; border: 1px solid %s; border-radius: 20px; }" %
                (colors["primary"], colors["border"])
            )

        for badge in self.badges:
            badge.setStyleSheet(
                "background: %s; color: %s; border-radius: 10px; font-size: 10px; font-weight: 800; padding: 2px 6px;" %
                (colors["accent_soft"], colors["accent"])
            )

        for bar in self.progress_bars:
            bar.setStyleSheet(
                "QProgressBar { background: %s; border: none; border-radius: 5px; }"
                "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 %s, stop:1 %s); border-radius: 5px; }" %
                (colors["border"], colors["accent2"], colors["accent"])
            )

        primary = self.findChild(QFrame, "DashPrimary")
        if primary:
            primary.setStyleSheet(
                "QFrame#DashPrimary { background: %s; border: 1px solid %s; border-radius: 22px; }" %
                (colors["primary"], colors["border"])
            )

        secondary = self.findChild(QFrame, "DashSecondary")
        if secondary:
            secondary.setStyleSheet(
                "QFrame#DashSecondary { background: %s; border: 1px solid %s; border-radius: 18px; }" %
                (colors["secondary"], colors["border"])
            )

        icon = self.findChild(QFrame, "DashIcon")
        if icon:
            icon.setStyleSheet(
                "QFrame#DashIcon { background: %s; border-radius: 20px; border: 1px solid %s; }" %
                (colors["accent_soft"], colors["border"])
            )

        for btn in self.findChildren(QPushButton, "DashAction"):
            btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 %s, stop:1 %s); color: white; border-radius: 12px; padding: 10px; font-weight: bold; }"
                "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 %s, stop:1 %s); }" %
                (colors["accent2"], colors["accent"], colors["accent"], colors["accent2"])
            )

        for link in self.findChildren(QPushButton, "DashLink"):
            link.setStyleSheet(
                "QPushButton { background: transparent; color: %s; border: none; font-weight: bold; }"
                "QPushButton:hover { color: %s; }" % (colors["accent"], colors["accent2"])
            )

        for acc in self.findChildren(QLabel, "DashAccent"):
            acc.setStyleSheet(
                "color: %s; font-size: 12px; font-weight: 800;" % colors["accent"]
            )

        if self.consistency_chart:
            self.consistency_chart.set_theme(colors, theme)
        if self.heatmap_chart:
            self.heatmap_chart.set_theme(colors, theme)
        if self.velocity_chart:
            self.velocity_chart.set_theme(colors, theme)
        if hasattr(self, "pomo_chart") and self.pomo_chart:
            self.pomo_chart.set_theme(colors, theme)

        self._apply_dynamic_styles()
