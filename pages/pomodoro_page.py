from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, QTimer

class PomodoroPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f7fafc;")
        layout = QHBoxLayout(self)
        
        # Variables du timer
        self.time_left = 25 * 60  # 25 minutes en secondes
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)

        # --- GAUCHE : UI DU TIMER ---
        container = QFrame()
        container.setStyleSheet("background-color: white; border-radius: 20px; border: 1px solid #edf2f7;")
        c_layout = QVBoxLayout(container)
        
        self.label = QLabel("25:00")
        self.label.setStyleSheet("font-size: 100px; font-weight: bold; color: #2d3748; border: none;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_box = QHBoxLayout()
        self.btn_start = QPushButton("Start")
        self.btn_start.setFixedSize(120, 45)
        self.btn_start.setStyleSheet("background-color: #3182ce; color: white; border-radius: 10px; font-weight: bold;")
        self.btn_start.clicked.connect(self.toggle_timer)
        
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setFixedSize(120, 45)
        self.btn_reset.setStyleSheet("background-color: white; border: 1px solid #cbd5e0; border-radius: 10px;")
        self.btn_reset.clicked.connect(self.reset_timer)
        
        btn_box.addStretch()
        btn_box.addWidget(self.btn_start)
        btn_box.addWidget(self.btn_reset)
        btn_box.addStretch()
        
        c_layout.addStretch()
        c_layout.addWidget(self.label)
        c_layout.addLayout(btn_box)
        c_layout.addStretch()

        layout.addWidget(container)

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            mins, secs = divmod(self.time_left, 60)
            self.label.setText(f"{mins:02d}:{secs:02d}")
        else:
            self.timer.stop()

    def toggle_timer(self):
        if self.timer.isActive():
            self.timer.stop()
            self.btn_start.setText("Start")
        else:
            self.timer.start(1000)
            self.btn_start.setText("Pause")

    def reset_timer(self):
        self.timer.stop()
        self.time_left = 25 * 60
        self.label.setText("25:00")
        self.btn_start.setText("Start")